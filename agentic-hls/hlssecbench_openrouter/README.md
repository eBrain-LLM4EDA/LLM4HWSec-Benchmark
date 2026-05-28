# HLSSecBench Agentic Generator with OpenRouter

This is a runnable scaffold for adapting HardSecBench-style agentic testbench generation to an HLS security benchmark.

It includes:

- OpenRouter client using the OpenAI-compatible Chat Completions API.
- Agent prompts for Architect, Expert, Tester, Security Analyzer, Arbiter, Mutator, and Target Model.
- JSON schemas for structured LLM outputs.
- YAML configuration files for models, agents, pipeline gates, and HLS tool commands.
- A Python orchestration pipeline that generates HLS tasks, secure reference implementations, testbenches, mutants, and reports.
- Safe-by-default execution: generated code is written to disk, but HLS commands are not run unless `allow_execution: true`.

## Install

```bash
cd hlssecbench_openrouter
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Set your OpenRouter key:

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

Slow or stalled provider calls are bounded by `openrouter.timeout_seconds` in
the pipeline config. Set `OPENROUTER_TIMEOUT_SECONDS` or increase that YAML
value if you intentionally want to wait longer for large generations. Retries
default to zero; use `openrouter.max_retries` or `OPENROUTER_MAX_RETRIES` if
you prefer retrying transient provider failures.

## Generate benchmark artifacts

```bash
hlssecbench generate \
  --seed examples/seeds.yaml \
  --out runs/demo \
  --config config/pipeline.yaml
```

By default this will **not** run any HLS tools or generated code (`allow_execution: false`).

If the Analyzer/Arbiter finds a repairable issue, the generator will use
`pipeline.max_repair_rounds` to automatically retry supported artifacts.
Automatic repair is currently implemented for `tester`, `expert`, and
`tool_config` revisions. `tool_config` repairs are routed back through the
Tester because the generated test scripts own the tool invocation behavior.
Other Arbiter targets are recorded in `reports/repair_history.json` for manual
follow-up.

### Running with PandA-Bambu via Docker (recommended)

The project ships a pre-configured PandA-Bambu container based on the official
`bambuhls/bambu:latest` image.

**1. Build the image** (one-time, from the `hlssecbench_openrouter/` directory):

```bash
docker compose build bambu-runner
```

**2. Generate with Docker execution enabled:**

```bash
hlssecbench generate \
  --seed examples/seeds.yaml \
  --out runs/demo \
  --config config/pipeline.docker.yaml
```

`config/pipeline.docker.yaml` sets `allow_execution: true` and routes every
tool step through the `hlssecbench-openrouter-bambu:latest` container.

**3. Run a single step manually for debugging:**

```bash
HLS_BENCH_WORKSPACE=$(pwd)/runs/demo/my_task_id \
  docker compose run --rm bambu-runner bash tests/run_synth.sh
```

> **Security note:** generated code from an LLM is executed inside the container.
> The compose file sets `network_mode: none` to block outbound network access.

## Evaluate a target model

After generating a task:

```bash
hlssecbench evaluate \
  --task runs/demo/hls_sec_demo_001 \
  --model openai/gpt-5.2 \
  --out runs/evals/demo_model
```

The target model sees only the public spec.

## Project layout

```text
config/
  agents.yaml
  pipeline.yaml
prompts/
  architect.md
  expert.md
  tester.md
  security_analyzer.md
  arbiter.md
  mutator.md
  target_model.md
schemas/
  task_spec.schema.json
  file_bundle.schema.json
  test_bundle.schema.json
  analyzer_report.schema.json
  arbiter_decision.schema.json
  mutation_bundle.schema.json
examples/
  seeds.yaml
src/hlssecbench_openrouter/
  cli.py
  llm.py
  agents.py
  orchestrator.py
  evaluator.py
  runner.py
  workspace.py
  schemas.py
  utils.py
```

## Notes

This is a research scaffold, not a finished benchmark. For publication-quality benchmark generation, add:

- Formal security checks where possible.
- Manual audit of retained tasks.
- HLS-tool-specific report parsers.
- RTL simulation integration.
- Side-channel analysis or leakage-proxy tools.
- CWE/HLS-specific mutation operators.
