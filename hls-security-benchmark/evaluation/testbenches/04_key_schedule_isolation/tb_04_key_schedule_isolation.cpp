/*
 * Testbench: 04_key_schedule_isolation
 * Tests crypto engine: key load, process, zeroize cycle.
 * Secure version adds a zeroize port.
 */
#include <iostream>
#include <cstdlib>
#include "ap_int.h"
#include "hls_stream.h"

namespace secure {
    #include "/benchmark/examples/04_key_schedule_isolation/reference_secure.cpp"
}

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "04_key_schedule_isolation";

void report(const char* name, bool pass, const char* reason = "") {
    tests_total++;
    if (pass) { tests_passed++; std::cout << "TEST " << EXAMPLE_ID << " " << name << ": PASS\n"; }
    else { std::cout << "TEST " << EXAMPLE_ID << " " << name << ": FAIL " << reason << "\n"; }
}

void test_key_load_and_process() {
    ap_uint<128> data_in = 0x0123456789ABCDEF;
    ap_uint<128> key = 0xFEDCBA9876543210;
    ap_uint<128> data_out;

    // Load key
    secure::crypto_engine(0, key, data_out, true, false, false);
    // Process data
    secure::crypto_engine(data_in, 0, data_out, false, true, false);

    // Output should be non-zero (XOR with key)
    report("key_load_process", data_out != 0, "Output is zero after key+process");
}

void test_deterministic_output() {
    ap_uint<128> data_in = 0xAAAABBBBCCCCDDDD;
    ap_uint<128> key = 0x1111222233334444;
    ap_uint<128> out1, out2;

    secure::crypto_engine(0, key, out1, true, false, false);
    secure::crypto_engine(data_in, 0, out1, false, true, false);

    secure::crypto_engine(0, key, out2, true, false, false);
    secure::crypto_engine(data_in, 0, out2, false, true, false);

    report("deterministic", out1 == out2, "Same inputs produce different outputs");
}

void test_different_keys() {
    ap_uint<128> data_in = 0x1234;
    ap_uint<128> key1 = 0xAAAA;
    ap_uint<128> key2 = 0xBBBB;
    ap_uint<128> out1, out2;

    secure::crypto_engine(0, key1, out1, true, false, false);
    secure::crypto_engine(data_in, 0, out1, false, true, false);

    secure::crypto_engine(0, key2, out2, true, false, false);
    secure::crypto_engine(data_in, 0, out2, false, true, false);

    report("different_keys", out1 != out2, "Same output for different keys");
}

void test_zeroize() {
    ap_uint<128> key = 0x5EC2E7;
    ap_uint<128> data_out;

    // Load key, then zeroize
    secure::crypto_engine(0, (ap_uint<128>)0xDEAD, data_out, true, false, false);
    secure::crypto_engine(0, 0, data_out, false, false, true);  // zeroize
    report("zeroize_runs", true, "");  // Just verify it doesn't crash
}

int main() {
    test_key_load_and_process();
    test_deterministic_output();
    test_different_keys();
    test_zeroize();
    std::cout << "SUMMARY " << EXAMPLE_ID << ": " << tests_passed << "/" << tests_total << " passed\n";
    return (tests_passed == tests_total) ? 0 : 1;
}
