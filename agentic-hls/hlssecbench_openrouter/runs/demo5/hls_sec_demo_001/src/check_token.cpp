#include "check_token.h"

// Internal expected token: compile-time constant, embedded in the design.
static const ap_uint<8> expected[16] = {
    0x3Au, 0x7Fu, 0x11u, 0xC9u,
    0x04u, 0xD2u, 0x88u, 0x5Eu,
    0xB1u, 0x09u, 0x6Cu, 0xF0u,
    0x23u, 0xA7u, 0x5Bu, 0x1Du
};

ap_uint<1> check_token(const ap_uint<8> token[16]) {
    ap_uint<8> diff = 0;

    // Fixed trip-count loop: always executes 16 iterations.
    for (int i = 0; i < 16; i = i + 1) {
        // Fixed indexing: only token[i] and expected[i] with the loop index.
        ap_uint<8> t = token[i];
        ap_uint<8> e = expected[i];
        ap_uint<8> x = (t ^ e);
        diff = (diff | x);
    }

    // Final decision after processing all bytes (no early exit).
    ap_uint<1> result = (diff == 0);
    return result;
}
