from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from .agents import AgentConfig, JsonAgent
from .domains import profile_as_prompt_context
from .llm import OpenRouterLLM
from .utils import read_yaml, slugify
from .validator import quality_report, validate_benchmark_case
from .workspace import Workspace

console = Console()


def load_agents(llm: OpenRouterLLM, agents_cfg_path: Path, defaults: dict[str, Any]) -> dict[str, JsonAgent]:
    raw = read_yaml(agents_cfg_path)
    cfg_defaults = raw.get("defaults", defaults)
    project_root = agents_cfg_path.parent.parent
    agents: dict[str, JsonAgent] = {}
    for name, spec in raw["agents"].items():
        agents[name] = JsonAgent(
            llm,
            AgentConfig(
                name=name,
                model=spec["model"],
                prompt_path=(project_root / spec["prompt"]).resolve(),
                schema_path=(project_root / spec["schema"]).resolve(),
                temperature=float(spec.get("temperature", cfg_defaults.get("temperature", 0.1))),
                max_tokens=int(spec.get("max_tokens", cfg_defaults.get("max_tokens", 16000))),
            ),
        )
    return agents


def _unique_workspace(out_root: Path, task_id: str) -> Path:
    candidate = out_root / task_id
    if not candidate.exists():
        return candidate
    idx = 1
    while True:
        candidate = out_root / f"{task_id}_gen{idx:03d}"
        if not candidate.exists():
            return candidate
        idx += 1


