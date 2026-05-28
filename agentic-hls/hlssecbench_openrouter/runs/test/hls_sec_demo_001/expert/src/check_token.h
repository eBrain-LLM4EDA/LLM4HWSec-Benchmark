#ifndef CHECK_TOKEN_H_
#define CHECK_TOKEN_H_

#include "ap_int.h"

// Top-level function (HLS entry point)
ap_uint<1> check_token(const ap_uint<8> token[16]);

#endif // CHECK_TOKEN_H_
