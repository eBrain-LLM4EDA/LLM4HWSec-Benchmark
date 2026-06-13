import pytest

from agentic_bench_gen.workspace import Workspace


def test_workspace_rejects_path_escape(tmp_path):
    ws = Workspace(tmp_path)

    with pytest.raises(ValueError):
        ws.path("../escape")


def test_workspace_writes_bundle_and_marks_shell_executable(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_file_bundle({
        "files": [
            {"path": "inputs/a.v", "content": "module a; endmodule\n"},
            {"path": "evaluation/run.sh", "content": "#!/usr/bin/env bash\n"},
        ]
    })

    assert (tmp_path / "inputs" / "a.v").exists()
    assert (tmp_path / "evaluation" / "run.sh").stat().st_mode & 0o100

