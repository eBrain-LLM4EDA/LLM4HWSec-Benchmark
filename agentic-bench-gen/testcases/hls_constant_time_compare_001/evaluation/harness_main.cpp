#include "mac_verify.h"

#include <cstdio>
#include <cstdlib>
#include <cstddef>
#include <new>
#include <random>

// ---------------------------------------------------------------------
// Global allocation counter for SR3. We override the global operator new
// / operator new[] so that any heap allocation performed anywhere in the
// process (including, in particular, inside verify()) during the
// measurement window increments this counter. Plain C arrays on the
// stack do not go through these operators, so precomputing test vectors
// as local arrays before the measurement window does not perturb the
// count.
// ---------------------------------------------------------------------
static unsigned long g_alloc_count = 0;

void* operator new(std::size_t size) {
    ++g_alloc_count;
    void* p = std::malloc(size ? size : 1);
    if (!p) {
        std::fprintf(stderr, "operator new: allocation failed\n");
        std::exit(1);
    }
    return p;
}

void* operator new[](std::size_t size) {
    ++g_alloc_count;
    void* p = std::malloc(size ? size : 1);
    if (!p) {
        std::fprintf(stderr, "operator new[]: allocation failed\n");
        std::exit(1);
    }
    return p;
}

void operator delete(void* p) noexcept {
    std::free(p);
}

void operator delete(void* p, std::size_t) noexcept {
    std::free(p);
}

void operator delete[](void* p) noexcept {
    std::free(p);
}

void operator delete[](void* p, std::size_t) noexcept {
    std::free(p);
}

// ---------------------------------------------------------------------
// Fixed-size plain-array vector containers (no STL containers so that we
// don't introduce incidental heap allocations before/after the
// measurement window).
// ---------------------------------------------------------------------

static const int NUM_BASE_TAGS = 25;
static const int NUM_POSITIONS = 16;
static const int NUM_MULTI_MISMATCH = 25;

// FR1: identical pairs
static unsigned char fr1_computed[NUM_BASE_TAGS][16];
static unsigned char fr1_received[NUM_BASE_TAGS][16];

// FR2: single-byte mismatch cases: NUM_BASE_TAGS * NUM_POSITIONS
static const int FR2_SINGLE_TOTAL = NUM_BASE_TAGS * NUM_POSITIONS;
static unsigned char fr2_single_computed[FR2_SINGLE_TOTAL][16];
static unsigned char fr2_single_received[FR2_SINGLE_TOTAL][16];

// FR2: multi-byte mismatch cases
static unsigned char fr2_multi_computed[NUM_MULTI_MISMATCH][16];
static unsigned char fr2_multi_received[NUM_MULTI_MISMATCH][16];

// FR4: fixed edge-case combos
struct Fr4Case {
    unsigned char computed[16];
    unsigned char received[16];
    bool expected;
};
static const int FR4_TOTAL = 8;
static Fr4Case fr4_cases[FR4_TOTAL];

// SR3: precomputed pairs to cycle through during the measurement window
static const int SR3_NUM_PAIRS = 50;
static const int SR3_NUM_CALLS = 1000;
static unsigned char sr3_computed[SR3_NUM_PAIRS][16];
static unsigned char sr3_received[SR3_NUM_PAIRS][16];

static void fill_random_tag(std::mt19937& rng, unsigned char tag[16]) {
    std::uniform_int_distribution<int> dist(0, 255);
    for (int i = 0; i < 16; ++i) {
        tag[i] = static_cast<unsigned char>(dist(rng));
    }
}

