/*
 * Constant-Time Token Comparison Implementation
 * Security Rationale:
 * - Uses bitwise OR accumulation to combine all byte comparison results without early exit
 * - Loop executes exactly 16 iterations regardless of input values (annotated with #pragma HLS loop_bound)
 * - No conditional branches or early returns based on comparison results
 * - Final result computed only after all 16 bytes examined
 * - All operations have fixed latency independent of data values
 * - Synthesizes to constant-time hardware circuit with no data-dependent control flow
 */

#include <stdint.h>
#include "compare_token.h"

uint8_t compare_token(uint8_t input_token[16], uint8_t reference_token[16]) {
    uint8_t mismatch = 0;
    uint8_t i;
    
    #pragma HLS loop_bound min=16 max=16
    for (i = 0; i < 16; i++) {
        uint8_t diff = input_token[i] ^ reference_token[i];
        mismatch |= diff;
    }
    
    uint8_t result = (mismatch == 0) ? 1 : 0;
    return result;
}
