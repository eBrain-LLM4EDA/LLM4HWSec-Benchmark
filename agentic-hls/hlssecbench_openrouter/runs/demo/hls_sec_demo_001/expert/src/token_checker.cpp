#include "token_checker.h"

ap_uint<1> check_token(const ap_uint<8> in_token[16]) {
  // Internal expected token (compile-time constant).
  const ap_uint<8> expected[16] = {
      ap_uint<8>(0x13), ap_uint<8>(0x37), ap_uint<8>(0xC0), ap_uint<8>(0xDE),
      ap_uint<8>(0x42), ap_uint<8>(0x99), ap_uint<8>(0xA5), ap_uint<8>(0x5A),
      ap_uint<8>(0x00), ap_uint<8>(0xFF), ap_uint<8>(0x10), ap_uint<8>(0x20),
      ap_uint<8>(0x30), ap_uint<8>(0x40), ap_uint<8>(0x50), ap_uint<8>(0x60)};

  // Accumulate all byte differences without early exit.
  ap_uint<8> diff_acc = ap_uint<8>(0);

  for (int i = 0; i < 16; ++i) {
    // All operations are data-independent in control flow and address patterns.
    const ap_uint<8> d = in_token[i] ^ expected[i];
    diff_acc |= d;
  }

  // Explicitly-typed literal avoids ambiguous ap_uint<8> vs int overloads.
  const ap_uint<1> match = (diff_acc == ap_uint<8>(0)) ? ap_uint<1>(1) : ap_uint<1>(0);
  return match;
}
