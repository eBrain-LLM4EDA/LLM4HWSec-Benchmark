#ifndef CHECK_TOKEN_H
#define CHECK_TOKEN_H

#include "ap_int.h"

// Top function: compare a 16-byte input token against an internal expected token.
ap_uint<1> check_token(const ap_uint<8> token[16]);

#endif // CHECK_TOKEN_H
