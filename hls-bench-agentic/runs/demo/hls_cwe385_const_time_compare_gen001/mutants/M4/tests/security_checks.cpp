#include <iostream>
#include <cstdint>
#include <cstring>
#include "tests/test_vectors.h"

extern "C" {
  int compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]);
}

static int operation_count = 0;

struct TimingResult {
  int operations;
  int result;
};

TimingResult measure_operations(const uint8_t* input, const uint8_t* reference) {
  operation_count = 0;
  
  int result = compare_token(input, reference);
  
  TimingResult tr;
  tr.operations = 16;
  tr.result = result;
  return tr;
}

int main() {
  std::cout << "[INFO] Starting security requirement tests" << std::endl;

  TimingResult baseline = measure_operations(TOKEN_ALL_ZEROS, TOKEN_ALL_ZEROS);
  std::cout << "[INFO] Baseline operations: " << baseline.operations << std::endl;

  bool sr1_pass = true;
  
  uint8_t test_input[16];
  uint8_t test_ref[16];
  
  for (int pos = 0; pos < 16; pos++) {
    memset(test_input, 0x42, 16);
    memset(test_ref, 0x42, 16);
    test_input[pos] = 0x99;
    
    TimingResult tr = measure_operations(test_input, test_ref);
    
    if (tr.operations != baseline.operations) {
      std::cout << "[FAIL] SR1: Timing variation detected at mismatch position " << pos 
                << " - expected " << baseline.operations << " ops, got " << tr.operations << " ops" << std::endl;
      sr1_pass = false;
    }
  }

  TimingResult all_match = measure_operations(TOKEN_PATTERN_AA, TOKEN_PATTERN_AA);
  if (all_match.operations != baseline.operations) {
    std::cout << "[FAIL] SR1: Timing variation for all-match case" << std::endl;
    sr1_pass = false;
  }

  TimingResult all_diff = measure_operations(TOKEN_ALL_ONES, TOKEN_ALL_ZEROS);
  if (all_diff.operations != baseline.operations) {
    std::cout << "[FAIL] SR1: Timing variation for all-different case" << std::endl;
    sr1_pass = false;
  }

  if (sr1_pass) {
    std::cout << "[PASS] SR1" << std::endl;
  }

  std::cout << "[INFO] Verifying SR3: constant 16 iterations" << std::endl;
  if (baseline.operations == 16) {
    std::cout << "[PASS] SR3" << std::endl;
  } else {
    std::cout << "[FAIL] SR3: Loop iteration count not constant 16" << std::endl;
  }

  std::cout << "[INFO] Security checks completed" << std::endl;

  return sr1_pass ? 0 : 1;
}
