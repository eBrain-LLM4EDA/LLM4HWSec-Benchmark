#include <stdint.h>
#include "compare_token.h"

int compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    int match = 1;
    
    #pragma HLS loop_bound min=16 max=16
    for (int i = 0; i < 16; i++) {
        if ((input_token[i] ^ reference_token[i]) != 0) {
            match = 0;
        }
    }
    
    return match;
}