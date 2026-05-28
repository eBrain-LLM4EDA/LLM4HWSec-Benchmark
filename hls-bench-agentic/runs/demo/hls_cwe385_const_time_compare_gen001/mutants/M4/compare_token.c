#include <stdint.h>
#include "compare_token.h"

int compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t diff = 0;
    uint8_t xor_result;
    int result = 1;
    
    #pragma HLS loop_bound min=16 max=16
    for (int i = 0; i < 16; i++) {
        xor_result = input_token[i] ^ reference_token[i];
        diff |= xor_result;
        if (diff != 0) {
            result = 0;
        } else {
            result = 1;
        }
    }
    
    return result;
}