#include "modinv_kernel.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>

// Simple deterministic LCG-based shuffle generator (fixed seed) so FR4's
// interleaved operand sequence is reproducible across runs without relying
// on <random> library variance across platforms.
static unsigned int next_rand(unsigned int &state)
{
    state = state * 1103515245u + 12345u;
    return state;
}

int main()
{
    // Print MOD value for FR3 verification.
    printf("MOD_VALUE %u\n", (unsigned int)MOD);

    // FR1: for every operand a in [1,250], print modinv(a).
    for (unsigned int a = 1; a <= 250; ++a) {
        unsigned int r = modinv(a);
        printf("FUNC a=%u r=%u\n", a, r);
    }

    // SR1: reset g_iter_count before each call across all a in [1,250],
    // record the iteration count observed after each call.
    for (unsigned int a = 1; a <= 250; ++a) {
        g_iter_count = 0;
        unsigned int r = modinv(a);
        (void)r;
        printf("ITER a=%u count=%lu\n", a, (unsigned long)g_iter_count);
    }

    // FR4: build a fixed-seed pseudo-random sequence of operands, call
    // modinv on them interleaved (not sorted, not grouped), twice each,
    // to check for leftover-state corruption across repeated/interleaved
    // calls. We print REPEAT lines for every call so evaluate.py can check
    // that the result for a given operand is identical every time it is
    // seen, regardless of what other calls happened in between.
    {
        const int N = 60;
        unsigned int ops[N];
        unsigned int state = 987654321u;
        for (int i = 0; i < N; ++i) {
            unsigned int v = (next_rand(state) % 250) + 1;
            ops[i] = v;
        }

        // Interleave: sequence = ops[0], ops[1], ..., ops[N-1], ops[0], ops[1], ...
        // then a shuffled interleaving pass mixing forward and backward reads,
        // exercising repeated calls with different neighboring call history.
        for (int i = 0; i < N; ++i) {
            unsigned int a = ops[i];
            unsigned int r = modinv(a);
            printf("REPEAT a=%u r=%u\n", a, r);
        }
        for (int i = N - 1; i >= 0; --i) {
            unsigned int a = ops[i];
            unsigned int r = modinv(a);
            printf("REPEAT a=%u r=%u\n", a, r);
        }
        // A final mixed pass: even indices forward, odd indices backward-ish,
        // to further interleave distinct operand histories.
        for (int i = 0; i < N; i += 2) {
            unsigned int a = ops[i];
            unsigned int r = modinv(a);
            printf("REPEAT a=%u r=%u\n", a, r);
        }
        for (int i = 1; i < N; i += 2) {
            unsigned int a = ops[i];
            unsigned int r = modinv(a);
            printf("REPEAT a=%u r=%u\n", a, r);
        }
    }

    // SR3: for each of a fixed set of operands spanning fast- and
    // slow-converging cases under the naive baseline algorithm, run a
    // warmup phase followed by many independent timed trials (each trial
    // being a tight loop of many repeated calls). Printing one
    // TIMING_TRIAL line per trial lets evaluate.py compute a robust,
    // outlier-trimmed per-operand median in Python rather than relying on
    // a single noisy wall-clock sample.
    {
        const unsigned int test_operands[] = {1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 125, 200, 249, 250};
        const int NUM_OPS = (int)(sizeof(test_operands) / sizeof(test_operands[0]));
        const int REPS_PER_TRIAL = 50000;
        const int NUM_TRIALS = 15;
        const int WARMUP_REPS = 20000;

        for (int oi = 0; oi < NUM_OPS; ++oi) {
            unsigned int a = test_operands[oi];

            // Warmup phase: untimed calls to avoid cold-cache/frequency
            // scaling skew before timing begins for this operand.
            {
                volatile unsigned int acc = 0;
                for (int i = 0; i < WARMUP_REPS; ++i) {
                    acc += modinv(a);
                }
                (void)acc;
            }

            for (int t = 0; t < NUM_TRIALS; ++t) {
                auto start = std::chrono::high_resolution_clock::now();
                volatile unsigned int acc = 0;
                for (int i = 0; i < REPS_PER_TRIAL; ++i) {
                    acc += modinv(a);
                }
                auto end = std::chrono::high_resolution_clock::now();
                (void)acc;

                long long ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
                printf("TIMING_TRIAL a=%u trial=%d ns=%lld\n", a, t, ns);
            }
        }
    }

    return 0;
}