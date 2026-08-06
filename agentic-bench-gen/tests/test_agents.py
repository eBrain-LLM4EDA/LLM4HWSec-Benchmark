import json

import pytest

from agentic_bench_gen.agents import AgentConfig, FileBundleAgent, JsonAgent, _plan_schema

BUNDLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["manifest", "files"],
    "properties": {
        "manifest": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "purpose"],
                "properties": {"path": {"type": "string"}, "purpose": {"type": "string"}},
            },
        },
        "files": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "content"],
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            },
        },
    },
}


class _FakeLLM:
    def __init__(self, plan):
        self.plan = plan
        self.json_calls = []
        self.text_calls = []

    def complete_json(self, **kwargs):
        self.json_calls.append(kwargs)
        return self.plan

    def complete_text(self, **kwargs):
        self.text_calls.append(kwargs)
        return f"content {len(self.text_calls)}"


def _make_agent(tmp_path, plan):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Build the case for {{x}}.")
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="builder", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=1000, reasoning={"max_tokens": 100},
    )
    return FileBundleAgent(_FakeLLM(plan), config)


SIMPLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status"],
    "properties": {"status": {"type": "string"}},
}


class _ScriptedLLM:
    """Returns one scripted JSON result per complete_json call."""

    def __init__(self, results):
        self._results = list(results)
        self.json_calls = []

    def complete_json(self, **kwargs):
        self.json_calls.append(kwargs)
        return self._results.pop(0)


def _make_json_agent(tmp_path, results):
    prompt = tmp_path / "p.md"
    prompt.write_text("Do {{x}}. Return JSON only.")
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(SIMPLE_SCHEMA))
    config = AgentConfig(
        name="a", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=100,
    )
    return JsonAgent(_ScriptedLLM(results), config)


def test_json_agent_puts_the_schema_in_the_user_message(tmp_path):
    # The prompts only say "Return JSON only"; the schema must travel in the
    # messages too, so the shape survives a provider that ignores or rejects
    # response_format.
    agent = _make_json_agent(tmp_path, [{"status": "ok"}])
    agent.run({"x": "y"})
    user_msg = agent.llm.json_calls[0]["messages"][1]["content"]
    assert "JSON Schema" in user_msg
    assert '"status"' in user_msg


def test_json_agent_repairs_invalid_response_with_the_validation_error(tmp_path):
    agent = _make_json_agent(tmp_path, [
        {"wrong_key": 1},          # violates SIMPLE_SCHEMA
        {"status": "ok"},          # repaired
    ])
    assert agent.run({"x": "y"}) == {"status": "ok"}
    repair_messages = agent.llm.json_calls[1]["messages"]
    # system + user + previous assistant response + repair request
    assert [m["role"] for m in repair_messages] == ["system", "user", "assistant", "user"]
    assert "wrong_key" in repair_messages[2]["content"]
    assert "does not validate" in repair_messages[3]["content"]


def test_json_agent_gives_up_after_max_repairs(tmp_path):
    agent = _make_json_agent(tmp_path, [{"bad": 1}, {"bad": 2}, {"bad": 3}, {"bad": 4}])
    with pytest.raises(ValueError, match="Schema validation failed"):
        agent.run({"x": "y"})
    # initial call + max_schema_repairs repair rounds
    assert len(agent.llm.json_calls) == 1 + JsonAgent.max_schema_repairs


def test_file_bundle_agent_plan_phase_repairs_schema_invalid_plan(tmp_path):
    prompt = tmp_path / "p.md"
    prompt.write_text("Build {{x}}.")
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="builder", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=100,
    )
    llm = _ScriptedLLM([
        {"manifest": [{"path": "inputs/a.c"}]},                      # missing 'purpose'
        {"manifest": [{"path": "inputs/a.c", "purpose": "code"}]},   # repaired
    ])
    llm.text_calls = []
    llm.complete_text = lambda **kw: (llm.text_calls.append(kw), "body")[1]
    agent = FileBundleAgent(llm, config)

    bundle = agent.run({"x": "y"})

    assert len(llm.json_calls) == 2
    assert bundle["files"] == [{"path": "inputs/a.c", "content": "body"}]


