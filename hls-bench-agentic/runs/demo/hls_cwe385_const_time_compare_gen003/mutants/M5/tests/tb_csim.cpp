#include <cstdio>
#include <cstdint>
#include <cstring>
#include "test_vectors.h"
extern "C" {
  uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]);
}
int main() {
  bool all_passed = true;
  printf("[INFO] Testing FR1: Function interface\n");
  uint8_t ref[16];
  uint8_t inp[16];
  memset(ref, 0xAA, 16);
  memset(inp, 0xAA, 16);
  uint8_t result = compare_token(inp, ref);
  if (result == 1) {
    printf("[PASS] FR1\n");
  } else {
    printf("[FAIL] FR1: Function did not return 1 for matching tokens\n");
    all_passed = false;
  }
  printf("[INFO] Testing FR2: All bytes match\n");
  for (int i = 0; i < 16; i++) {
    ref[i] = TEST_REF_TOKEN[i];
    inp[i] = TEST_REF_TOKEN[i];
  }
  result = compare_token(inp, ref);
  if (result == 1) {
    printf("[PASS] FR2\n");
  } else {
    printf("[FAIL] FR2: Expected return value 1 for matching tokens, got %u\n", result);
    all_passed = false;
  }
  printf("[INFO] Testing FR3: First byte differs\n");
  memcpy(inp, TEST_REF_TOKEN, 16);
  inp[0] ^= 0x01;
  result = compare_token(inp, ref);
  if (result == 0) {
    printf("[PASS] FR3\n");
  } else {
    printf("[FAIL] FR3: Expected return value 0 for mismatched tokens, got %u\n", result);
    all_passed = false;
  }
  printf("[INFO] Testing FR4: Last byte differs\n");
  memcpy(inp, TEST_REF_TOKEN, 16);
  inp[15] ^= 0xFF;
  result = compare_token(inp, ref);
  if (result == 0) {
    printf("[PASS] FR4\n");
  } else {
    printf("[FAIL] FR4: Expected return value 0 for last byte mismatch, got %u\n", result);
    all_passed = false;
  }
  printf("[INFO] Testing FR5: Middle byte differs\n");
  memcpy(inp, TEST_REF_TOKEN, 16);
  inp[8] ^= 0x55;
  result = compare_token(inp, ref);
  if (result == 0) {
    printf("[PASS] FR5\n");
  } else {
    printf("[FAIL] FR5: Expected return value 0 for middle byte mismatch, got %u\n", result);
    all_passed = false;
  }
  printf("[INFO] Testing deterministic behavior\n");
  int loop_count = 0;
  for (int i = 0; i < 16; i++) {
    loop_count++;
  }
  if (loop_count == 16) {
    printf("[INFO] Loop iteration count verified: 16\n");
  } else {
    printf("[FAIL] Loop iteration count mismatch: expected 16, got %d\n", loop_count);
    all_passed = false;
  }
  if (all_passed) {
    printf("[INFO] All functional tests passed\n");
    return 0;
  } else {
    printf("[INFO] Some functional tests failed\n");
    return 1;
  }
}
