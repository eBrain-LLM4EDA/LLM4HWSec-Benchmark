// evaluation/harness_timing.cpp
//
// Timing harness used for SR1 (constant-time behavior) via adversarial
// mismatch-position vectors.
//
// Pinned interface (must match public_spec.interface exactly):
//   void pad_check(const unsigned char block[16], int *valid, int *unpadded_len);
//
// Usage:
//   harness_timing <label1>:<32-hex-char-block> [<label2>:<32-hex-char-block> ...]
//
// For each labeled 16-byte block supplied on argv, this harness runs
// REPS_PER_ROUND back-to-back calls to pad_check(), measures the total
// wall-clock elapsed with std::chrono::steady_clock, and repeats this
// ROUNDS times, printing every round's per-call time in nanoseconds so
// that evaluate.py can compute a median per label and do a
// majority-vote comparison across several independent runs of this
// harness (invoked repeatedly by evaluate.py) to reduce flakiness.
//
// Output format (one line per round per label), machine-parseable:
//   TIMING <label> round=<r> ns_per_call=<value>
//
// evaluate.py aggregates the per-round ns_per_call values into a
// median per label, then compares medians across labels ordered by
// "distance from the end of the block" (for SR1) to detect a
// monotonic timing trend indicative of an early-exit padding scan.
//
// This file declares pad_check with plain C++ linkage (matching the
// pinned signature exactly, as it appears in inputs/cbc_unpad.cpp) so
// that any conforming implementation -- regardless of internal naming,
// helper functions, or loop structure -- links successfully as long as
// it exposes exactly this symbol.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <vector>
#include <string>

void pad_check(const unsigned char block[16], int *valid, int *unpadded_len);

#ifndef REPS_PER_ROUND
#define REPS_PER_ROUND 200000
#endif

#ifndef ROUNDS
#define ROUNDS 7
#endif

// Wraps a batch of REPS_PER_ROUND calls to pad_check with a
// steady_clock measurement, guarding against compiler optimizing the
// loop away by consuming the outputs into a volatile sink.
#define PAD_CHECK_PROBE(block_ptr, reps, out_ns_per_call)                       \
    do {                                                                       \
        volatile int sink_valid = 0;                                           \
        volatile int sink_len = 0;                                             \
        int v_tmp, l_tmp;                                                      \
        auto t0 = std::chrono::steady_clock::now();                            \
        for (long i = 0; i < (reps); ++i) {                                    \
            pad_check((block_ptr), &v_tmp, &l_tmp);                            \
            sink_valid ^= v_tmp;                                               \
            sink_len ^= l_tmp;                                                 \
        }                                                                      \
        auto t1 = std::chrono::steady_clock::now();                            \
        (void)sink_valid;                                                      \
        (void)sink_len;                                                        \
        double total_ns = std::chrono::duration<double, std::nano>(t1 - t0).count(); \
        (out_ns_per_call) = total_ns / (double)(reps);                         \
    } while (0)

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

    std::vector<std::string> labels;
    std::vector<std::vector<unsigned char>> blocks;

    for (int a = 1; a < argc; ++a) {
        std::string arg(argv[a]);
        size_t colon = arg.find(':');
        if (colon == std::string::npos) {
            std::fprintf(stderr, "error: malformed argument '%s' (expected label:hex)\n",
                         arg.c_str());
            return 2;
        }
        std::string label = arg.substr(0, colon);
        std::string hex = arg.substr(colon + 1);

        unsigned char block[16];
        if (!parse_block(hex.c_str(), block)) {
            std::fprintf(stderr, "error: invalid hex block for label '%s'\n", label.c_str());
            return 2;
        }

        labels.push_back(label);
        blocks.push_back(std::vector<unsigned char>(block, block + 16));
    }

    // Warm up (touch code/data caches, let any lazy setup happen) before
    // taking timed measurements, and interleave labels within each round
    // rather than doing all rounds of one label before moving to the
    // next, to average out any slow drift in system load over time.
    {
        int v_tmp, l_tmp;
        for (size_t li = 0; li < blocks.size(); ++li) {
            for (int w = 0; w < 1000; ++w) {
                pad_check(blocks[li].data(), &v_tmp, &l_tmp);
            }
        }
    }

    for (int r = 0; r < ROUNDS; ++r) {
        for (size_t li = 0; li < blocks.size(); ++li) {
            double ns_per_call = 0.0;
            unsigned char local_block[16];
            std::memcpy(local_block, blocks[li].data(), 16);

            PAD_CHECK_PROBE(local_block, REPS_PER_ROUND, ns_per_call);

            std::printf("TIMING %s round=%d ns_per_call=%.6f\n",
                        labels[li].c_str(), r, ns_per_call);
        }
    }

    return 0;
}