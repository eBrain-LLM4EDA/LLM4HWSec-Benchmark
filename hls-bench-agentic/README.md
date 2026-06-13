# HLS Bench Agentic

Agentic HLS security benchmark generator and evaluator.

## Generate Benchmarks

The default pipeline is safe-by-default: generated code and shell scripts are
written to disk, but tool execution is disabled unless you opt into it.

```bash
cd hls-bench-agentic
hlsbench generate --seed examples/cwe_seeds.yaml --out runs/demo --config config/pipeline.yaml
```

OpenRouter calls are bounded by `openrouter.timeout_seconds` and
`openrouter.max_retries` in the pipeline config. You can override them with
`OPENROUTER_TIMEOUT_SECONDS` and `OPENROUTER_MAX_RETRIES`.

## Run Bambu Tests With Docker

The generated benchmark test scripts expect `bambu` for synthesis and co-simulation. To avoid host-specific installs, use the shared Docker image built by `agentic-hls`.

Build the shared image once:

```bash
cd ../agentic-hls/hlssecbench_openrouter
docker compose build bambu-runner
```

Build and run all tests for the demo workspace:

```bash
cd hls-bench-agentic
./scripts/run-bambu-tests.sh
```

Run all tests for another generated workspace:

```bash
./scripts/run-bambu-tests.sh runs/demo/hls_cwe385_const_time_compare
```

Run only one step:

```bash
./scripts/run-bambu-tests.sh runs/demo/hls_cwe385_const_time_compare "bash tests/run_synth.sh"
```

Equivalent direct Compose usage:

```bash
cd hls-bench-agentic
export HLS_BENCH_WORKSPACE="$PWD/runs/demo/hls_cwe385_const_time_compare"
export HLS_BENCH_TEST_COMMAND="bash tests/run_csim.sh && bash tests/run_synth.sh"
docker compose run --rm bambu-tests
```

The compose service uses `hlssecbench-openrouter-bambu:latest` by default and mounts the directory named by `HLS_BENCH_WORKSPACE` at `/workspace`, so it can run any generated task workspace. Test outputs such as `synth_out/`, `cosim_out/`, and logs are written back into that mounted workspace on the host.

To use a different local image, set `HLS_BENCH_BAMBU_IMAGE`.

## Use Docker During Generation

The normal pipeline config assumes generated scripts run on the host. To run tool steps inside the same Bambu image during generation, build the image first and use the Docker config:

```bash
cd hls-bench-agentic
hlsbench generate --seed examples/cwe_seeds.yaml --out runs/demo --config config/pipeline.docker.yaml
```

This uses Docker for every configured execution step, including `run_csim.sh`, `run_synth.sh`, `run_cosim.sh`, and `run_rtl_security.sh`.

Generated task workspaces are never overwritten. If a generated `task_id` already exists under the output directory, the next run is written to a suffixed folder such as `hls_cwe385_const_time_compare_gen001`.
