#include "compare_token.h"
#include <stdint.h>

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t result = 1;
    uint8_t i;
    
    #pragma HLS loop_bound 16
    for (i = 0; i < 16; i++) {
        result = result && (input_token[i] == reference_token[i]);
    }
    
    return result;
}
