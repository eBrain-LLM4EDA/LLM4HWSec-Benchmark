/*
 * Constant-Time Token Comparison Implementation
 * 
 * Security Rationale:
 * This implementation ensures constant-time execution by:
 * 1. Processing all 16 bytes unconditionally using a fixed-bound loop
 * 2. Accumulating comparison results using bitwise OR without branching
 * 3. Avoiding early returns, breaks, or secret-dependent control flow
 * 4. Using only bitwise operations that execute in constant time
 * 5. Computing final result from accumulated difference without branches
 * 
 * The loop bound is statically fixed at 16 iterations. XOR operations
 * detect byte differences, and bitwise OR accumulates any mismatch.
 * The final comparison (diff == 0) produces the boolean result without
 * revealing which bytes differed or their positions.
 */

#include "compare_token.h"
#include <stdint.h>

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t diff = 0;
    uint8_t i;
    
    #pragma HLS loop_bound 16
    for (i = 0; i < 16; i++) {
        diff |= (input_token[i] ^ reference_token[i]);
    }
    
    return (diff == 0) ? 1 : 0;
}
