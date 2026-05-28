from __future__ import annotations

import json
import shutil
from pathlib import Path

from rich.console import Console

from .agents import AgentConfig, JsonAgent
from .llm import OpenRouterLLM
from .runner import ToolRunner, parse_execution_config
from .utils import read_json, read_text, read_yaml, write_json
from .workspace import Workspace


console = Console()


def evaluate_target_model(
    *,
    task_dir: str | Path,
    model: str,
    out_dir: str | Path,
    config_path: str | Path,
) -> Path:
    task_dir = Path(task_dir).resolve()
    config_path = Path(config_path).resolve()
    pipeline_cfg = read_yaml(config_path)
    agents_cfg = read_yaml((config_path.parent.parent / pipeline_cfg["agents_config"]).resolve())

    public_spec = read_json(task_dir / "spec" / "public_spec.json")
    prompt_path = (config_path.parent.parent / agents_cfg["agents"]["target_model"]["prompt"]).resolve()
    schema_path = (config_path.parent.parent / agents_cfg["agents"]["target_model"]["schema"]).resolve()

    openrouter_config = pipeline_cfg.get("openrouter", {})
    llm = OpenRouterLLM.from_env(
        base_url=openrouter_config.get("base_url", "https://openrouter.ai/api/v1"),
        timeout_seconds=float(openrouter_config.get("timeout_seconds", 120)),
        max_retries=int(openrouter_config.get("max_retries", 0)),
    )
    agent = JsonAgent(
        llm,
        AgentConfig(
            name="target_model",
            model=model,
            prompt_path=prompt_path,
            schema_path=schema_path,
            temperature=float(agents_cfg["agents"]["target_model"].get("temperature", 0.2)),
            max_tokens=int(agents_cfg.get("defaults", {}).get("max_tokens", 12000)),
        )
    )

    console.print(f"[bold]Generating target candidate with {model}[/bold]")
    candidate_bundle = agent.run({"public_spec_json": public_spec})

    out = Workspace(Path(out_dir).resolve() / task_dir.name / model.replace("/", "__").replace(":", "_"))
    out.write_json("candidate/candidate_bundle.json", candidate_bundle)
    out.write_file_bundle(candidate_bundle, base_dir=".")

    # Copy tests and specs from generated benchmark.
    shutil.copytree(task_dir / "tests", out.path("tests"), dirs_exist_ok=True)
    shutil.copytree(task_dir / "spec", out.path("spec"), dirs_exist_ok=True)

    runner = ToolRunner(parse_execution_config(pipeline_cfg))
    execution_results = runner.run_all(out.root)
    out.write_json("reports/evaluation_summary.json", {
        "task_id": task_dir.name,
        "model": model,
        "execution_results": execution_results,
        "note": "Target model saw only spec/public_spec.json. Hidden spec is copied only for local reporting; do not expose it during prompting.",
    })

    console.print(f"[green]Wrote evaluation workspace:[/green] {out.root}")
    return out.root
