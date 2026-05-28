#include "check_token.h"

ap_uint<1> check_token(const ap_uint<8> token[16]) {
    // Built-in expected token: "SECURE_TOKEN_16!"
    // Kept constant to avoid any mutable persistent state.
    static const ap_uint<8> expected[16] = {
        ap_uint<8>(0x53), ap_uint<8>(0x45), ap_uint<8>(0x43), ap_uint<8>(0x55),
        ap_uint<8>(0x52), ap_uint<8>(0x45), ap_uint<8>(0x5F), ap_uint<8>(0x54),
        ap_uint<8>(0x4F), ap_uint<8>(0x4B), ap_uint<8>(0x45), ap_uint<8>(0x4E),
        ap_uint<8>(0x5F), ap_uint<8>(0x31), ap_uint<8>(0x36), ap_uint<8>(0x21)
    };

    // Constant-time reduction of per-byte differences.
    ap_uint<8> diff = 0;

    // Fixed-iteration loop: always compares all 16 bytes.
    for (int i = 0; i < 16; ++i) {
        // No secret-dependent branches; index depends only on loop counter.
        diff |= (token[i] ^ expected[i]);
    }

    // Match iff all bytes match.
    ap_uint<1> match = (diff == ap_uint<8>(0));
    return match;
}
