#include "compare_token.h"

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t match = 1;
    
    #pragma HLS loop_bound min=16 max=16
    for (uint8_t i = 0; i < 16; i++) {
        if (input_token[i] != reference_token[i]) {
            match = 0;
        }
    }
    
    // Clear sensitive local state before returning
    uint8_t result = match;
    match = 0;
    return result;
}