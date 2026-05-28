import pytest
from hls_bench_agentic.ast_analyzer import analyze_source
from hls_bench_agentic.security_verifier import verify, SUPPORTED_DOMAINS

_SIDE_CHANNEL_SECURE = """
#include <stdint.h>
uint8_t compare_token(const uint8_t *a, const uint8_t *b) {
    #pragma HLS pipeline
    #pragma HLS loop_bound 16
    uint8_t diff = 0;
    for (int i = 0; i < 16; i++) {
        diff |= (a[i] ^ b[i]);
    }
    return diff == 0;
}
"""

_SIDE_CHANNEL_INSECURE = """
#include <stdint.h>
uint8_t compare_token(const uint8_t *a, const uint8_t *b) {
    for (int i = 0; i < 16; i++) {
        if (a[i] != b[i]) return 0;
    }
    return 1;
}
"""

_ACCESS_CONTROL_SECURE = """
#include <stdint.h>
static int check_privilege(uint8_t level, uint8_t required) {
    return level >= required;
}
uint32_t sec_config_reg(uint32_t addr, uint32_t wdata, uint8_t write_en,
                        uint8_t privilege_level) {
    uint32_t rdata = 0;
    if (addr == 3) {
        if (!check_privilege(privilege_level, 3)) {
            return 0;
        }
    }
    if (write_en) {
        // write
    }
    return rdata;
}
"""

_RESOURCE_ISOLATION_SECURE = """
#include <stdint.h>
#include <string.h>
static uint8_t domain_a[32];
static uint8_t domain_b[32];
void zeroize_buffer(uint8_t *buf, int len) {
    memset(buf, 0, len);
}
void transfer(uint8_t *out, int len) {
    zeroize_buffer(domain_a, 32);
    for (int i = 0; i < len; i++) out[i] = domain_b[i];
}
"""

def _spec(domain: str, difficulty: str = "easy") -> dict:
    return {
        "hidden_spec": {
            "security_domain": domain,
            "difficulty": difficulty,
            "forbidden_patterns": ["early return", "return 0 inside loop"],
            "security_requirements": [],
        }
    }


def test_supported_domains():
    assert "side_channel" in SUPPORTED_DOMAINS
    assert "access_control" in SUPPORTED_DOMAINS
    assert "information_flow_tracking" in SUPPORTED_DOMAINS
    assert "resource_isolation" in SUPPORTED_DOMAINS


def test_side_channel_secure_scores_higher():
    r_secure   = analyze_source(_SIDE_CHANNEL_SECURE)
    r_insecure = analyze_source(_SIDE_CHANNEL_INSECURE)
    secure_score   = verify(r_secure,   _spec("side_channel")).total_score
    insecure_score = verify(r_insecure, _spec("side_channel")).total_score
    assert secure_score > insecure_score


def test_access_control_secure_scores_above_zero():
    r = analyze_source(_ACCESS_CONTROL_SECURE)
    report = verify(r, _spec("access_control"))
    assert report.total_score > 0.0
    assert report.domain == "access_control"


def test_resource_isolation_detects_zeroization():
    r = analyze_source(_RESOURCE_ISOLATION_SECURE)
    report = verify(r, _spec("resource_isolation"))
    assert report.total_score > 0.0


def test_report_has_property_scores():
    r = analyze_source(_SIDE_CHANNEL_SECURE)
    report = verify(r, _spec("side_channel"))
    assert len(report.property_scores) > 0
    for ps in report.property_scores:
        assert 0.0 <= ps.score <= ps.max_score


def test_generic_domain_works():
    r = analyze_source(_SIDE_CHANNEL_SECURE)
    spec = {
        "hidden_spec": {
            "security_domain": "generic",
            "difficulty": "easy",
            "forbidden_patterns": ["early return", "printf"],
            "security_requirements": [],
        }
    }
    report = verify(r, spec)
    assert 0.0 <= report.total_score <= 1.0