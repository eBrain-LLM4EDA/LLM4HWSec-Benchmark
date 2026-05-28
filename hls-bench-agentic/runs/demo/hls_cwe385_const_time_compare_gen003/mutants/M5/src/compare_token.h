#ifdef __cplusplus
extern "C" {
#endif

#ifndef COMPARE_TOKEN_H
#define COMPARE_TOKEN_H

#include <stdint.h>

uint8_t compare_token(const uint8_t input_token[16], const uint8_t reference_token[16]);

#endif

#ifdef __cplusplus
}
#endif
