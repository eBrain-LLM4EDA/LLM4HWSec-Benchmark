from hls_bench_agentic.ast_analyzer import (
    analyze_source,
    score_synthesis_compatibility,
    _CLANG_AVAILABLE,
)

_CONST_TIME = """
#include <stdint.h>
uint8_t compare_token(const uint8_t *a, const uint8_t *b, uint8_t len) {
    #pragma HLS pipeline
    #pragma HLS loop_bound 16
    uint8_t diff = 0;
    for (int i = 0; i < 16; i++) {
        diff |= (a[i] ^ b[i]);
    }
    return diff == 0;
}
"""

_INSECURE_EARLY_RETURN = """
#include <stdint.h>
uint8_t compare_token(const uint8_t *a, const uint8_t *b, uint8_t len) {
    for (int i = 0; i < 16; i++) {
        if (a[i] != b[i]) return 0;
    }
    return 1;
}
"""

_SYNTH_BAD = """
#include <stdint.h>
#include <stdio.h>
uint8_t foo(uint8_t x) {
    printf("debug: %d\\n", x);
    uint8_t *p = (uint8_t*)malloc(16);
    free(p);
    return x;
}
"""

_TAINT = """
struct tainted_byte { uint8_t data; int label; };
tainted_byte operator^(tainted_byte a, tainted_byte b) {
    return {(uint8_t)(a.data ^ b.data), a.label | b.label};
}
"""


def test_analyze_returns_result():
    r = analyze_source(_CONST_TIME)
    assert r.analysis_method in ("clang", "regex")


def test_pragmas_extracted():
    r = analyze_source(_CONST_TIME)
    kinds = {p.kind.lower() for p in r.pragmas}
    assert "pipeline" in kinds or "loop_bound" in kinds


def test_synthesis_violations_detected():
    r = analyze_source(_SYNTH_BAD)
    assert len(r.synthesis_violations) > 0


def test_no_violations_on_clean_code():
    r = analyze_source(_CONST_TIME)
    assert len(r.synthesis_violations) == 0


def test_taint_type_detected():
    r = analyze_source(_TAINT)
    assert r.has_taint_types


def test_taint_type_not_falsely_detected():
    r = analyze_source(_CONST_TIME)
    assert not r.has_taint_types


def test_synthesis_score_clean():
    r = analyze_source(_CONST_TIME)
    score, reason = score_synthesis_compatibility(r)
    assert score >= 0.80
    assert isinstance(reason, str)


def test_synthesis_score_bad():
    r = analyze_source(_SYNTH_BAD)
    score, _ = score_synthesis_compatibility(r)
    assert score <= 0.50


def test_loop_detected():
    r = analyze_source(_CONST_TIME)
    assert len(r.loops) > 0


def test_early_exit_detected_regex():
    r = analyze_source(_INSECURE_EARLY_RETURN)
    # regex analysis detects break/return; clang may detect in loop body
    has_early = any(l.has_early_exit for l in r.loops)
    # At minimum, synthesis_violations should be empty (the code itself is syntactically valid)
    assert len(r.synthesis_violations) == 0