def test_file_bundle_plan_phase_uses_a_capped_budget(tmp_path):
    # The plan is a manifest, not the bundle: it gets ~12K (plus the thinking
    # budget) even when the agent's per-file budget is 48K, and its truncation
    # escalation is capped at twice that instead of the 64K instance ceiling.
    prompt = tmp_path / "p.md"
    prompt.write_text("Build {{x}}.")
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="tester", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=48000, reasoning={"max_tokens": 8000},
    )
    agent = FileBundleAgent(
        _FakeLLM({"manifest": [{"path": "evaluation/evaluate.py", "purpose": "grader"}]}),
        config,
    )
    agent.run({"x": "y"})
    plan_call = agent.llm.json_calls[0]
    # (12000 + 8000 reasoning) * 2: unenforced adaptive thinking bills inside
    # completion_tokens, and the 1x budget truncated ~half the real plan calls.
    assert plan_call["max_tokens"] == 40000
    assert plan_call["escalation_cap"] == 48000        # capped by max_tokens
    # Per-file emission keeps the full budget.
    assert agent.llm.text_calls[0]["max_tokens"] == 48000


def test_plan_schema_drops_files_but_keeps_the_rest():
    plan = _plan_schema(BUNDLE_SCHEMA)
    assert "files" not in plan["properties"]
    assert "files" not in plan["required"]
    assert "manifest" in plan["required"]
    # The original schema must remain untouched (used to validate the final bundle).
    assert "files" in BUNDLE_SCHEMA["properties"]
    assert "files" in BUNDLE_SCHEMA["required"]


def test_file_bundle_agent_assembles_bundle_from_plan_and_per_file_calls(tmp_path):
    plan = {"manifest": [
        {"path": "inputs/kernel.c", "purpose": "insecure baseline implementation"},
        {"path": "README.md", "purpose": "participant instructions"},
    ]}
    agent = _make_agent(tmp_path, plan)

    bundle = agent.run({"x": "y"})

    assert [f["path"] for f in bundle["files"]] == ["inputs/kernel.c", "README.md"]
    assert bundle["files"][0]["content"] == "content 1"
    assert bundle["manifest"] == plan["manifest"]
    # Phase 1 used the derived plan schema (no files required).
    assert "files" not in agent.llm.json_calls[0]["schema"]["properties"]
    # Per-agent reasoning config reaches both phases.
    assert agent.llm.json_calls[0]["reasoning"] == {"max_tokens": 100}
    assert agent.llm.text_calls[0]["reasoning"] == {"max_tokens": 100}


def test_file_bundle_agent_gives_later_files_the_earlier_content(tmp_path):
    plan = {"manifest": [
        {"path": "inputs/kernel.c", "purpose": "code"},
        {"path": "README.md", "purpose": "docs referencing the code"},
    ]}
    agent = _make_agent(tmp_path, plan)
    agent.run({"x": "y"})

    second_request = agent.llm.text_calls[1]["messages"][1]["content"]
    assert "content 1" in second_request           # earlier file's final content
    assert "inputs/kernel.c" in second_request     # and its path
    assert "README.md" in second_request           # the file being requested


