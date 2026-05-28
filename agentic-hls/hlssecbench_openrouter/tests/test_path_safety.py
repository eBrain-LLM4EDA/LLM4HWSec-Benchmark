from hlssecbench_openrouter.workspace import Workspace
import pytest


def test_workspace_rejects_parent_escape(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(ValueError):
        ws.path("../escape.txt")
