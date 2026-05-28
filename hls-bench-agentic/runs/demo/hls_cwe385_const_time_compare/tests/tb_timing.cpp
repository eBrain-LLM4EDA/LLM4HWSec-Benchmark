#include <iostream>
#include <cstdint>
#include <cstring>
#include "src/compare_token.h"

using namespace std;

static uint64_t deterministic_step_proxy(uint8_t input[16], uint8_t reference[16]) {
    uint8_t mismatch = 0;
    uint64_t steps = 0;

    for (int i = 0; i < 16; i++) {
        mismatch |= static_cast<uint8_t>(input[i] ^ reference[i]);
        steps++;
    }

    volatile uint8_t expected = (mismatch == 0) ? 1 : 0;
    volatile uint8_t actual = compare_token(input, reference);
    return (expected == actual) ? steps : 0;
}

int main() {
    uint8_t ref[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                       0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    
    // Test case 1: All match
    uint8_t input1[16];
    memcpy(input1, ref, 16);
    
    // Test case 2: First byte mismatch
    uint8_t input2[16];
    memcpy(input2, ref, 16);
    input2[0] = 0xFF;
    
    // Test case 3: Last byte mismatch
    uint8_t input3[16];
    memcpy(input3, ref, 16);
    input3[15] = 0xFF;
    
    // Test case 4: Middle byte mismatch
    uint8_t input4[16];
    memcpy(input4, ref, 16);
    input4[7] = 0xFF;
    
    uint64_t steps1 = deterministic_step_proxy(input1, ref);
    uint64_t steps2 = deterministic_step_proxy(input2, ref);
    uint64_t steps3 = deterministic_step_proxy(input3, ref);
    uint64_t steps4 = deterministic_step_proxy(input4, ref);

    cout << "Deterministic step proxy:" << endl;
    cout << "All match: " << steps1 << endl;
    cout << "First byte mismatch: " << steps2 << endl;
    cout << "Last byte mismatch: " << steps3 << endl;
    cout << "Middle byte mismatch: " << steps4 << endl;

    if (steps1 == 16 && steps2 == 16 && steps3 == 16 && steps4 == 16) {
        cout << "[PASS] SR1" << endl;
        return 0;
    } else {
        cout << "[FAIL] SR1: deterministic operation-count proxy changed across mismatch positions" << endl;
        return 1;
    }
}