def test_file_bundle_retries_oversized_file_with_compact_request(tmp_path):
    plan = {"manifest": [{"path": "inputs/netlist.v", "purpose": "compact netlist"}]}
    agent = _make_agent(tmp_path, plan)
    calls = []

    def complete_text(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("OpenRouter completion failed: output is too large")
        return "module compact; endmodule"

    agent.llm.complete_text = complete_text
    bundle = agent.run({"x": "y"})
    assert bundle["files"][0]["content"] == "module compact; endmodule"
    assert len(calls) == 2
    assert "COMPACT REPLACEMENT REQUIRED" in calls[1]["messages"][1]["content"]
    assert calls[1]["max_tokens"] <= 16000


def test_file_bundle_targeted_repair_skips_plan_and_unrelated_files(tmp_path):
    plan = {"manifest": [
        {"path": "evaluation/evaluate.py", "purpose": "grader"},
        {"path": "evaluation/private/tb.v", "purpose": "simulation evidence"},
        {"path": "evaluation/README.md", "purpose": "docs"},
    ]}
    agent = _make_agent(tmp_path, plan)
    previous = {**plan, "files": [
        {"path": "evaluation/evaluate.py", "content": "old grader"},
        {"path": "evaluation/private/tb.v", "content": "old tb"},
        {"path": "evaluation/README.md", "content": "old docs"},
    ]}

    repaired = agent.repair_files(
        {"x": "y", "repair_notes": "fix evidence", "previous_bundle_json": previous},
        previous,
        ["evaluation/private/tb.v", "evaluation/evaluate.py"],
    )

    assert agent.llm.json_calls == []
    assert len(agent.llm.text_calls) == 2
    by_path = {item["path"]: item["content"] for item in repaired["files"]}
    assert by_path == {
        "evaluation/evaluate.py": "content 2",
        "evaluation/private/tb.v": "content 1",
        "evaluation/README.md": "old docs",
    }


def test_file_bundle_agent_rejects_empty_manifest(tmp_path):
    agent = _make_agent(tmp_path, {"manifest": []})
    with pytest.raises(ValueError, match="empty manifest"):
        agent.run({"x": "y"})


def test_file_bundle_agent_rejects_manifest_entry_without_path(tmp_path):
    agent = _make_agent(tmp_path, {"manifest": [{"path": "  ", "purpose": "p"}]})
    with pytest.raises(ValueError, match="without a path"):
        agent.run({"x": "y"})


def _make_agent_with_allowed(tmp_path, plan, allowed):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Build the case for {{x}}.")
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="builder", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=1000, allowed_paths=allowed,
    )
    return FileBundleAgent(_FakeLLM(plan), config)


def test_file_bundle_agent_drops_out_of_scope_planned_files(tmp_path):
    # The ArtifactBuilder scope-creep case: it plans its own evaluation files,
    # which must be dropped before any per-file completion is spent on them.
    plan = {"manifest": [
        {"path": "README.md", "purpose": "docs"},
        {"path": "inputs/kernel.cpp", "purpose": "baseline"},
        {"path": "evaluation/evaluate.py", "purpose": "grader (not ours)"},
        {"path": "evaluation/harness_main.cpp", "purpose": "harness (not ours)"},
        {"path": "golden/kernel.cpp", "purpose": "golden (not ours)"},
    ]}
    allowed = ["README.md", "metadata.json", "inputs/", "submission/"]
    agent = _make_agent_with_allowed(tmp_path, plan, allowed)

    bundle = agent.run({"x": "y"})

    kept = [f["path"] for f in bundle["files"]]
    assert kept == ["README.md", "inputs/kernel.cpp"]
    # No completion was spent on the dropped files.
    assert len(agent.llm.text_calls) == 2
    # The returned manifest is pruned to match the emitted files.
    assert [m["path"] for m in bundle["manifest"]] == ["README.md", "inputs/kernel.cpp"]


def test_file_bundle_agent_without_allowed_paths_keeps_everything(tmp_path):
    plan = {"manifest": [
        {"path": "evaluation/evaluate.py", "purpose": "grader"},
        {"path": "tests/private/check.py", "purpose": "harness"},
    ]}
    agent = _make_agent_with_allowed(tmp_path, plan, None)
    bundle = agent.run({"x": "y"})
    assert [f["path"] for f in bundle["files"]] == ["evaluation/evaluate.py", "tests/private/check.py"]


def test_file_bundle_agent_raises_when_all_files_out_of_scope(tmp_path):
    plan = {"manifest": [{"path": "evaluation/evaluate.py", "purpose": "grader"}]}
    agent = _make_agent_with_allowed(tmp_path, plan, ["inputs/"])
    with pytest.raises(ValueError, match="out of scope"):
        agent.run({"x": "y"})


def test_file_bundle_agent_drops_path_traversal_even_without_scope_rules(tmp_path):
    plan = {"manifest": [
        {"path": "../escape.txt", "purpose": "unsafe"},
        {"path": "inputs/a.c", "purpose": "safe"},
    ]}
    agent = _make_agent_with_allowed(tmp_path, plan, None)
    bundle = agent.run({"x": "y"})
    assert [item["path"] for item in bundle["files"]] == ["inputs/a.c"]


