#include <stdint.h>
#include "compare_token.h"

int compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t diff = 0;
    uint8_t xor_result;
    
    #pragma HLS loop_bound min=16 max=16
    for (int i = 0; i < 16; i++) {
        xor_result = input_token[i] ^ reference_token[i];
        if (xor_result != 0) {
            return 0;
        }
        diff |= xor_result;
    }
    
    uint8_t match = (diff == 0) ? 1 : 0;
    return (int)match;
}