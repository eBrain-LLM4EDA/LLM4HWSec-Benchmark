// evaluation/harness_counter.cpp
//
// Self-test fixture for the counting/probing methodology used by
// evaluation/harness_probe.cpp when computing the SR3 verdict.
//
// This file does NOT call the submission's pad_check() at all. Instead
// it contains two small, self-contained, deliberately independent
// reimplementations of the PKCS#7 padding-region scan -- one shaped
// like the KNOWN-VULNERABLE baseline pattern (stops scanning as soon
// as a mismatch is found: EARLY_EXIT), and one shaped like a
// KNOWN-CONSTANT-TIME pattern (always walks the full 16-byte block,
// accumulating a mask, never branching on the comparison result to
// change control flow: FULL_SCAN). Both variants are instrumented
// with an explicit, deterministic iteration counter (not wall-clock
// timing, not a hardware cycle counter) so that evaluate.py can
// sanity-check, once per grading run, that "counting the number of
// per-byte comparison steps actually executed" is a methodology that
// (a) reports a position-correlated, non-constant iteration count for
// the EARLY_EXIT shape, and (b) reports a perfectly constant iteration
// count (always 16) for the FULL_SCAN shape, across the same set of
// adversarial mismatch-position vectors used against the real
// submission in harness_probe.cpp.
//
// This is purely a self-test of the measurement technique; it never
// contributes to the pass/fail verdict for the actual submission. The
// actual SR3 verdict against the submission is produced separately by
// evaluate.py invoking evaluation/harness_probe.cpp, which links
// directly against the submission's pad_check() and measures its
// behavior. If this self-test ever failed to distinguish EARLY_EXIT
// from FULL_SCAN, that would indicate the counting methodology itself
// is unsound -- evaluate.py runs this fixture once as a guard before
// trusting harness_probe.cpp's results.
//
// Build-time selection:
//   g++ -DSCAN_MODE=EARLY_EXIT  -o harness_counter_early evaluation/harness_counter.cpp
//   g++ -DSCAN_MODE=FULL_SCAN   -o harness_counter_full  evaluation/harness_counter.cpp
//
// Usage:
//   harness_counter_<mode> <label1>:<32-hex-char-block> [<label2>:<32-hex-char-block> ...]
//
// Output format (one line per label), machine-parseable:
//   COUNT <label> iterations=<n> valid=<0|1> len=<n>
//
// where `iterations` is the number of per-byte comparison steps
// actually executed while scanning the padding region of the block
// (not counting the initial length-byte range check), `valid` and
// `len` are the resulting PKCS#7 validity/length outputs of this
// fixture's own scan (for sanity cross-checking against the reference
// oracle, independent of the submission).

#include <cstdio>
#include <cstdlib>
#include <cstring>

#ifndef SCAN_MODE
#error "SCAN_MODE must be defined to either EARLY_EXIT or FULL_SCAN"
#endif

#define EARLY_EXIT 1
#define FULL_SCAN 2

#if (SCAN_MODE != EARLY_EXIT) && (SCAN_MODE != FULL_SCAN)
#error "SCAN_MODE must be EARLY_EXIT or FULL_SCAN"
#endif

// counting_pad_check: a self-contained fixture reimplementation of the
// PKCS#7 padding-region scan, instrumented with an explicit iteration
// counter. This function is intentionally NOT the submission under
// test -- it exists solely so evaluate.py can verify that counting
// "number of per-byte comparisons executed" reliably distinguishes an
// early-exit scan from a full, uniform scan, using the exact same
// vector shapes (adversarial mismatch positions within a fixed N=8
// padding region) that harness_probe.cpp will later apply to the real
// submission.
static void counting_pad_check(const unsigned char block[16],
                                int *valid, int *unpadded_len,
                                long *iterations)
{
    *iterations = 0;

    unsigned char n = block[15];

    if (n == 0 || n > 16) {
        *valid = 0;
        *unpadded_len = 16;
        return;
    }

    int start = 16 - (int)n;

#if SCAN_MODE == EARLY_EXIT
    // KNOWN-VULNERABLE shape: stop scanning (and stop counting further
    // iterations) as soon as the first mismatching byte is found,
    // scanning from the end of the block backward toward `start` --
    // exactly the pattern that produces a position-dependent
    // comparison count (the classic Vaudenay timing oracle shape).
    for (int i = 15; i >= start; --i) {
        (*iterations)++;
        if (block[i] != n) {
            *valid = 0;
            *unpadded_len = 16;
            return;
        }
    }
    *valid = 1;
    *unpadded_len = start;
#elif SCAN_MODE == FULL_SCAN
    // KNOWN-CONSTANT-TIME shape: always walk every byte position in
    // the padding region (start..15) regardless of whether an earlier
    // byte already mismatched, accumulating validity via bitwise
    // logic rather than branching on the comparison result to alter
    // control flow. The iteration counter always increments exactly
    // (16 - start) times for a given N, and since padding-region
    // vectors used by harness_probe.cpp for SR3 fix N=8, this counter
    // will always read exactly 8 across every mismatch-position
    // vector tested, independent of where the mismatch is placed.
    int mismatch_mask = 0;
    for (int i = start; i <= 15; ++i) {
        (*iterations)++;
        mismatch_mask |= (block[i] != n) ? 1 : 0;
    }
    if (mismatch_mask == 0) {
        *valid = 1;
        *unpadded_len = start;
    } else {
        *valid = 0;
        *unpadded_len = 16;
    }
#endif
}

static int hex_nibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static bool parse_block(const char *hex, unsigned char block[16])
{
    if (std::strlen(hex) != 32) return false;
    for (int i = 0; i < 16; ++i) {
        int hi = hex_nibble(hex[2 * i]);
        int lo = hex_nibble(hex[2 * i + 1]);
        if (hi < 0 || lo < 0) return false;
        block[i] = (unsigned char)((hi << 4) | lo);
    }
    return true;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        std::fprintf(stderr,
            "usage: %s <label>:<32-hex-char-block> [<label>:<32-hex-char-block> ...]\n",
            argv[0]);
        return 2;
    }

    for (int a = 1; a < argc; ++a) {
        std::string arg_str(argv[a]);
        // Manual split on first ':' without pulling in <string> algorithms
        // beyond basic std::string usage (already used elsewhere in the
        // harness suite for argv parsing convenience).
        size_t colon = arg_str.find(':');
        if (colon == std::string::npos) {
            std::fprintf(stderr, "error: malformed argument '%s' (expected label:hex)\n",
                         arg_str.c_str());
            return 2;
        }
        std::string label = arg_str.substr(0, colon);
        std::string hex = arg_str.substr(colon + 1);

        unsigned char block[16];
        if (!parse_block(hex.c_str(), block)) {
            std::fprintf(stderr, "error: invalid hex block for label '%s'\n", label.c_str());
            return 2;
        }

        int valid = -1;
        int unpadded_len = -1;
        long iterations = -1;

        counting_pad_check(block, &valid, &unpadded_len, &iterations);

        std::printf("COUNT %s iterations=%ld valid=%d len=%d\n",
                    label.c_str(), iterations, valid, unpadded_len);
    }

    return 0;
}