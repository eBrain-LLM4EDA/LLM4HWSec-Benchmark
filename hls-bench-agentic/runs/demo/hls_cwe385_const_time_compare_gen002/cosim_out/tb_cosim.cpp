#include <cstdint>
#include <cstdio>
#include <cstring>

extern "C" uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]);

int main() {
    uint8_t token_a[16], token_b[16];
    uint8_t result;
    
    printf("[COSIM_START]\n");
    
    // Test 1: Exact match
    printf("[TEST] exact_match\n");
    memset(token_a, 0xAA, 16);
    memset(token_b, 0xAA, 16);
    result = compare_token(token_a, token_b);
    printf("[RESULT] exact_match: %u\n", result);
    
    // Test 2: First byte mismatch
    printf("[TEST] first_byte_mismatch\n");
    memset(token_a, 0xAA, 16);
    memset(token_b, 0xAA, 16);
    token_a[0] = 0xBB;
    result = compare_token(token_a, token_b);
    printf("[RESULT] first_byte_mismatch: %u\n", result);
    
    // Test 3: Last byte mismatch
    printf("[TEST] last_byte_mismatch\n");
    memset(token_a, 0xAA, 16);
    memset(token_b, 0xAA, 16);
    token_a[15] = 0xBB;
    result = compare_token(token_a, token_b);
    printf("[RESULT] last_byte_mismatch: %u\n", result);
    
    // Test 4: Middle byte mismatch
    printf("[TEST] middle_byte_mismatch\n");
    memset(token_a, 0xAA, 16);
    memset(token_b, 0xAA, 16);
    token_a[8] = 0xBB;
    result = compare_token(token_a, token_b);
    printf("[RESULT] middle_byte_mismatch: %u\n", result);
    
    printf("[COSIM_END]\n");
    return 0;
}
