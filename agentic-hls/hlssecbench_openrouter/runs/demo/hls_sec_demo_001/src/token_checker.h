#pragma once

#include <ap_int.h>

// Returns 1 if in_token[0..15] exactly matches the internal expected token, else 0.
ap_uint<1> check_token(const ap_uint<8> in_token[16]);
