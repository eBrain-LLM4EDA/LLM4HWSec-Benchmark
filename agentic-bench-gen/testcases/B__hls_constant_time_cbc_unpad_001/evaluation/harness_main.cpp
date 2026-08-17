// evaluation/harness_main.cpp
//
// Behavioral test harness for the pad_check kernel.
//
// Pinned interface (must match public_spec.interface exactly):
//   void pad_check(const unsigned char block[16], int *valid, int *unpadded_len);
//
// Usage:
//   harness_main <32-hex-char-block>
//
// The 16-byte block is supplied as a 32-character hex string on argv[1].
// The harness invokes pad_check exactly once, then prints a single
// machine-parseable line:
//
//   RESULT valid=<0|1> len=<n> block_unchanged=<0|1>
//
// `block_unchanged` is 1 iff the 16 input bytes are bit-identical after
// the call (used by evaluate.py to help verify FR4's "must not modify
// block[]" requirement). No internal iteration/comparison counting is
// attempted here since that would require instrumenting submission
// internals; SR1 (constant-time behavior) and SR3's authoritative
// behavioral probe are checked separately by evaluation/harness_timing.cpp
// and evaluation/harness_probe.cpp.
//
// This file declares pad_check with plain C++ linkage (matching the
// pinned signature exactly, as it appears in inputs/cbc_unpad.cpp) so
// that any conforming implementation -- regardless of internal naming,
// helper functions, or loop structure -- links successfully as long as
// it exposes exactly this symbol.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cctype>

void pad_check(const unsigned char block[16], int *valid, int *unpadded_len);

static int hex_nibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s <32-hex-char-block>\n", argv[0]);
        return 2;
    }

    const char *hex = argv[1];
    if (std::strlen(hex) != 32) {
        std::fprintf(stderr, "error: expected 32 hex chars (16 bytes), got %zu chars\n",
                     std::strlen(hex));
        return 2;
    }

    unsigned char block[16];
    for (int i = 0; i < 16; ++i) {
        int hi = hex_nibble(hex[2 * i]);
        int lo = hex_nibble(hex[2 * i + 1]);
        if (hi < 0 || lo < 0) {
            std::fprintf(stderr, "error: invalid hex digit at byte %d\n", i);
            return 2;
        }
        block[i] = (unsigned char)((hi << 4) | lo);
    }

    unsigned char block_before[16];
    std::memcpy(block_before, block, 16);

    int valid = -1;
    int unpadded_len = -1;

    pad_check(block, &valid, &unpadded_len);

    int unchanged = (std::memcmp(block_before, block, 16) == 0) ? 1 : 0;

    std::printf("RESULT valid=%d len=%d block_unchanged=%d\n",
                valid, unpadded_len, unchanged);

    return 0;
}