class BenchGenOrchestrator:
    """Domain-modular agentic benchmark generation pipeline."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).resolve()
        self.pipeline_cfg = read_yaml(self.config_path)
        openrouter_cfg = self.pipeline_cfg.get("openrouter", {})
        self.llm = OpenRouterLLM.from_env(
            base_url=openrouter_cfg.get("base_url", "https://openrouter.ai/api/v1"),
            timeout_seconds=float(openrouter_cfg.get("timeout_seconds", 120)),
            max_retries=int(openrouter_cfg.get("max_retries", 3)),
        )
        agents_cfg_path = (self.config_path.parent.parent / self.pipeline_cfg["agents_config"]).resolve()
        self.agents = load_agents(self.llm, agents_cfg_path, self.pipeline_cfg.get("defaults", {}))

    def generate(self, seed_path: str | Path, out_dir: str | Path) -> list[Path]:
        seeds = read_yaml(seed_path)
        out_root = Path(out_dir).resolve()
        out_root.mkdir(parents=True, exist_ok=True)
        max_repair = int(self.pipeline_cfg.get("pipeline", {}).get("max_repair_rounds", 2))
        expand = bool(self.pipeline_cfg.get("pipeline", {}).get("expand_seeds", True))

        generated: list[Path] = []
        for raw_seed in seeds:
            ideas = self._expand_seed(raw_seed) if expand and "idea_generator" in self.agents else [raw_seed]
            for idea in ideas:
                generated.append(self._generate_one(idea, out_root, max_repair))
        return generated

    def _expand_seed(self, raw_seed: dict[str, Any]) -> list[dict[str, Any]]:
        domain_context = profile_as_prompt_context(str(raw_seed.get("domain_id", "hls_security_codegen")))
        console.print(f"[bold cyan]IdeaGenerator:[/bold cyan] expanding {raw_seed.get('seed_id', 'seed')}")
        try:
            bundle = self.agents["idea_generator"].run({
                "seed_yaml": raw_seed,
                "domain_profile_json": domain_context,
            })
            return bundle.get("ideas", [raw_seed])
        except Exception as exc:
            console.print(f"[yellow]IdeaGenerator failed ({exc}); using raw seed.[/yellow]")
            return [raw_seed]

    def _generate_one(self, idea: dict[str, Any], out_root: Path, max_repair: int) -> Path:
        repair_notes = ""
        task_spec: dict[str, Any] | None = None
        artifact_bundle: dict[str, Any] | None = None
        expert_bundle: dict[str, Any] | None = None
        tester_bundle: dict[str, Any] | None = None
        mutation_bundle: dict[str, Any] | None = None
        analyzer_report: dict[str, Any] | None = None
        arbiter_decision: dict[str, Any] | None = None
        ws_path: Path | None = None
        generate_mutants = bool(self.pipeline_cfg.get("pipeline", {}).get("generate_mutants", True))

        for round_idx in range(max_repair + 1):
            artifact_to_fix = arbiter_decision["artifact_to_revise"] if arbiter_decision else "none"
            domain_id = str(idea.get("domain_id", "hls_security_codegen"))
            domain_context = profile_as_prompt_context(domain_id)

            if round_idx == 0 or artifact_to_fix == "specification":
                console.print(f"[bold]Architect (round {round_idx}):[/bold] {domain_id}")
                task_spec = self.agents["architect"].run({
                    "seed_yaml": idea,
                    "domain_profile_json": domain_context,
                    "repair_notes": repair_notes,
                })
                task_spec = _normalize_task_spec(task_spec, idea, domain_context)

            task_id = str(task_spec["task_id"])
            if ws_path is None:
                ws_path = _unique_workspace(out_root, task_id)
            ws = Workspace(ws_path)
            ws.write_json("spec/task_spec.json", task_spec)
            ws.write_json("spec/public_spec.json", task_spec["public_spec"])
            ws.write_json("spec/hidden_spec.json", task_spec["hidden_spec"])

            if round_idx == 0 or artifact_to_fix in {"specification", "case_artifacts"}:
                console.print(f"[bold]ArtifactBuilder (round {round_idx}):[/bold] {task_id}")
                artifact_bundle = self.agents["artifact_builder"].run({
                    "task_spec_json": task_spec,
                    "domain_profile_json": domain_context,
                    "repair_notes": repair_notes,
                })
                ws.write_json("artifacts/artifact_bundle.json", artifact_bundle)
                ws.write_file_bundle(artifact_bundle)

            if round_idx == 0 or artifact_to_fix in {"specification", "case_artifacts"}:
                console.print(f"[bold]Expert (round {round_idx}):[/bold] golden reference for {task_id}")
                expert_bundle = self.agents["expert"].run({
                    "task_spec_json": task_spec,
                    "domain_profile_json": domain_context,
                    "repair_notes": repair_notes,
                })
                ws.write_json("expert/expert_bundle.json", expert_bundle)
                ws.write_file_bundle(expert_bundle)

            if round_idx == 0 or artifact_to_fix in {"specification", "case_artifacts", "evaluation_framework"}:
                console.print(f"[bold]Tester (round {round_idx}):[/bold] requirement harnesses for {task_id}")
                tester_bundle = self.agents["tester"].run({
                    "task_spec_json": task_spec,
                    "domain_profile_json": domain_context,
                    "repair_notes": repair_notes,
                })
                ws.write_json("tests/tester_bundle.json", tester_bundle)
                ws.write_file_bundle(tester_bundle)

            if generate_mutants and "mutator" in self.agents and (round_idx == 0 or artifact_to_fix in {"case_artifacts", "evaluation_framework"}):
                console.print(f"[bold]Mutator (round {round_idx}):[/bold] quality mutants for {task_id}")
                mutation_bundle = {"mutants": []}
                mutants_target = int(self.pipeline_cfg.get("pipeline", {}).get("mutants_per_case", 5))
                for m_idx in range(mutants_target):
                    console.print(f"  -> generating mutant {m_idx + 1}/{mutants_target}...")
                    try:
                        m_bundle = self.agents["mutator"].run({
                            "task_spec_json": task_spec,
                            "artifact_bundle_json": artifact_bundle,
                            "expert_bundle_json": expert_bundle,
                            "tester_bundle_json": tester_bundle,
                            "previous_mutations": [
                                {
                                    "mutant_id": m.get("mutant_id"),
                                    "operator": m.get("operator"),
                                    "target_requirement_id": m.get("target_requirement_id"),
                                }
                                for m in mutation_bundle["mutants"]
                            ],
                        })
                        if "mutants" in m_bundle:
                            mutation_bundle["mutants"].extend(m_bundle["mutants"])
                    except Exception as exc:
                        console.print(f"  -> [yellow]mutant generation failed:[/yellow] {exc}")
                        
                ws.write_json("mutants/mutation_bundle.json", mutation_bundle)

            validation = validate_benchmark_case(task_spec, artifact_bundle, tester_bundle, expert_bundle, mutation_bundle, ws)
            ws.write_json("reports/validation_report.json", validation)

            console.print(f"[bold]Analyzer (round {round_idx}):[/bold] {task_id}")
            analyzer_report = self.agents["analyzer"].run({
                "task_spec_json": task_spec,
                "artifact_bundle_json": artifact_bundle,
                "tester_bundle_json": tester_bundle,
                "validation_report_json": validation,
            })
            ws.write_json("reports/analyzer_report.json", analyzer_report)

            console.print(f"[bold]Arbiter (round {round_idx}):[/bold] {task_id}")
            arbiter_decision = self.agents["arbiter"].run({
                "task_spec_json": task_spec,
                "analyzer_report_json": analyzer_report,
                "validation_report_json": validation,
            })
            ws.write_json(f"reports/arbiter_decision_r{round_idx}.json", arbiter_decision)

            if arbiter_decision.get("retain_case", False):
                break
            repair_notes = json.dumps(arbiter_decision, indent=2, sort_keys=True)

        ws.write_json("reports/quality_report.json", quality_report(
            ws_read_json(ws, "reports/validation_report.json"),
            analyzer_report or {"overall_status": "fail", "issues": []},
            min_coverage_score=float(self.pipeline_cfg.get("validation", {}).get("min_coverage_score", 0.80)),
            min_mutation_score=float(self.pipeline_cfg.get("validation", {}).get("min_mutation_score", 0.50)),
        ))
        return ws.root


def ws_read_json(ws: Workspace, rel: str) -> dict[str, Any]:
    return json.loads(ws.path(rel).read_text(encoding="utf-8"))


def _normalize_task_spec(raw: dict[str, Any], seed: dict[str, Any], domain_context: dict[str, Any]) -> dict[str, Any]:
    domain_id = str(raw.get("domain_id") or seed.get("domain_id") or domain_context["domain_id"])
    task_id = slugify(str(raw.get("task_id") or seed.get("seed_id") or f"{domain_id}_case"))
    public = raw.get("public_spec") if isinstance(raw.get("public_spec"), dict) else {}
    hidden = raw.get("hidden_spec") if isinstance(raw.get("hidden_spec"), dict) else {}
    evaluation = raw.get("evaluation") if isinstance(raw.get("evaluation"), dict) else {}
    metrics = evaluation.get("metrics") or [
        {"name": metric, "direction": "maximize", "description": metric.replace("_", " ")}
        for metric in domain_context["default_metrics"]
    ]
    return {
        "task_id": task_id,
        "domain_id": domain_id,
        "title": str(raw.get("title") or seed.get("title") or domain_context["title"]),
        "public_spec": {
            "objective": public.get("objective") or seed.get("objective") or domain_context["example_tasks"][0],
            "input_artifacts": public.get("input_artifacts") or domain_context["input_artifacts"],
            "expected_outputs": public.get("expected_outputs") or domain_context["output_artifacts"],
            "interface": public.get("interface") or seed.get("interface") or "",
            "functional_requirements": public.get("functional_requirements") or seed.get("functional_requirements") or [
                {"id": "FR1", "requirement": "The submitted artifact satisfies the public objective and interface contract."}
            ],
            "constraints": public.get("constraints") or seed.get("constraints") or [],
            "response_format": public.get("response_format") or "JSON or Markdown report plus generated artifacts as requested.",
        },
        "hidden_spec": {
            "ground_truth": hidden.get("ground_truth") or seed.get("ground_truth") or "Evaluator-specific ground truth to be generated with the case artifacts.",
            "threat_model": hidden.get("threat_model") or seed.get("threat_model") or "",
            "cwe_ids": hidden.get("cwe_ids") or seed.get("cwe_ids") or [],
            "security_requirements": hidden.get("security_requirements") or seed.get("security_requirements") or [
                {"id": "SR1", "requirement": "The submitted artifact satisfies the hidden domain-specific security property.", "detection_strategy": "Requirement-level private harness."}
            ],
            "acceptance_criteria": hidden.get("acceptance_criteria") or seed.get("acceptance_criteria") or [],
        },
        "evaluation": {
            "metrics": metrics,
            "baselines": evaluation.get("baselines") or domain_context["baseline_sources"],
        },
    }
