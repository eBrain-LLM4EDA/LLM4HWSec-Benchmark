#include <iostream>
#include <stdint.h>
#include <cstring>
#include "vectors.h"
extern "C" uint8_t compare_token(uint8_t input_token[16], uint8_t reference_token[16]);
int main() {
  for(int i=0; i<num_vectors; i++) {
    uint8_t inp[16], ref[16];
    memcpy(inp, test_vectors[i].input, 16);
    memcpy(ref, test_vectors[i].reference, 16);
    uint8_t result = compare_token(inp, ref);
    if(result != test_vectors[i].expected) {
      std::cout << "[FAIL] SR1: cosim vector " << test_vectors[i].name << " expected " << (int)test_vectors[i].expected << " got " << (int)result << std::endl;
      return 1;
    }
  }
  std::cout << "[PASS] SR1" << std::endl;
  return 0;
}
