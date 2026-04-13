/*
 * Testbench: 03_constant_time_compare
 * Tests that the secure comparator produces correct match/no-match results.
 * Both insecure and secure should agree on all match outcomes.
 */
#include <iostream>
#include <cstdlib>
#include "ap_int.h"
#include "hls_stream.h"

namespace insecure {
    #include "/benchmark/examples/03_constant_time_compare/insecure.cpp"
}
namespace secure {
    #include "/benchmark/examples/03_constant_time_compare/reference_secure.cpp"
}

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "03_constant_time_compare";

void report(const char* name, bool pass, const char* reason = "") {
    tests_total++;
    if (pass) { tests_passed++; std::cout << "TEST " << EXAMPLE_ID << " " << name << ": PASS\n"; }
    else { std::cout << "TEST " << EXAMPLE_ID << " " << name << ": FAIL " << reason << "\n"; }
}

void test_exact_match() {
    hls::stream<secure::compare_req> s_req;
    hls::stream<secure::compare_resp> s_resp;
    secure::compare_req r;
    for (int i = 0; i < 32; i++) { r.candidate[i] = 0xAA; r.reference[i] = 0xAA; }
    s_req.write(r);
    secure::token_compare(s_req, s_resp);
    secure::compare_resp res = s_resp.read();
    report("exact_match", res.match == true, "Should match");
}

void test_first_byte_mismatch() {
    hls::stream<secure::compare_req> s_req;
    hls::stream<secure::compare_resp> s_resp;
    secure::compare_req r;
    for (int i = 0; i < 32; i++) { r.candidate[i] = 0xAA; r.reference[i] = 0xAA; }
    r.candidate[0] = 0xBB;
    s_req.write(r);
    secure::token_compare(s_req, s_resp);
    report("first_byte_mismatch", s_resp.read().match == false, "Should not match");
}

void test_last_byte_mismatch() {
    hls::stream<secure::compare_req> s_req;
    hls::stream<secure::compare_resp> s_resp;
    secure::compare_req r;
    for (int i = 0; i < 32; i++) { r.candidate[i] = 0x55; r.reference[i] = 0x55; }
    r.candidate[31] = 0x56;
    s_req.write(r);
    secure::token_compare(s_req, s_resp);
    report("last_byte_mismatch", s_resp.read().match == false, "Should not match");
}

void test_all_different() {
    hls::stream<secure::compare_req> s_req;
    hls::stream<secure::compare_resp> s_resp;
    secure::compare_req r;
    for (int i = 0; i < 32; i++) { r.candidate[i] = i; r.reference[i] = 31 - i; }
    s_req.write(r);
    secure::token_compare(s_req, s_resp);
    report("all_different", s_resp.read().match == false, "Should not match");
}

void test_equivalence_with_insecure() {
    // Both versions should agree on match outcome
    bool all_agree = true;
    for (int trial = 0; trial < 8; trial++) {
        hls::stream<insecure::compare_req> i_req;
        hls::stream<insecure::compare_resp> i_resp;
        hls::stream<secure::compare_req> s_req;
        hls::stream<secure::compare_resp> s_resp;

        insecure::compare_req ir;
        secure::compare_req sr;
        for (int i = 0; i < 32; i++) {
            ir.candidate[i] = (trial * 7 + i) & 0xFF;
            ir.reference[i] = (trial < 4) ? ir.candidate[i] : (ap_uint<8>)((ir.candidate[i] + 1) & 0xFF);
            sr.candidate[i] = ir.candidate[i];
            sr.reference[i] = ir.reference[i];
        }
        i_req.write(ir); insecure::token_compare(i_req, i_resp);
        s_req.write(sr); secure::token_compare(s_req, s_resp);
        if (i_resp.read().match != s_resp.read().match) all_agree = false;
    }
    report("equivalence_8_trials", all_agree, "Secure/insecure disagree on match result");
}

int main() {
    test_exact_match();
    test_first_byte_mismatch();
    test_last_byte_mismatch();
    test_all_different();
    test_equivalence_with_insecure();
    std::cout << "SUMMARY " << EXAMPLE_ID << ": " << tests_passed << "/" << tests_total << " passed\n";
    return (tests_passed == tests_total) ? 0 : 1;
}