def test_plan_budget_is_not_doubled_without_reasoning(tmp_path):
    prompt = tmp_path / "p.md"
    prompt.write_text("Build {{x}}.")
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="builder", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=32000,   # no reasoning
    )
    agent = FileBundleAgent(
        _FakeLLM({"manifest": [{"path": "inputs/a.c", "purpose": "code"}]}), config,
    )
    agent.run({"x": "y"})
    assert agent.llm.json_calls[0]["max_tokens"] == 12000   # plain _PLAN_MAX_TOKENS


def test_plan_max_tokens_config_overrides_the_default_plan_budget(tmp_path):
    prompt = tmp_path / "p.md"
    prompt.write_text("Build {{x}}.")
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="tester", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=48000, reasoning={"max_tokens": 8000},
        plan_max_tokens=20000,
    )
    agent = FileBundleAgent(
        _FakeLLM({"manifest": [{"path": "evaluation/evaluate.py", "purpose": "grader"}]}),
        config,
    )
    agent.run({"x": "y"})
    plan_call = agent.llm.json_calls[0]
    # (20000 configured + 8000 reasoning) * 2, saturated by max_tokens.
    assert plan_call["max_tokens"] == 48000
    assert plan_call["escalation_cap"] == 48000
    assert agent.llm.text_calls[0]["max_tokens"] == 48000


def test_effort_based_reasoning_still_gets_doubled_plan_headroom(tmp_path):
    # Effort-style reasoning has no token number to add, but thinking still
    # bills inside completion_tokens — the 2x headroom must apply regardless.
    prompt = tmp_path / "p.md"
    prompt.write_text("Build {{x}}.")
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="tester", model="m", prompt_path=prompt, schema_path=schema,
        temperature=1.0, max_tokens=48000, reasoning={"effort": "high"},
    )
    agent = FileBundleAgent(
        _FakeLLM({"manifest": [{"path": "evaluation/evaluate.py", "purpose": "grader"}]}),
        config,
    )
    agent.run({"x": "y"})
    plan_call = agent.llm.json_calls[0]
    assert plan_call["max_tokens"] == 24000        # _PLAN_MAX_TOKENS * 2
    assert plan_call["reasoning"] == {"effort": "high"}
    assert agent.llm.text_calls[0]["max_tokens"] == 48000


def test_globally_enabled_reasoning_doubles_the_plan_budget_too(tmp_path):
    # An agent without its own reasoning config inherits the pipeline-level
    # default at call time; the plan budget must account for that thinking the
    # same way, or the plan starts at 1x and truncates (seen on
    # artifact_builder repair-round plans with openrouter.reasoning enabled).
    prompt = tmp_path / "p.md"
    prompt.write_text("Build {{x}}.")
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="builder", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=32000,   # no per-agent reasoning
    )
    llm = _FakeLLM({"manifest": [{"path": "inputs/a.c", "purpose": "code"}]})
    llm.reasoning = {"enabled": True}        # pipeline-level default
    agent = FileBundleAgent(llm, config)
    agent.run({"x": "y"})
    assert agent.llm.json_calls[0]["max_tokens"] == 24000   # _PLAN_MAX_TOKENS * 2


def test_agent_reasoning_disable_beats_globally_enabled_reasoning(tmp_path):
    # A per-agent explicit OFF overrides the pipeline default at call time, so
    # the plan budget must stay at 1x.
    prompt = tmp_path / "p.md"
    prompt.write_text("Build {{x}}.")
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="builder", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=32000, reasoning={"enabled": False},
    )
    llm = _FakeLLM({"manifest": [{"path": "inputs/a.c", "purpose": "code"}]})
    llm.reasoning = {"enabled": True}
    agent = FileBundleAgent(llm, config)
    agent.run({"x": "y"})
    assert agent.llm.json_calls[0]["max_tokens"] == 12000


def test_explicitly_disabled_reasoning_gets_plain_plan_budget(tmp_path):
    prompt = tmp_path / "p.md"
    prompt.write_text("Build {{x}}.")
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(BUNDLE_SCHEMA))
    config = AgentConfig(
        name="builder", model="m", prompt_path=prompt, schema_path=schema,
        temperature=0.1, max_tokens=32000, reasoning={"enabled": False},
    )
    agent = FileBundleAgent(
        _FakeLLM({"manifest": [{"path": "inputs/a.c", "purpose": "code"}]}), config,
    )
    agent.run({"x": "y"})
    assert agent.llm.json_calls[0]["max_tokens"] == 12000
