#include "compare_token.h"
#include <stdint.h>

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t i;
    
    #pragma HLS loop_bound 16
    for (i = 0; i < 16; i++) {
        if (input_token[i] != reference_token[i]) {
            return 0;
        }
    }
    
    return 1;
}
