# HLS Bench Agentic

Agentic HLS security benchmark generator and evaluator.

## Run Bambu Tests With Docker

The generated benchmark test scripts expect `bambu` for synthesis and co-simulation. To avoid host-specific installs, use the included Docker Compose runner.

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
docker compose build bambu-tests
docker compose run --rm bambu-tests
```

The image is built from `bambuhls/bambu:latest` and mounts the directory named by `HLS_BENCH_WORKSPACE` at `/workspace`, so it can run any generated task workspace. Test outputs such as `synth_out/`, `cosim_out/`, and logs are written back into that mounted workspace on the host.

## Use Docker During Generation

The normal pipeline config assumes generated scripts run on the host. To run tool steps inside the same Bambu image during generation, build the image first and use the Docker config:

```bash
cd hls-bench-agentic
docker compose build bambu-tests
hlsbench generate --seed examples/cwe_seeds.yaml --out runs/demo --config config/pipeline.docker.yaml
```

This uses Docker for every configured execution step, including `run_csim.sh`, `run_synth.sh`, `run_cosim.sh`, and `run_rtl_security.sh`.

Generated task workspaces are never overwritten. If a generated `task_id` already exists under the output directory, the next run is written to a suffixed folder such as `hls_cwe385_const_time_compare_gen001`.
