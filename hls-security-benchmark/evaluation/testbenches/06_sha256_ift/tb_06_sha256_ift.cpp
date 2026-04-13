/*
 * Testbench: 06_sha256_ift
 * Tests HMAC-SHA256 secure version (debug port removed).
 * Verifies deterministic output and different keys produce different MACs.
 */
#include <iostream>
#include <cstdlib>
#include "ap_int.h"
#include "hls_stream.h"

namespace secure {
    #include "/benchmark/examples/06_sha256_ift/reference_secure.cpp"
}

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "06_sha256_ift";

void report(const char* name, bool pass, const char* reason = "") {
    tests_total++;
    if (pass) { tests_passed++; std::cout << "TEST " << EXAMPLE_ID << " " << name << ": PASS\n"; }
    else { std::cout << "TEST " << EXAMPLE_ID << " " << name << ": FAIL " << reason << "\n"; }
}

void test_basic_hmac() {
    ap_uint<512> msg = 0;
    ap_uint<256> key = 0x12345678;
    ap_uint<256> mac;
    secure::hmac_sha256(msg, key, mac);
    report("basic_nonzero", mac != 0, "HMAC output should be non-zero");
}

void test_deterministic() {
    ap_uint<512> msg = 0xABCD;
    ap_uint<256> key = 0x9999;
    ap_uint<256> mac1, mac2;
    secure::hmac_sha256(msg, key, mac1);
    secure::hmac_sha256(msg, key, mac2);
    report("deterministic", mac1 == mac2, "Same inputs should produce same MAC");
}

void test_different_keys() {
    ap_uint<512> msg = 0x1111;
    ap_uint<256> key1 = 0xAAAA;
    ap_uint<256> key2 = 0xBBBB;
    ap_uint<256> mac1, mac2;
    secure::hmac_sha256(msg, key1, mac1);
    secure::hmac_sha256(msg, key2, mac2);
    report("different_keys", mac1 != mac2, "Different keys should produce different MACs");
}

void test_different_messages() {
    ap_uint<512> msg1 = 0x1111;
    ap_uint<512> msg2 = 0x2222;
    ap_uint<256> key = 0xCCCC;
    ap_uint<256> mac1, mac2;
    secure::hmac_sha256(msg1, key, mac1);
    secure::hmac_sha256(msg2, key, mac2);
    report("different_messages", mac1 != mac2, "Different messages should produce different MACs");
}

int main() {
    test_basic_hmac();
    test_deterministic();
    test_different_keys();
    test_different_messages();
    std::cout << "SUMMARY " << EXAMPLE_ID << ": " << tests_passed << "/" << tests_total << " passed\n";
    return (tests_passed == tests_total) ? 0 : 1;
}
