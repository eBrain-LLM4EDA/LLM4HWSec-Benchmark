#include "compare_token.h"
#include <stdint.h>

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t diff = 0;
    uint8_t i;
    
    #pragma HLS loop_bound 16
    for (i = 0; i < 16; i++) {
        uint8_t byte_diff = input_token[i] ^ reference_token[i];
        if (byte_diff != 0) {
            diff = 1;
        } else {
            diff = diff;
        }
    }
    
    return (diff == 0) ? 1 : 0;
}
