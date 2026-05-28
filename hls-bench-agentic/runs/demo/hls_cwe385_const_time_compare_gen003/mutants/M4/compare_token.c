#include <stdint.h>
#include "compare_token.h"

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t mismatch = 0;
    
    for (uint8_t i = 0; i < 16; i++) {
        mismatch |= input_token[i] ^ reference_token[i];
    }
    
    return (mismatch == 0) ? 1 : 0;
}