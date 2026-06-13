from hls_bench_agentic.runner import CommandStep, ExecutionConfig, ToolRunner, parse_execution_config


def test_runner_classifies_not_run_marker_as_not_run():
    assert ToolRunner.classify_result(0, "[NOT_RUN] bambu not found\n", "") == "not_run"


def test_docker_wrapper_uses_resolved_workspace_and_platform(tmp_path):
    runner = ToolRunner(
        ExecutionConfig(
            allow_execution=True,
            timeout_seconds=1,
            docker_enabled=True,
            docker_image="hlssecbench-openrouter-bambu:latest",
            docker_platform="linux/amd64",
        )
    )

    command = runner._wrap_command(
        step=CommandStep(name="synth", command="bash tests/run_synth.sh"),
        workspace=tmp_path,
    )

    assert "--platform linux/amd64" in command
    assert f"{tmp_path}:/workspace" in command
    assert "$(pwd)" not in command


def test_pipeline_can_disable_cosim_step(tmp_path):
    config = parse_execution_config({
        "pipeline": {"enable_cosim": False},
        "execution": {
            "allow_execution": True,
            "timeout_seconds": 1,
            "steps": [
                {"name": "csim", "command": "true"},
                {"name": "cosim", "command": "false"},
            ],
        },
    })
    runner = ToolRunner(config)

    results = runner.run_all(tmp_path)
    steps = {step["name"]: step for step in results["steps"]}

    assert steps["csim"]["status"] == "pass"
    assert steps["cosim"]["status"] == "not_run"
    assert steps["cosim"]["enabled"] is False
