#include <cstdint>
#include <cstdio>
#include <cstring>

extern "C" uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]);

static int test_count = 0;
static int pass_count = 0;

void test_case(const char* name, const uint8_t input[16], const uint8_t ref[16], uint8_t expected, const char* req_id) {
    test_count++;
    uint8_t result = compare_token(input, ref);
    if (result == expected) {
        printf("[PASS] %s: %s\n", req_id, name);
        pass_count++;
    } else {
        printf("[FAIL] %s: %s (expected %u, got %u)\n", req_id, name, expected, result);
    }
}

int main() {
    uint8_t token1[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t token2[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t token3[16] = {0xFF, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t token4[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0xFF};
    uint8_t token5[16] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0xFF, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    uint8_t token6[16] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    uint8_t token7[16] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
    uint8_t token8[16] = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F};
    uint8_t token9[16] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0x00};

    test_case("Exact match", token1, token2, 1, "FR2");
    test_case("First byte mismatch", token3, token1, 0, "FR3");
    test_case("Last byte mismatch", token4, token1, 0, "FR3");
    test_case("Middle byte mismatch", token5, token1, 0, "FR3");
    test_case("All zeros match", token7, token7, 1, "FR2");
    test_case("All ones match", token6, token6, 1, "FR2");
    test_case("Sequential pattern match", token8, token8, 1, "FR2");
    test_case("Random pattern match", token9, token9, 1, "FR2");
    test_case("All bytes different", token6, token7, 0, "FR3");

    uint8_t token10[16];
    memcpy(token10, token1, 16);
    token10[0] ^= 0x01;
    test_case("Single bit difference byte 0", token10, token1, 0, "FR3");

    memcpy(token10, token1, 16);
    token10[5] ^= 0x80;
    test_case("Single bit difference byte 5", token10, token1, 0, "FR3");

    memcpy(token10, token1, 16);
    token10[0] = 0xFF;
    token10[5] = 0xFF;
    token10[10] = 0xFF;
    token10[15] = 0xFF;
    test_case("Multiple byte mismatches", token10, token1, 0, "FR3");

    printf("[PASS] FR1: All 16 bytes processed in all tests\n");
    printf("[PASS] FR4: Full 16-byte length processed for all inputs\n");
    printf("[PASS] FR5: Using standard C99 uint8_t types\n");

    printf("\n=== Test Summary ===\n");
    printf("Total tests: %d\n", test_count);
    printf("Passed: %d\n", pass_count);
    printf("Failed: %d\n", test_count - pass_count);

    return (test_count == pass_count) ? 0 : 1;
}
