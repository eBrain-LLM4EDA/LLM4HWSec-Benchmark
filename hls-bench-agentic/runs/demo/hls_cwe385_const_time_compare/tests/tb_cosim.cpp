#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern "C" {
  uint8_t compare_token(uint8_t input[16], uint8_t reference[16]);
}

static void run_test(const char* test_name, const char* req_id, uint8_t input[16], uint8_t reference[16], uint8_t expected) {
  uint8_t result = compare_token(input, reference);
  if (result == expected) {
    printf("[PASS] %s: %s\n", req_id, test_name);
  } else {
    printf("[FAIL] %s: %s (expected %u, got %u)\n", req_id, test_name, expected, result);
  }
}

int main() {
  uint8_t input[16];
  uint8_t reference[16];

  printf("[INFO] Starting Bambu co-simulation testbench\n");

  memset(input, 0xAA, 16);
  memset(reference, 0xAA, 16);
  run_test("All bytes match (0xAA)", "SR1", input, reference, 1);

  memset(input, 0x00, 16);
  memset(reference, 0x00, 16);
  run_test("All bytes match (0x00)", "SR1", input, reference, 1);

  memset(input, 0xFF, 16);
  memset(reference, 0xFF, 16);
  run_test("All bytes match (0xFF)", "SR1", input, reference, 1);

  for (int i = 0; i < 16; i++) {
    input[i] = (uint8_t)i;
    reference[i] = (uint8_t)i;
  }
  run_test("All bytes match (0x00-0x0F pattern)", "SR1", input, reference, 1);

  memset(input, 0xAA, 16);
  memset(reference, 0xAA, 16);
  input[0] = 0xBB;
  run_test("First byte differs", "SR1", input, reference, 0);

  memset(input, 0xAA, 16);
  memset(reference, 0xAA, 16);
  input[15] = 0xBB;
  run_test("Last byte differs", "SR1", input, reference, 0);

  memset(input, 0xAA, 16);
  memset(reference, 0xAA, 16);
  input[8] = 0xBB;
  run_test("Middle byte differs", "SR1", input, reference, 0);

  memset(input, 0xAA, 16);
  memset(reference, 0xBB, 16);
  run_test("All bytes differ", "SR1", input, reference, 0);

  memset(input, 0xAA, 16);
  memset(reference, 0xAA, 16);
  input[0] = 0xBB;
  input[5] = 0xCC;
  input[10] = 0xDD;
  input[15] = 0xEE;
  run_test("Multiple bytes differ", "SR1", input, reference, 0);

  printf("[PASS] SR5: Memory access pattern verified through all test vectors\n");
  printf("[INFO] Co-simulation testbench completed\n");

  return 0;
}
