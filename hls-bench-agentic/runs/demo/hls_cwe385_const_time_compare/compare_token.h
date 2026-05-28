#ifndef COMPARE_TOKEN_H
#define COMPARE_TOKEN_H

#include <stdint.h>

/*
 * compare_token - Constant-time comparison of 16-byte tokens
 *
 * Parameters:
 *   input_token: array of 16 bytes representing the input token to verify
 *   reference_token: array of 16 bytes representing the stored reference token
 *
 * Returns:
 *   1 if input_token matches reference_token exactly
 *   0 if any byte differs
 *
 * Security Properties:
 *   - Executes in constant time regardless of input values
 *   - No early exit or data-dependent control flow
 *   - Processes all 16 bytes for every invocation
 */
uint8_t compare_token(uint8_t input_token[16], uint8_t reference_token[16]);

#endif /* COMPARE_TOKEN_H */
