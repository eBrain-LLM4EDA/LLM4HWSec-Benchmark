import json

from agentic_bench_gen.utils import write_json


def test_write_json_atomically_replaces_document_without_temp_files(tmp_path):
    path = tmp_path / "report.json"
    write_json(path, {"version": 1})
    write_json(path, {"version": 2, "complete": True})

    assert json.loads(path.read_text()) == {"version": 2, "complete": True}
    assert list(tmp_path.glob(".report.json.*.tmp")) == []
