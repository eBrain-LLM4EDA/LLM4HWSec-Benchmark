/*
 * Testbench: 08_modexp_side_channel
 * Tests modular exponentiation correctness.
 * Both versions should produce the same result for small test vectors.
 */
#include <iostream>
#include <cstdlib>
#include "ap_int.h"
#include "hls_stream.h"

namespace insecure {
    #include "/benchmark/examples/08_modexp_side_channel/insecure.cpp"
}
namespace secure {
    #include "/benchmark/examples/08_modexp_side_channel/reference_secure.cpp"
}

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "08_modexp_side_channel";

void report(const char* name, bool pass, const char* reason = "") {
    tests_total++;
    if (pass) { tests_passed++; std::cout << "TEST " << EXAMPLE_ID << " " << name << ": PASS\n"; }
    else { std::cout << "TEST " << EXAMPLE_ID << " " << name << ": FAIL " << reason << "\n"; }
}

void test_small_modexp() {
    // 3^5 mod 13 = 243 mod 13 = 9
    hls::stream<secure::modexp_req> s_req;
    hls::stream<secure::modexp_resp> s_resp;
    secure::modexp_req r;
    r.base = 3;
    r.exponent = 5;
    r.modulus = 13;
    s_req.write(r);
    secure::modular_exp(s_req, s_resp);
    secure::modexp_resp res = s_resp.read();
    report("3_pow_5_mod_13", res.result == 9, "Expected 9");
}

void test_power_of_two_exp() {
    // 2^10 mod 1000 = 1024 mod 1000 = 24
    hls::stream<secure::modexp_req> s_req;
    hls::stream<secure::modexp_resp> s_resp;
    secure::modexp_req r;
    r.base = 2;
    r.exponent = 10;
    r.modulus = 1000;
    s_req.write(r);
    secure::modular_exp(s_req, s_resp);
    secure::modexp_resp res = s_resp.read();
    report("2_pow_10_mod_1000", res.result == 24, "Expected 24");
}

void test_exp_one() {
    // x^1 mod m = x mod m
    hls::stream<secure::modexp_req> s_req;
    hls::stream<secure::modexp_resp> s_resp;
    secure::modexp_req r;
    r.base = 7;
    r.exponent = 1;
    r.modulus = 100;
    s_req.write(r);
    secure::modular_exp(s_req, s_resp);
    secure::modexp_resp res = s_resp.read();
    report("x_pow_1", res.result == 7, "Expected 7");
}

void test_equivalence() {
    // Both versions should produce same result
    hls::stream<insecure::modexp_req> i_req;
    hls::stream<insecure::modexp_resp> i_resp;
    hls::stream<secure::modexp_req> s_req;
    hls::stream<secure::modexp_resp> s_resp;

    insecure::modexp_req ir;
    ir.base = 5; ir.exponent = 7; ir.modulus = 23;
    i_req.write(ir);
    insecure::modular_exp(i_req, i_resp);

    secure::modexp_req sr;
    sr.base = 5; sr.exponent = 7; sr.modulus = 23;
    s_req.write(sr);
    secure::modular_exp(s_req, s_resp);

    report("equivalence_5_7_23",
           i_resp.read().result == s_resp.read().result,
           "Secure and insecure should agree");
}

int main() {
    test_small_modexp();
    test_power_of_two_exp();
    test_exp_one();
    test_equivalence();
    std::cout << "SUMMARY " << EXAMPLE_ID << ": " << tests_passed << "/" << tests_total << " passed\n";
    return (tests_passed == tests_total) ? 0 : 1;
}
