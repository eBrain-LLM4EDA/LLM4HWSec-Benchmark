import pytest
import subprocess

from hls_bench_agentic.workspace import Workspace


def test_path_rejects_parent_escape(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(ValueError, match="escapes workspace"):
        ws.path("../escape.txt")


def test_path_rejects_absolute(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(ValueError, match="escapes workspace"):
        ws.path("/etc/passwd")


def test_path_allows_nested(tmp_path):
    ws = Workspace(tmp_path)
    p = ws.path("subdir/file.txt")
    assert p.is_relative_to(tmp_path)


def test_write_file_bundle_rejects_absolute_path(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(ValueError, match="Absolute path"):
        ws.write_file_bundle({"files": [{"path": "/etc/passwd", "content": "x"}]})


def test_write_file_bundle_rejects_traversal(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(ValueError, match="escapes workspace"):
        ws.write_file_bundle({"files": [{"path": "../escape.txt", "content": "x"}]})


def test_write_file_bundle_creates_files(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_file_bundle({
        "files": [
            {"path": "src/main.cpp", "content": "int main() {}"},
            {"path": "tests/run_csim.sh", "content": "#!/bin/bash\necho done"},
        ]
    })
    assert (tmp_path / "src" / "main.cpp").read_text() == "int main() {}"
    assert (tmp_path / "tests" / "run_csim.sh").read_text() == "#!/bin/bash\necho done"


def test_write_file_bundle_makes_sh_executable(tmp_path):
    import stat
    ws = Workspace(tmp_path)
    ws.write_file_bundle({"files": [{"path": "run.sh", "content": "#!/bin/bash"}]})
    mode = (tmp_path / "run.sh").stat().st_mode
    assert mode & stat.S_IXUSR


def test_normalize_hls_implementation_creates_canonical_impl(tmp_path):
    ws = Workspace(tmp_path)
    ws.normalize_hls_implementation({
        "files": [
            {"path": "compare_token.c", "content": "#include \"compare_token.h\"\nint compare_token(void) { return 1; }\n"},
            {"path": "compare_token.h", "content": "int compare_token(void);\n"},
        ]
    })

    assert (tmp_path / "src" / "impl.cpp").read_text() == "#include \"compare_token.h\"\nint compare_token(void) { return 1; }\n"
    assert 'extern "C"' in (tmp_path / "src" / "compare_token.h").read_text()
    assert "int compare_token(void);" in (tmp_path / "src" / "compare_token.h").read_text()


def test_normalize_hls_implementation_rejects_bundle_without_source(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(ValueError, match="No C/C\\+\\+ implementation"):
        ws.normalize_hls_implementation({"files": [{"path": "compare_token.h", "content": "int f(void);"}]})


def test_normalize_hls_implementation_prefers_top_function(tmp_path):
    ws = Workspace(tmp_path)
    ws.normalize_hls_implementation(
        {
            "files": [
                {"path": "helper.c", "content": "int helper(void) { return 0; }\n"},
                {"path": "compare_token.c", "content": "int compare_token(void) { return 1; }\n"},
            ]
        },
        top_function="compare_token",
    )

    assert (tmp_path / "src" / "impl.cpp").read_text() == "int compare_token(void) { return 1; }\n"


def test_normalized_header_supports_extern_c_testbench_linkage(tmp_path):
    ws = Workspace(tmp_path)
    ws.normalize_hls_implementation({
        "files": [
            {"path": "compare_token.c", "content": "#include \"compare_token.h\"\nint compare_token(void) { return 1; }\n"},
            {"path": "compare_token.h", "content": "int compare_token(void);\n"},
        ]
    })
    (tmp_path / "tb.cpp").write_text(
        'extern "C" int compare_token(void);\n'
        "int main() { return compare_token() == 1 ? 0 : 1; }\n"
    )

    proc = subprocess.run(
        ["g++", "-std=c++11", "-I.", "tb.cpp", "src/impl.cpp", "-o", "tb"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    run = subprocess.run([str(tmp_path / "tb")], text=True, capture_output=True)
    assert run.returncode == 0
