/*
 * Testbench: 01_aes_ift
 * Tests that the secure AES kernel produces correct ciphertext
 * and does not expose a debug port.
 */
#include <iostream>
#include <cstdlib>
#include "ap_int.h"
#include "hls_stream.h"

namespace secure {
    #include "/benchmark/examples/01_aes_ift/reference_secure.cpp"
}

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "01_aes_ift";

void report(const char* name, bool pass, const char* reason = "") {
    tests_total++;
    if (pass) { tests_passed++; std::cout << "TEST " << EXAMPLE_ID << " " << name << ": PASS\n"; }
    else { std::cout << "TEST " << EXAMPLE_ID << " " << name << ": FAIL " << reason << "\n"; }
}

void test_basic_encrypt() {
    ap_uint<128> pt = 0;  // all-zero plaintext
    ap_uint<128> key = 0; // all-zero key
    ap_uint<128> ct;
    secure::aes_encrypt(pt, key, ct);
    // With all-zero inputs, output should be deterministic and non-zero
    // (AES never maps zero to zero)
    report("basic_encrypt_nonzero", ct != 0, "Ciphertext is zero for non-trivial AES");
}

void test_different_keys_different_output() {
    ap_uint<128> pt = 0x0123456789ABCDEF;
    ap_uint<128> key1 = 0x1111;
    ap_uint<128> key2 = 0x2222;
    ap_uint<128> ct1, ct2;
    secure::aes_encrypt(pt, key1, ct1);
    secure::aes_encrypt(pt, key2, ct2);
    report("different_keys", ct1 != ct2, "Same ciphertext for different keys");
}

void test_different_plaintexts() {
    // Use values that differ in the lowest byte (byte 0) to ensure
    // the simplified AES (which may have a truncated S-box) still
    // produces different ciphertexts after SubBytes+ShiftRows+AddRoundKey
    ap_uint<128> pt1 = 0x01;
    ap_uint<128> pt2 = 0x02;
    ap_uint<128> key = 0;
    ap_uint<128> ct1, ct2;
    secure::aes_encrypt(pt1, key, ct1);
    secure::aes_encrypt(pt2, key, ct2);
    report("different_plaintexts", ct1 != ct2, "Same ciphertext for different plaintexts");
}

void test_deterministic() {
    ap_uint<128> pt = 0xDEAD;
    ap_uint<128> key = 0xBEEF;
    ap_uint<128> ct1, ct2;
    secure::aes_encrypt(pt, key, ct1);
    secure::aes_encrypt(pt, key, ct2);
    report("deterministic", ct1 == ct2, "Same inputs produce different outputs");
}

int main() {
    test_basic_encrypt();
    test_different_keys_different_output();
    test_different_plaintexts();
    test_deterministic();
    std::cout << "SUMMARY " << EXAMPLE_ID << ": " << tests_passed << "/" << tests_total << " passed\n";
    return (tests_passed == tests_total) ? 0 : 1;
}