int main() {
    std::mt19937 rng(1234567u);
    std::uniform_int_distribution<int> byte_dist(0, 255);
    std::uniform_int_distribution<int> pos_dist(0, 15);
    std::uniform_int_distribution<int> nonzero_xor_dist(1, 255);

    // -------------------------------------------------------------
    // Build FR1 vectors: identical (computed, received) pairs
    // -------------------------------------------------------------
    for (int i = 0; i < NUM_BASE_TAGS; ++i) {
        fill_random_tag(rng, fr1_computed[i]);
        for (int b = 0; b < 16; ++b) {
            fr1_received[i][b] = fr1_computed[i][b];
        }
    }

    // -------------------------------------------------------------
    // Build FR2 single-byte-mismatch vectors: 25 base tags, each with a
    // single-byte flip at each of the 16 positions.
    // -------------------------------------------------------------
    unsigned char fr2_base[NUM_BASE_TAGS][16];
    for (int i = 0; i < NUM_BASE_TAGS; ++i) {
        fill_random_tag(rng, fr2_base[i]);
    }

    int idx = 0;
    for (int i = 0; i < NUM_BASE_TAGS; ++i) {
        for (int pos = 0; pos < NUM_POSITIONS; ++pos) {
            for (int b = 0; b < 16; ++b) {
                fr2_single_computed[idx][b] = fr2_base[i][b];
                fr2_single_received[idx][b] = fr2_base[i][b];
            }
            unsigned char xor_val = static_cast<unsigned char>(nonzero_xor_dist(rng));
            fr2_single_received[idx][pos] = static_cast<unsigned char>(fr2_single_received[idx][pos] ^ xor_val);
            ++idx;
        }
    }

    // -------------------------------------------------------------
    // Build FR2 multi-byte-mismatch vectors
    // -------------------------------------------------------------
    for (int i = 0; i < NUM_MULTI_MISMATCH; ++i) {
        fill_random_tag(rng, fr2_multi_computed[i]);
        for (int b = 0; b < 16; ++b) {
            fr2_multi_received[i][b] = fr2_multi_computed[i][b];
        }
        // Flip a random number of distinct positions (between 2 and 5)
        std::uniform_int_distribution<int> num_flips_dist(2, 5);
        int num_flips = num_flips_dist(rng);
        bool flipped[16] = { false };
        int flips_done = 0;
        int guard = 0;
        while (flips_done < num_flips && guard < 1000) {
            int p = pos_dist(rng);
            ++guard;
            if (!flipped[p]) {
                unsigned char xor_val = static_cast<unsigned char>(nonzero_xor_dist(rng));
                fr2_multi_received[i][p] = static_cast<unsigned char>(fr2_multi_received[i][p] ^ xor_val);
                flipped[p] = true;
                ++flips_done;
            }
        }
    }

    // -------------------------------------------------------------
    // Build FR4 edge-case combos: all-zero and all-0xFF tags, as
    // computed/received, in every equal and unequal combination.
    // -------------------------------------------------------------
    unsigned char all_zero[16];
    unsigned char all_ff[16];
    for (int b = 0; b < 16; ++b) {
        all_zero[b] = 0x00;
        all_ff[b] = 0xFF;
    }

    // Case 0: zero vs zero -> true
    for (int b = 0; b < 16; ++b) { fr4_cases[0].computed[b] = all_zero[b]; fr4_cases[0].received[b] = all_zero[b]; }
    fr4_cases[0].expected = true;

    // Case 1: ff vs ff -> true
    for (int b = 0; b < 16; ++b) { fr4_cases[1].computed[b] = all_ff[b]; fr4_cases[1].received[b] = all_ff[b]; }
    fr4_cases[1].expected = true;

    // Case 2: zero vs ff -> false
    for (int b = 0; b < 16; ++b) { fr4_cases[2].computed[b] = all_zero[b]; fr4_cases[2].received[b] = all_ff[b]; }
    fr4_cases[2].expected = false;

    // Case 3: ff vs zero -> false
    for (int b = 0; b < 16; ++b) { fr4_cases[3].computed[b] = all_ff[b]; fr4_cases[3].received[b] = all_zero[b]; }
    fr4_cases[3].expected = false;

    // Case 4: zero vs random-nonzero-first-byte -> false
    {
        unsigned char rnd[16];
        for (int b = 0; b < 16; ++b) rnd[b] = all_zero[b];
        rnd[0] = 0x01;
        for (int b = 0; b < 16; ++b) { fr4_cases[4].computed[b] = all_zero[b]; fr4_cases[4].received[b] = rnd[b]; }
        fr4_cases[4].expected = false;
    }

    // Case 5: ff vs random-changed-last-byte -> false
    {
        unsigned char rnd[16];
        for (int b = 0; b < 16; ++b) rnd[b] = all_ff[b];
        rnd[15] = 0xFE;
        for (int b = 0; b < 16; ++b) { fr4_cases[5].computed[b] = all_ff[b]; fr4_cases[5].received[b] = rnd[b]; }
        fr4_cases[5].expected = false;
    }

    // Case 6: zero vs zero with one middle byte changed -> false
    {
        unsigned char rnd[16];
        for (int b = 0; b < 16; ++b) rnd[b] = all_zero[b];
        rnd[8] = 0x80;
        for (int b = 0; b < 16; ++b) { fr4_cases[6].computed[b] = all_zero[b]; fr4_cases[6].received[b] = rnd[b]; }
        fr4_cases[6].expected = false;
    }

    // Case 7: ff computed vs ff received but one byte cleared -> false
    {
        unsigned char rnd[16];
        for (int b = 0; b < 16; ++b) rnd[b] = all_ff[b];
        rnd[3] = 0x00;
        for (int b = 0; b < 16; ++b) { fr4_cases[7].computed[b] = all_ff[b]; fr4_cases[7].received[b] = rnd[b]; }
        fr4_cases[7].expected = false;
    }

    // -------------------------------------------------------------
    // Build SR3 precomputed pairs: mix of matching and mismatching tags,
    // constructed entirely before the measurement window begins.
    // -------------------------------------------------------------
    for (int i = 0; i < SR3_NUM_PAIRS; ++i) {
        fill_random_tag(rng, sr3_computed[i]);
        for (int b = 0; b < 16; ++b) {
            sr3_received[i][b] = sr3_computed[i][b];
        }
        if (i % 2 == 1) {
            int p = pos_dist(rng);
            unsigned char xor_val = static_cast<unsigned char>(nonzero_xor_dist(rng));
            sr3_received[i][p] = static_cast<unsigned char>(sr3_received[i][p] ^ xor_val);
        }
    }

    // =================================================================
    // Run FR1: identical pairs must all verify true
    // =================================================================
    {
        int pass = 0;
        int total = NUM_BASE_TAGS;
        for (int i = 0; i < NUM_BASE_TAGS; ++i) {
            bool result = verify(fr1_computed[i], fr1_received[i]);
            if (result == true) {
                ++pass;
            }
        }
        std::printf("FR1_RESULT %d %d\n", pass, total);
    }

    // =================================================================
    // Run FR2: all single-byte and multi-byte mismatch cases must be
    // rejected (verify() returns false).
    // =================================================================
    {
        int pass = 0;
        int total = FR2_SINGLE_TOTAL + NUM_MULTI_MISMATCH;

        for (int i = 0; i < FR2_SINGLE_TOTAL; ++i) {
            bool result = verify(fr2_single_computed[i], fr2_single_received[i]);
            if (result == false) {
                ++pass;
            }
        }

        for (int i = 0; i < NUM_MULTI_MISMATCH; ++i) {
            bool result = verify(fr2_multi_computed[i], fr2_multi_received[i]);
            if (result == false) {
                ++pass;
            }
        }

        std::printf("FR2_RESULT %d %d\n", pass, total);
    }

    // =================================================================
    // Run FR4: all-zero / all-0xFF edge cases plus near-edge variants
    // =================================================================
    {
        int pass = 0;
        int total = FR4_TOTAL;
        for (int i = 0; i < FR4_TOTAL; ++i) {
            bool result = verify(fr4_cases[i].computed, fr4_cases[i].received);
            if (result == fr4_cases[i].expected) {
                ++pass;
            }
        }
        std::printf("FR4_RESULT %d %d\n", pass, total);
    }

    // =================================================================
    // Run SR3: measure heap allocations strictly during repeated verify()
    // invocations over precomputed stack-array pairs. No other allocating
    // operation should occur inside this loop.
    // =================================================================
    {
        g_alloc_count = 0;
        volatile bool sink = false; // prevent the loop from being optimized away
        for (int call = 0; call < SR3_NUM_CALLS; ++call) {
            int idx2 = call % SR3_NUM_PAIRS;
            bool result = verify(sr3_computed[idx2], sr3_received[idx2]);
            sink = result;
        }
        (void)sink;
        std::printf("SR3_ALLOC_COUNT %lu\n", g_alloc_count);
    }

    return 0;
}