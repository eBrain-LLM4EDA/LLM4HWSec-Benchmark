/*
 * Constant-Time Token Comparison Implementation
 * Security Rationale:
 * - Uses accumulator pattern with bitwise OR to collect mismatch information
 * - Fixed 16-iteration loop with #pragma HLS loop_bound ensures constant timing
 * - No secret-dependent branches (no if/else on comparison results)
 * - No early return or break statements
 * - Single return statement after loop completes
 * - Bitwise XOR and OR operations have fixed latency
 * - All 16 bytes processed regardless of match/mismatch status
 * - Prevents timing side-channel attacks by ensuring identical execution time
 */

#include <stdint.h>
#include "compare_token.h"

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t mismatch = 0;
    
    #pragma HLS loop_bound min=16 max=16
    for (uint8_t i = 0; i < 16; i++) {
        mismatch |= input_token[i] ^ reference_token[i];
    }
    
    return (mismatch == 0) ? 1 : 0;
}