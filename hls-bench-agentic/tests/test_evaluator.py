from hls_bench_agentic.evaluator import _clamp_score, _collect_source_files
from hls_bench_agentic.workspace import Workspace


def test_evaluation_candidate_can_be_normalized_to_canonical_impl(tmp_path):
    candidate_bundle = {
        "files": [
            {"path": "compare_token.c", "content": "#include \"compare_token.h\"\nint compare_token(void) { return 1; }\n"},
            {"path": "compare_token.h", "content": "int compare_token(void);\n"},
        ]
    }
    out = Workspace(tmp_path)
    out.write_file_bundle(candidate_bundle, base_dir=".")
    out.normalize_hls_implementation(candidate_bundle, top_function="compare_token")

    assert (tmp_path / "src" / "impl.cpp").exists()
    assert 'extern "C"' in (tmp_path / "src" / "compare_token.h").read_text()
    assert _collect_source_files(candidate_bundle)["compare_token.c"].startswith("#include")


def test_clamp_score_bounds_llm_scores_after_schema_parse():
    assert _clamp_score(1.5) == 1.0
    assert _clamp_score(-0.25) == 0.0
    assert _clamp_score("0.4") == 0.4
    assert _clamp_score("not-a-number") is None
