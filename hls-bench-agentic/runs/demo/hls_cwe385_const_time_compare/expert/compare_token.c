/*
 * Constant-Time Token Comparison Implementation
 * Security Rationale:
 * - Uses bitwise accumulation to avoid early exit on mismatch
 * - Loop bound is statically fixed to 16 iterations via pragma
 * - No conditional branches depend on secret token data
 * - All 16 bytes are read unconditionally in every execution
 * - Memory access pattern is independent of token content
 * - Execution latency is constant regardless of input values
 */

#include <stdint.h>
#include "compare_token.h"

uint8_t compare_token(uint8_t input[16], uint8_t reference[16]) {
    uint8_t result = 1;
    uint8_t i;
    
    #pragma HLS loop_bound min 16 max 16
    for (i = 0; i < 16; i++) {
        uint8_t byte_match = (input[i] == reference[i]) ? 1 : 0;
        result &= byte_match;
    }
    
    return result;
}
