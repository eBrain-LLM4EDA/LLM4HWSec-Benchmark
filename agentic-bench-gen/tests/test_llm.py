from types import SimpleNamespace

import pytest

from agentic_bench_gen.llm import OpenRouterLLM, OpenRouterSettings, _looks_degenerate


class _Msg:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, content, finish_reason):
        self.message = _Msg(content)
        self.finish_reason = finish_reason


class _Resp:
    def __init__(self, content, finish_reason, usage=None):
        self.choices = [_Choice(content, finish_reason)]
        self.usage = usage


class _FakeCompletions:
    """Records every call and returns scripted responses. Script items are
    exceptions, (content, finish_reason) pairs, or (content, finish_reason,
    usage) triples."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = []
        self.kwargs = []

    def create(self, **kwargs):
        self.calls.append(kwargs["max_tokens"])
        self.kwargs.append(kwargs)
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, _Resp):
            return item
        content, finish = item[0], item[1]
        usage = item[2] if len(item) > 2 else None
        return _Resp(content, finish, usage)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


def _usage(prompt=100, completion=100, reasoning=None):
    details = SimpleNamespace(reasoning_tokens=reasoning) if reasoning is not None else None
    return SimpleNamespace(
        prompt_tokens=prompt, completion_tokens=completion, completion_tokens_details=details,
    )


def _make_llm(script, max_output_tokens=64000, reasoning=None, provider=None):
    llm = OpenRouterLLM.__new__(OpenRouterLLM)  # bypass OpenAI client construction
    llm.default_retries = 3
    llm.max_output_tokens = max_output_tokens
    llm.reasoning = reasoning
    llm.provider = provider
    llm.usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "calls": 0}
    llm._response_format_broken = set()
    llm.client = type("C", (), {"chat": _FakeChat(_FakeCompletions(script))})
    return llm


def _call(llm, **overrides):
    kwargs = dict(
        model="m", messages=[], schema_name="s", schema={"type": "object"},
        max_tokens=16000,
    )
    kwargs.update(overrides)
    return llm.complete_json(**kwargs)


def test_escalates_max_tokens_on_truncation_then_succeeds():
    # First call truncates; second (doubled) succeeds.
    llm = _make_llm([
        (None, "length"),
        ('{"ok": true}', "stop"),
    ])
    result = _call(llm)
    assert result == {"ok": True}
    assert llm.client.chat.completions.calls == [16000, 32000]


def test_escalation_is_capped_and_does_not_exceed_max_output_tokens():
    # Every call truncates; escalation stops at the cap, then raises a clear error.
    llm = _make_llm([(None, "length")] * 10, max_output_tokens=64000)
    with pytest.raises(RuntimeError, match="truncated at max_tokens=64000"):
        _call(llm)
    # 16000 -> 32000 -> 64000, then the cap-hit call, no further growth.
    assert llm.client.chat.completions.calls == [16000, 32000, 64000]


def test_successful_call_does_not_escalate():
    llm = _make_llm([('{"ok": 1}', "stop")])
    assert _call(llm) == {"ok": 1}
    assert llm.client.chat.completions.calls == [16000]


def _credit_error(affordable):
    return RuntimeError(
        f"Error code: 402 - {{'error': {{'message': \"This request requires more credits, "
        f"or fewer max_tokens. You requested up to 48000 tokens, but can only afford "
        f"{affordable}.\"}}}}"
    )


def test_credit_limit_reduces_max_tokens_and_retries():
    llm = _make_llm([
        _credit_error(43890),
        ('{"ok": true}', "stop"),
    ])
    result = _call(llm, max_tokens=48000)
    assert result == {"ok": True}
    assert llm.client.chat.completions.calls == [48000, 43890]


def test_key_limit_403_fails_fast_without_retrying():
    # A single create() call; the terminal 403 must not be retried.
    llm = _make_llm([
        RuntimeError("Error code: 403 - {'error': {'message': 'Key limit exceeded (total limit).'}}"),
    ])
    with pytest.raises(RuntimeError, match="account/key limit"):
        _call(llm)
    assert llm.client.chat.completions.calls == [16000]


def test_context_overflow_fails_fast_without_retrying():
    llm = _make_llm([
        RuntimeError(
            "Error code: 400 - {'error': {'message': \"This endpoint's maximum context length "
            "is 200000 tokens. However, you requested about 210000 tokens.\"}}"
        ),
    ])
    with pytest.raises(RuntimeError, match="context window"):
        _call(llm)
    assert llm.client.chat.completions.calls == [16000]


def test_truncation_does_not_escalate_above_credit_ceiling():
    # Credit-capped to 43890, then the response truncates at that ceiling — it must
    # not try to climb back to 64000, and must raise a credit-aware error.
    llm = _make_llm([
        _credit_error(43890),
        (None, "length"),
    ])
    with pytest.raises(RuntimeError, match="credit balance"):
        _call(llm, max_tokens=48000)
    assert llm.client.chat.completions.calls == [48000, 43890]


def test_mislabelled_truncation_escalates_instead_of_same_cap_retries():
    # Truncated JSON (unbalanced braces) but finish_reason says "stop": this is
    # truncation in disguise and must escalate, not retry 3x at the same cap.
    llm = _make_llm([
        ('{"files": [{"path": "a.c", "content": "int', "stop"),
        ('{"ok": true}', "stop"),
    ])
    assert _call(llm) == {"ok": True}
    assert llm.client.chat.completions.calls == [16000, 32000]


def test_invalid_but_complete_json_uses_generic_retry_at_same_cap():
    llm = _make_llm([
        ("not json at all", "stop"),
        ('{"ok": true}', "stop"),
    ])
    assert _call(llm) == {"ok": True}
    assert llm.client.chat.completions.calls == [16000, 16000]


def test_degenerate_repetition_fails_fast_without_escalating():
    looping = '{"files": [' + '"AAAA",\n' * 600
    llm = _make_llm([(looping, "length")])
    with pytest.raises(RuntimeError, match="looping"):
        _call(llm)
    # No escalation retry: raising max_tokens would only extend the loop.
    assert llm.client.chat.completions.calls == [16000]


def test_below_budget_length_stop_retries_at_same_cap_without_escalating():
    # The provider cut the response at ~8K although 32K was requested. That is
    # a provider-side stop, not a token limit: escalation must not happen, but
    # plain retries must (routing may pick a different endpoint).
    llm = _make_llm([
        ('{"partial": ', "length", _usage(completion=8000)),
        ('{"ok": true}', "stop"),
    ])
    assert _call(llm, max_tokens=32000) == {"ok": True}
    assert llm.client.chat.completions.calls == [32000, 32000]


def test_persistent_below_budget_length_stop_eventually_raises():
    llm = _make_llm([('{"partial": ', "length", _usage(completion=8000))] * 5)
    with pytest.raises(RuntimeError, match="provider-side stop"):
        _call(llm, max_tokens=32000)
    # initial + default_retries, all at the same cap — never escalated.
    assert llm.client.chat.completions.calls == [32000] * 4


def test_content_filter_stop_is_retried_then_succeeds():
    # finish_reason='content_filter' (a provider safety layer cut the response
    # mid-JSON) must be retried as its own case — NOT misdiagnosed as a token
    # clamp by the truncated-JSON heuristic.
    llm = _make_llm([
        ('{"ideas": [{"seed_id": "x', "content_filter", _usage(completion=1967)),
        ('{"ok": true}', "stop"),
    ])
    assert _call(llm) == {"ok": True}
    assert llm.client.chat.completions.calls == [16000, 16000]


def test_persistent_content_filter_raises_with_provider_pin_advice():
    llm = _make_llm([("blocked", "content_filter", _usage(completion=10))] * 5)
    with pytest.raises(RuntimeError, match="content_filter.*anthropic"):
        _call(llm)
    assert llm.client.chat.completions.calls == [16000] * 4


def test_provider_pin_is_sent_in_extra_body():
    pin = {"order": ["anthropic"], "allow_fallbacks": False}
    llm = _make_llm([('{"ok": 1}', "stop")], provider=pin)
    _call(llm)
    assert llm.client.chat.completions.kwargs[0]["extra_body"] == {"provider": pin}


def test_provider_pin_survives_the_reasoning_disable_retry():
    pin = {"order": ["anthropic"], "allow_fallbacks": False}
    llm = _make_llm([
        ("", "stop"),
        ('{"ok": 1}', "stop"),
    ], reasoning={"max_tokens": 8000}, provider=pin)
    assert _call(llm) == {"ok": 1}
    kwargs = llm.client.chat.completions.kwargs
    assert kwargs[0]["extra_body"] == {"reasoning": {"max_tokens": 8000}, "provider": pin}
    assert kwargs[1]["extra_body"] == {"reasoning": {"enabled": False}, "provider": pin}


def test_reasoning_config_is_sent_via_extra_body():
    llm = _make_llm([('{"ok": 1}', "stop")], reasoning={"enabled": False})
    _call(llm)
    assert llm.client.chat.completions.kwargs[0]["extra_body"] == {"reasoning": {"enabled": False}}


def test_no_reasoning_config_sends_no_extra_body():
    llm = _make_llm([('{"ok": 1}', "stop")])
    _call(llm)
    assert llm.client.chat.completions.kwargs[0]["extra_body"] is None


def test_usage_totals_accumulate_including_reasoning_tokens():
    llm = _make_llm([
        ('{"ok": 1}', "stop", _usage(prompt=1000, completion=500, reasoning=200)),
    ])
    _call(llm)
    assert llm.usage_totals == {
        "prompt_tokens": 1000, "completion_tokens": 500, "reasoning_tokens": 200, "calls": 1,
    }


def test_complete_text_returns_raw_content_and_strips_fences():
    llm = _make_llm([("```c\nint f() { return 0; }\n```", "stop")])
    out = llm.complete_text(model="m", messages=[], label="builder:inputs/a.c", max_tokens=16000)
    assert out == "int f() { return 0; }"
    # Plain-text completions must not send a response_format.
    assert "response_format" not in llm.client.chat.completions.kwargs[0]


def test_complete_text_escalates_on_truncation():
    llm = _make_llm([
        ("partial file", "length"),
        ("full file content", "stop"),
    ])
    out = llm.complete_text(model="m", messages=[], label="f", max_tokens=16000)
    assert out == "full file content"
    assert llm.client.chat.completions.calls == [16000, 32000]


def test_complete_text_honors_per_file_escalation_cap():
    llm = _make_llm([("partial file", "length")])
    with pytest.raises(RuntimeError, match="output is too large"):
        llm.complete_text(
            model="m", messages=[], label="f", max_tokens=16000,
            escalation_cap=16000,
        )
    assert llm.client.chat.completions.calls == [16000]


def test_per_call_reasoning_overrides_instance_default():
    llm = _make_llm([('{"ok": 1}', "stop")], reasoning={"enabled": False})
    _call(llm, reasoning={"max_tokens": 500})
    assert llm.client.chat.completions.kwargs[0]["extra_body"] == {"reasoning": {"max_tokens": 500}}


def test_looks_degenerate_detects_loops_but_not_normal_code():
    assert _looks_degenerate("x" * 1000) is True
    assert _looks_degenerate('{"a": 1}\n' * 200) is True
    normal = "\n".join(f"int f{i}() {{ return {i}; }}" for i in range(200))
    assert _looks_degenerate(normal) is False
    assert _looks_degenerate("") is False


def test_empty_response_with_reasoning_retries_with_reasoning_explicitly_disabled():
    # First call returns empty content while reasoning is active; the retry
    # sends an EXPLICIT reasoning disable (stripping the field would fall back
    # to the provider default, re-enabling reasoning on reasoning-default
    # models) and succeeds — no crash.
    llm = _make_llm([
        ("", "stop"),
        ('{"ok": true}', "stop"),
    ], reasoning={"max_tokens": 8000})
    result = _call(llm)
    assert result == {"ok": True}
    kwargs = llm.client.chat.completions.kwargs
    assert kwargs[0].get("extra_body") == {"reasoning": {"max_tokens": 8000}}
    assert kwargs[1].get("extra_body") == {"reasoning": {"enabled": False}}


def test_empty_response_with_reasoning_already_disabled_does_not_strip_the_disable():
    # `{"enabled": false}` is an explicit OFF: the empty-response recovery must
    # not treat it as "reasoning active" and strip it (which would re-enable
    # provider-default reasoning). The varied retry instead drops the JSON
    # response_format.
    llm = _make_llm([
        ("", "stop"),
        ('{"ok": true}', "stop"),
    ], reasoning={"enabled": False})
    assert _call(llm) == {"ok": True}
    kwargs = llm.client.chat.completions.kwargs
    assert kwargs[0].get("extra_body") == {"reasoning": {"enabled": False}}
    assert "response_format" in kwargs[0]
    assert kwargs[1].get("extra_body") == {"reasoning": {"enabled": False}}
    assert "response_format" not in kwargs[1]


def test_empty_truncation_with_reasoning_disables_reasoning_instead_of_escalating():
    # finish_reason='length' with EMPTY content means the whole budget went to
    # hidden reasoning — escalating max_tokens only funds longer rumination.
    # The recovery is the empty-response one: retry once with reasoning
    # explicitly disabled, at the SAME budget.
    llm = _make_llm([
        ("", "length"),
        ('{"ok": true}', "stop"),
    ], reasoning={"effort": "high"})
    result = _call(llm)
    assert result == {"ok": True}
    completions = llm.client.chat.completions
    assert completions.calls == [16000, 16000]      # no escalation
    assert completions.kwargs[0].get("extra_body") == {"reasoning": {"effort": "high"}}
    assert completions.kwargs[1].get("extra_body") == {"reasoning": {"enabled": False}}


def test_empty_truncation_after_reasoning_disable_falls_back_to_escalation():
    # If the response still truncates empty AFTER the reasoning-off retry, the
    # one-shot disable is spent and normal escalation takes over.
    llm = _make_llm([
        ("", "length"),
        ("", "length"),
        ('{"ok": true}', "stop"),
    ], reasoning={"effort": "high"})
    assert _call(llm) == {"ok": True}
    assert llm.client.chat.completions.calls == [16000, 16000, 32000]


def test_partial_truncation_with_reasoning_still_escalates():
    # Non-empty truncated content means the model was writing a real answer
    # that did not fit — a bigger budget is the right fix there.
    llm = _make_llm([
        ('{"ok": tr', "length"),
        ('{"ok": true}', "stop"),
    ], reasoning={"effort": "high"})
    assert _call(llm) == {"ok": True}
    completions = llm.client.chat.completions
    assert completions.calls == [16000, 32000]
    assert completions.kwargs[1].get("extra_body") == {"reasoning": {"effort": "high"}}


def test_reasoning_and_response_format_are_never_combined():
    # Anthropic-style providers implement the schema format as a FORCED tool
    # call, which cannot coexist with extended thinking — sending both yields
    # empty assistant messages. Reasoning wins; the schema stays in messages.
    llm = _make_llm([('{"ok": 1}', "stop")], reasoning={"max_tokens": 8000})
    assert _call(llm) == {"ok": 1}
    kwargs = llm.client.chat.completions.kwargs[0]
    assert "response_format" not in kwargs
    assert kwargs["extra_body"] == {"reasoning": {"max_tokens": 8000}}


def test_explicitly_disabled_reasoning_still_sends_response_format():
    llm = _make_llm([('{"ok": 1}', "stop")], reasoning={"enabled": False})
    assert _call(llm) == {"ok": 1}
    assert "response_format" in llm.client.chat.completions.kwargs[0]


def test_json_payload_in_tool_calls_is_used_when_content_is_empty():
    # Some providers return the schema-constrained JSON as a tool call with an
    # empty content field — that is a complete response, not an empty one.
    resp = _Resp("", "stop")
    resp.choices[0].message.tool_calls = [
        SimpleNamespace(function=SimpleNamespace(arguments='{"ok": 1}')),
    ]
    llm = _make_llm([resp])
    assert _call(llm) == {"ok": 1}
    assert llm.client.chat.completions.calls == [16000]


def test_persistent_empty_with_reasoning_disables_reasoning_then_retries():
    # With reasoning active no response_format is sent, so the ladder is:
    # 1) disable reasoning once, 2) plain transient retries.
    llm = _make_llm([
        ("", "stop"),
        ("", "stop"),
        ('{"ok": true}', "stop"),
    ], reasoning={"max_tokens": 8000})
    assert _call(llm) == {"ok": True}
    kwargs = llm.client.chat.completions.kwargs
    assert all("response_format" not in k for k in kwargs)
    assert kwargs[1]["extra_body"] == {"reasoning": {"enabled": False}}
    assert kwargs[2]["extra_body"] == {"reasoning": {"enabled": False}}


def test_escalation_cap_bounds_truncation_escalation_per_call():
    # A plan-phase call must not climb to the instance-wide 64K ceiling.
    llm = _make_llm([(None, "length")] * 5)
    with pytest.raises(RuntimeError, match="cap of 8000"):
        _call(llm, max_tokens=4000, escalation_cap=8000)
    assert llm.client.chat.completions.calls == [4000, 8000]


def test_whitespace_only_response_is_treated_as_empty():
    llm = _make_llm([
        ("   \n\t ", "stop"),
        ('{"ok": 1}', "stop"),
    ], reasoning={"max_tokens": 8000})
    assert _call(llm) == {"ok": 1}


def test_empty_response_without_reasoning_drops_format_then_succeeds():
    # No reasoning to disable: the first varied retry drops the JSON
    # response_format (some providers return empty content when the
    # schema-constrained format is active).
    llm = _make_llm([
        ("", "stop"),
        ('{"ok": true}', "stop"),
    ])
    result = _call(llm)
    assert result == {"ok": True}
    assert llm.client.chat.completions.calls == [16000, 16000]
    assert "response_format" in llm.client.chat.completions.kwargs[0]
    assert "response_format" not in llm.client.chat.completions.kwargs[1]


def test_format_drop_success_disables_response_format_for_later_calls():
    # Empty with response_format, fine without it: the (model, label) pair is
    # memoized so the next call skips the guaranteed-dead format-on first try.
    llm = _make_llm([
        ("", "stop"),
        ('{"ok": 1}', "stop"),
        ('{"ok": 2}', "stop"),
    ])
    assert _call(llm) == {"ok": 1}
    assert _call(llm) == {"ok": 2}
    kwargs = llm.client.chat.completions.kwargs
    assert "response_format" in kwargs[0]
    assert "response_format" not in kwargs[1]
    assert "response_format" not in kwargs[2]
    assert len(kwargs) == 3  # the second request needed no empty+retry pair


def test_first_try_success_does_not_memoize_format_as_broken():
    llm = _make_llm([
        ('{"ok": 1}', "stop"),
        ('{"ok": 2}', "stop"),
    ])
    assert _call(llm) == {"ok": 1}
    assert _call(llm) == {"ok": 2}
    kwargs = llm.client.chat.completions.kwargs
    assert "response_format" in kwargs[0]
    assert "response_format" in kwargs[1]


def test_every_response_is_logged_verbatim_to_the_attached_run_log(tmp_path):
    from agentic_bench_gen.logio import console as shared_console

    log = tmp_path / "generation.log"
    shared_console.attach_log_file(log)
    try:
        llm = _make_llm([
            ("", "stop"),                                   # empty attempt
            ('{"ok": true, "note": "[TEST] PASS"}', "stop"),
        ])
        assert _call(llm) == {"ok": True, "note": "[TEST] PASS"}
    finally:
        shared_console.detach_log_file()
    text = log.read_text()
    assert "<EMPTY CONTENT>" in text                        # failed attempt recorded too
    assert '{"ok": true, "note": "[TEST] PASS"}' in text    # raw response, markup intact
    assert "===== response [s]" in text                     # call metadata header


def test_persistent_empty_response_eventually_raises():
    llm = _make_llm([("", "stop")] * 6)
    with pytest.raises(RuntimeError, match="Empty content"):
        _call(llm)


def test_close_unbalanced_json_appends_missing_closers():
    from agentic_bench_gen.llm import _close_unbalanced_json

    assert _close_unbalanced_json('{"a": [1, 2') == '{"a": [1, 2]}'
    assert _close_unbalanced_json('{"a": 1') == '{"a": 1}'
    # Balanced, mid-string, or mismatched tails are not salvageable.
    assert _close_unbalanced_json('{"a": 1}') is None
    assert _close_unbalanced_json('{"a": "unterminated') is None
    assert _close_unbalanced_json('{"a": [}') is None
    # Braces inside strings must not confuse the scanner.
    assert _close_unbalanced_json('{"code": "int f() { return 1; }"') == '{"code": "int f() { return 1; }"}'


def test_stop_response_missing_final_brace_is_salvaged_without_retry():
    # Regression: the mutator emitted complete JSON minus the trailing '}' with
    # finish_reason='stop'; the brace heuristic then misdiagnosed it as a
    # provider-side cut and burned a full retry.
    content = '{"mutants": [{"mutant_id": "m1", "files": [{"path": "a.c", "content": "int f() {"}]}]'
    llm = _make_llm([(content, "stop", _usage())])
    result = _call(llm)
    assert result["mutants"][0]["mutant_id"] == "m1"
    assert len(llm.client.chat.completions.calls) == 1
