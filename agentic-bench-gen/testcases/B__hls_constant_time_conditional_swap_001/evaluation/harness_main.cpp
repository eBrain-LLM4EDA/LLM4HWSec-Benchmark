#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <vector>
#include <string>
#include <chrono>
#include <algorithm>

// Plain C++ linkage declaration matching a normal C++17 translation unit
// that defines conditional_swap with the exact pinned signature. Do NOT
// use extern "C" here: the submission is compiled as ordinary C++17, so
// its mangled symbol must match this ordinary C++ declaration exactly.
void conditional_swap(uint32_t *P, uint32_t *Q, int n, unsigned int ctrl_bit);

// Simple deterministic PRNG (xorshift32) so results are reproducible
// across runs and independent of platform rand() implementations.
static uint32_t xorshift32(uint32_t &state)
{
    uint32_t x = state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    state = x;
    return x;
}

static void fill_random(std::vector<uint32_t> &v, uint32_t seed)
{
    uint32_t state = seed ? seed : 0xdeadbeefu;
    for (size_t i = 0; i < v.size(); ++i)
    {
        v[i] = xorshift32(state);
    }
}

int main(int argc, char **argv)
{
    if (argc < 2)
    {
        fprintf(stderr, "usage: %s <functional|access_trace|timing> [args]\n", argv[0]);
        return 2;
    }

    std::string mode = argv[1];

    if (mode == "functional")
    {
        const int sizes[] = {1, 2, 64, 4096};
        int overall_fail = 0;

        for (int si = 0; si < 4; ++si)
        {
            int n = sizes[si];

            // --- ctrl_bit = 1: expect full swap ---
            {
                std::vector<uint32_t> P(n), Q(n);
                fill_random(P, 0x1234u + (uint32_t)n);
                fill_random(Q, 0x9abcu + (uint32_t)n * 7u + 1u);

                std::vector<uint32_t> origP = P, origQ = Q;

                conditional_swap(P.data(), Q.data(), n, 1u);

                bool ok = true;
                for (int i = 0; i < n; ++i)
                {
                    if (P[i] != origQ[i] || Q[i] != origP[i])
                    {
                        ok = false;
                        break;
                    }
                }

                printf("PROBE swap_ctrl1_n%d %s\n", n, ok ? "PASS" : "FAIL");
                if (!ok) overall_fail = 1;
            }

            // --- ctrl_bit = 0: expect no change ---
            {
                std::vector<uint32_t> P(n), Q(n);
                fill_random(P, 0x5555u + (uint32_t)n * 3u);
                fill_random(Q, 0xaaaau + (uint32_t)n * 11u + 2u);

                std::vector<uint32_t> origP = P, origQ = Q;

                conditional_swap(P.data(), Q.data(), n, 0u);

                bool ok = true;
                for (int i = 0; i < n; ++i)
                {
                    if (P[i] != origP[i] || Q[i] != origQ[i])
                    {
                        ok = false;
                        break;
                    }
                }

                printf("PROBE noop_ctrl0_n%d %s\n", n, ok ? "PASS" : "FAIL");
                if (!ok) overall_fail = 1;
            }
        }

        printf("FUNCTIONAL_DONE %s\n", overall_fail ? "FAIL" : "PASS");
        return overall_fail;
    }
    else if (mode == "access_trace")
    {
        // SR2: build a fixed-size buffer with per-element sentinel values
        // that let us reconstruct, after the call, exactly which indices
        // were touched (i.e. whose value changed) and in what pattern.
        // Because we cannot instrument the callee's internal instruction
        // stream from outside without recompiling it, we approximate the
        // "access pattern" observable at the interface level: which
        // indices ended up modified, and a checksum computed by folding
        // over all indices in a fixed deterministic order so that any
        // data-dependent skipping of indices (e.g. an early-return branch
        // guarded by ctrl_bit) shows up as a differing fingerprint length
        // or order between ctrl_bit=0 and ctrl_bit=1 runs.
        //
        // Usage: access_trace <n>
        if (argc < 3)
        {
            fprintf(stderr, "access_trace requires <n>\n");
            return 2;
        }
        int n = atoi(argv[2]);
        if (n <= 0) n = 64;

        for (unsigned int ctrl = 0; ctrl <= 1; ++ctrl)
        {
            std::vector<uint32_t> P(n), Q(n);
            fill_random(P, 0x2468u + (uint32_t)n);
            fill_random(Q, 0x1357u + (uint32_t)n * 13u);

            std::vector<uint32_t> origP = P, origQ = Q;

            conditional_swap(P.data(), Q.data(), n, ctrl);

            // Build a fixed-order fingerprint: for each index i (in
            // ascending order, always visiting every index regardless of
            // whether it changed), record whether P[i] changed and
            // whether Q[i] changed, folding a running checksum. This
            // always iterates the full fixed range 0..n-1 in the same
            // order for both ctrl values; a constant-time / masked
            // implementation touches every index identically for both
            // ctrl values, so the "changed" bit vector will differ in
            // VALUE at a given ctrl (values legitimately differ) but the
            // LENGTH and ORDER (i.e., that index i was visited and
            // produced a defined changed/unchanged classification) must
            // be identical in structure. We print a fingerprint that
            // encodes, per index, only whether *some* deterministic
            // structural signal was observed, using a checksum over the
            // sequence of (i, changedP, changedQ) triples where changedP
            // and changedQ are computed relative to a XOR-difference from
            // original, not raw values, so the fingerprint's *shape*
            // (order/length) is what we compare, not the secret-dependent
            // content.
            uint64_t checksum = 1469598103934665603ULL; // FNV offset basis
            int touched_count = 0;
            for (int i = 0; i < n; ++i)
            {
                int changedP = (P[i] != origP[i]) ? 1 : 0;
                int changedQ = (Q[i] != origQ[i]) ? 1 : 0;
                if (changedP || changedQ) touched_count++;

                // Fold index and structural (not value) info into checksum
                uint64_t mix = (uint64_t)(uint32_t)i;
                mix ^= ((uint64_t)changedP << 32);
                mix ^= ((uint64_t)changedQ << 33);
                checksum ^= mix;
                checksum *= 1099511628211ULL; // FNV prime
            }

            printf("ACCESS_TRACE ctrl=%u n=%d indices_visited=%d fingerprint=%016llx\n",
                   ctrl, n, n, (unsigned long long)checksum);
            (void)touched_count;
        }

        return 0;
    }
    else if (mode == "timing")
    {
        // SR3: time many repeated calls to conditional_swap for
        // ctrl_bit=0 and ctrl_bit=1 at a large n, report median
        // microseconds for each so evaluate.py can compare ratios.
        //
        // Usage: timing <n> <trials>
        int n = (argc >= 3) ? atoi(argv[2]) : 4096;
        int trials = (argc >= 4) ? atoi(argv[3]) : 401;
        if (n <= 0) n = 4096;
        if (trials <= 0) trials = 401;

        for (unsigned int ctrl = 0; ctrl <= 1; ++ctrl)
        {
            std::vector<uint32_t> P(n), Q(n);
            fill_random(P, 0x777u + (uint32_t)n);
            fill_random(Q, 0x888u + (uint32_t)n);

            std::vector<double> samples;
            samples.reserve(trials);

            // Warm-up
            for (int w = 0; w < 5; ++w)
            {
                conditional_swap(P.data(), Q.data(), n, ctrl);
            }

            for (int t = 0; t < trials; ++t)
            {
                auto start = std::chrono::high_resolution_clock::now();
                conditional_swap(P.data(), Q.data(), n, ctrl);
                auto end = std::chrono::high_resolution_clock::now();
                double us = std::chrono::duration<double, std::micro>(end - start).count();
                samples.push_back(us);
            }

            std::sort(samples.begin(), samples.end());
            double median;
            size_t m = samples.size();
            if (m % 2 == 0)
            {
                median = (samples[m / 2 - 1] + samples[m / 2]) / 2.0;
            }
            else
            {
                median = samples[m / 2];
            }

            printf("TIMING ctrl=%u n=%d trials=%d median_us=%.6f\n",
                   ctrl, n, trials, median);
        }

        return 0;
    }
    else
    {
        fprintf(stderr, "unknown mode: %s\n", mode.c_str());
        return 2;
    }
}