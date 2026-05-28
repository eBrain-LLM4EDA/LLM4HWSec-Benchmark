/*
 * Constant-Time Token Comparison Implementation
 * Security Rationale:
 * - Processes all 16 bytes unconditionally using fixed loop bound
 * - Uses bitwise OR accumulation (diff |= xor_result) to avoid short-circuit evaluation
 * - No early returns, breaks, or data-dependent branches
 * - XOR operation produces 0 for matching bytes, non-zero for mismatches
 * - Final result computed after all bytes processed via bitwise NOT of accumulated diff
 * - Execution latency identical regardless of mismatch position or count
 * - Suitable for PandA-Bambu synthesis with deterministic timing
 */

#include <stdint.h>
#include "compare_token.h"

int compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]) {
    uint8_t diff = 0;
    uint8_t xor_result;
    
    #pragma HLS loop_bound min=16 max=16
    for (int i = 0; i < 16; i++) {
        xor_result = input_token[i] ^ reference_token[i];
        diff |= xor_result;
    }
    
    uint8_t match = (diff == 0) ? 1 : 0;
    return (int)match;
}