/*
 * Constant-Time Token Comparison Implementation
 * 
 * Security Rationale:
 * This implementation ensures constant-time execution by:
 * 1. Using a fixed-iteration loop (exactly 16 iterations) with #pragma HLS loop_bound
 * 2. Avoiding all secret-dependent control flow (no if/else, break, continue, early return)
 * 3. Using bitwise XOR to compute byte differences without branching
 * 4. Accumulating differences with bitwise OR to preserve constant timing
 * 5. Computing final result only after loop completion using bitwise NOT
 * 
 * The loop always executes 16 times regardless of input values, preventing
 * timing side-channels that could leak information about token mismatch positions.
 */

#include "compare_token.h"
#include <stdint.h>

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t diff = 0;
    uint8_t i;
    
    #pragma HLS loop_bound min=16 max=16
    for (i = 0; i < 16; i++) {
        diff |= input_token[i] ^ reference_token[i];
    }
    
    return (diff == 0) ? 1 : 0;
}