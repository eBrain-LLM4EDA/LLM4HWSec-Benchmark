#include <iostream>
#include <cstdint>
#include <cstring>
#include "tests/test_vectors.h"

extern "C" {
  int compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]);
}

static int test_count = 0;
static int pass_count = 0;
static int fail_count = 0;

void run_test(const char* test_name, const char* req_id, const uint8_t* input, const uint8_t* reference, int expected) {
  test_count++;
  int result = compare_token(input, reference);
  if (result == expected) {
    std::cout << "[PASS] " << req_id << ": " << test_name << std::endl;
    pass_count++;
  } else {
    std::cout << "[FAIL] " << req_id << ": " << test_name << " - expected " << expected << ", got " << result << std::endl;
    fail_count++;
  }
}

int main() {
  std::cout << "[INFO] Starting functional requirement tests" << std::endl;

  run_test("All bytes match (zeros)", "FR2", TOKEN_ALL_ZEROS, TOKEN_ALL_ZEROS, 1);
  run_test("All bytes match (ones)", "FR2", TOKEN_ALL_ONES, TOKEN_ALL_ONES, 1);
  run_test("All bytes match (0xAA pattern)", "FR2", TOKEN_PATTERN_AA, TOKEN_PATTERN_AA, 1);
  run_test("All bytes match (sequential)", "FR2", TOKEN_SEQUENTIAL, TOKEN_SEQUENTIAL, 1);
  run_test("All bytes match (random)", "FR2", TOKEN_RANDOM_1, TOKEN_RANDOM_1, 1);

  run_test("Mismatch at byte 0", "FR3", TOKEN_MISMATCH_POS_0, TOKEN_ALL_ZEROS, 0);
  run_test("Mismatch at byte 7 (middle)", "FR3", TOKEN_MISMATCH_POS_7, TOKEN_ALL_ZEROS, 0);
  run_test("Mismatch at byte 15 (last)", "FR3", TOKEN_MISMATCH_POS_15, TOKEN_ALL_ZEROS, 0);
  run_test("All bytes differ", "FR3", TOKEN_ALL_ONES, TOKEN_ALL_ZEROS, 0);
  run_test("Multiple random mismatches", "FR3", TOKEN_MULTI_MISMATCH, TOKEN_ALL_ZEROS, 0);
  run_test("Single bit difference at byte 5", "FR3", TOKEN_SINGLE_BIT_DIFF, TOKEN_SINGLE_BIT_REF, 0);

  uint8_t test_input[16];
  uint8_t test_ref[16];
  for (int pos = 0; pos < 16; pos++) {
    memset(test_input, 0x55, 16);
    memset(test_ref, 0x55, 16);
    test_input[pos] = 0xAA;
    char test_name[64];
    snprintf(test_name, sizeof(test_name), "FR4: Mismatch at position %d", pos);
    run_test(test_name, "FR4", test_input, test_ref, 0);
  }

  run_test("FR1: All 16 bytes accessed (match)", "FR1", TOKEN_SEQUENTIAL, TOKEN_SEQUENTIAL, 1);
  run_test("FR1: All 16 bytes accessed (mismatch last)", "FR1", TOKEN_MISMATCH_POS_15, TOKEN_ALL_ZEROS, 0);

  std::cout << "[INFO] Test summary: " << pass_count << " passed, " << fail_count << " failed out of " << test_count << " tests" << std::endl;

  if (fail_count > 0) {
    return 1;
  }

  return 0;
}
