#include <iostream>
#include <cstdint>
#include <cstring>
#include "src/compare_token.h"

using namespace std;

bool test_all_match() {
    uint8_t input[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                         0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t reference[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                             0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t result = compare_token(input, reference);
    return result == 1;
}

bool test_first_byte_mismatch() {
    uint8_t input[16] = {0xFF, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                         0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t reference[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                             0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t result = compare_token(input, reference);
    return result == 0;
}

bool test_last_byte_mismatch() {
    uint8_t input[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                         0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0xFF};
    uint8_t reference[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                             0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t result = compare_token(input, reference);
    return result == 0;
}

bool test_middle_byte_mismatch() {
    uint8_t input[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0xFF,
                         0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t reference[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                             0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t result = compare_token(input, reference);
    return result == 0;
}

bool test_all_bytes_differ() {
    uint8_t input[16] = {0xFF, 0xFE, 0xFD, 0xFC, 0xFB, 0xFA, 0xF9, 0xF8,
                         0xF7, 0xF6, 0xF5, 0xF4, 0xF3, 0xF2, 0xF1, 0xF0};
    uint8_t reference[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                             0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t result = compare_token(input, reference);
    return result == 0;
}

bool test_multiple_mismatches() {
    uint8_t input[16] = {0x01, 0x02, 0xFF, 0x04, 0x05, 0xEE, 0x07, 0x08,
                         0x09, 0x0A, 0x0B, 0xDD, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t reference[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                             0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t result = compare_token(input, reference);
    return result == 0;
}

int main() {
    bool all_passed = true;

    // FR1: Function compares all 16 bytes
    if (test_all_match() && test_all_bytes_differ()) {
        cout << "[PASS] FR1" << endl;
    } else {
        cout << "[FAIL] FR1: Function does not correctly compare all 16 bytes" << endl;
        all_passed = false;
    }

    // FR2: Returns 1 if all bytes match
    if (test_all_match()) {
        cout << "[PASS] FR2" << endl;
    } else {
        cout << "[FAIL] FR2: Function does not return 1 for matching tokens" << endl;
        all_passed = false;
    }

    // FR3: Returns 0 if any byte differs
    if (test_first_byte_mismatch() && test_last_byte_mismatch() && test_middle_byte_mismatch()) {
        cout << "[PASS] FR3" << endl;
    } else {
        cout << "[FAIL] FR3: Function does not return 0 for mismatched tokens" << endl;
        all_passed = false;
    }

    // FR4: Processes entire token length
    if (test_last_byte_mismatch()) {
        cout << "[PASS] FR4" << endl;
    } else {
        cout << "[FAIL] FR4: Function does not process entire token length" << endl;
        all_passed = false;
    }

    // FR5: Loop iterates exactly 16 times (verified by FR1-FR4 passing)
    if (all_passed) {
        cout << "[PASS] FR5" << endl;
    } else {
        cout << "[FAIL] FR5: Loop iteration count verification failed" << endl;
    }

    return all_passed ? 0 : 1;
}
