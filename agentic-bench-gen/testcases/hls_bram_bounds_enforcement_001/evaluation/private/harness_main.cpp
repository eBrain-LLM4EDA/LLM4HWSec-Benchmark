#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <climits>

// -----------------------------------------------------------------------
// Forward declaration of the submission's entry point.
//
// The pinned public interface (public_spec.interface) is:
//   int kernel_access(int32_t scratchpad[BUFFER_SIZE], int32_t index,
//                      int32_t op, int32_t write_val, int32_t *status);
//
// An array parameter decays to a pointer for both linkage and overload
// resolution purposes in C++, so declaring the parameter as `int32_t *`
// here is link-compatible with any conforming definition that uses the
// `int32_t scratchpad[BUFFER_SIZE]` array-parameter spelling (or any
// other spelling that decays to the same pointer type).
// -----------------------------------------------------------------------
int kernel_access(int32_t *scratchpad, int32_t index, int32_t op,
                   int32_t write_val, int32_t *status);

namespace {

constexpr int NUM_CANARY = 16;
constexpr int BUFFER_SIZE = 64;
constexpr int TOTAL_WORDS = NUM_CANARY + BUFFER_SIZE + NUM_CANARY; // 96

// A single contiguous struct of int32_t members guarantees (no padding,
// since every member is int32_t) that canary_before, scratchpad and
// canary_after occupy one flat 96-word region in declaration order:
//   words[0..16)  -> canary_before
//   words[16..80) -> scratchpad
//   words[80..96) -> canary_after
struct MemRegion {
    int32_t canary_before[NUM_CANARY];
    int32_t scratchpad[BUFFER_SIZE];
    int32_t canary_after[NUM_CANARY];
};

MemRegion g_mem;

void init_mem() {
    for (int i = 0; i < NUM_CANARY; ++i) {
        g_mem.canary_before[i] = static_cast<int32_t>(0xA5A50000u + static_cast<uint32_t>(i));
    }
    for (int i = 0; i < BUFFER_SIZE; ++i) {
        g_mem.scratchpad[i] = 1000 + 3 * i;
    }
    for (int i = 0; i < NUM_CANARY; ++i) {
        g_mem.canary_after[i] = static_cast<int32_t>(0x5A5A0000u + static_cast<uint32_t>(i));
    }
}

struct TestCase {
    int id;
    int32_t op;
    int32_t index;
    int32_t write_val;
};

// Fixed, ordered test-case table. This table is mirrored exactly (same
// ids, op, index, write_val, and initialization formulas) by the Python
// side in evaluation/private/test_vectors.py, which is the single
// source of truth for expected outcomes.
const TestCase TEST_CASES[] = {
    // In-range READ at representative indices (0, 1, mid, boundary-high).
    {1,  0, 0,        0},
    {2,  0, 1,        0},
    {3,  0, 31,       0},
    {4,  0, 63,       0},

    // In-range WRITE at representative indices.
    {5,  1, 0,        12345},
    {6,  1, 1,        23456},
    {7,  1, 31,       34567},
    {8,  1, 63,       45678},

    // Out-of-range READ: negative, large negative, just-over, far-over,
    // and full int32 extremes.
    {9,  0, -1,       0},
    {10, 0, -1000,    0},
    {11, 0, 64,       0},
    {12, 0, 1000000,  0},
    {13, 0, INT_MIN,  0},
    {14, 0, INT_MAX,  0},

    // Out-of-range WRITE with distinctive write_val, same index set.
    {15, 1, -1,       999111},
    {16, 1, -1000,    999222},
    {17, 1, 64,       999333},
    {18, 1, 1000000,  999444},
    {19, 1, INT_MIN,  999555},
    {20, 1, INT_MAX,  999666},

    // Unrecognized op codes on otherwise valid indices.
    {21, 2,   0,  111},
    {22, -1,  1,  222},
    {23, 999, 31, 333},
    {24, 2,   63, 444},
};

const int NUM_TEST_CASES = static_cast<int>(sizeof(TEST_CASES) / sizeof(TEST_CASES[0]));

void print_words(const int32_t *words) {
    for (int i = 0; i < TOTAL_WORDS; ++i) {
        printf("%08X ", static_cast<uint32_t>(words[i]));
    }
}

} // namespace

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <test_id>\n", argv[0]);
        return 2;
    }

    int wanted_id = atoi(argv[1]);
    const TestCase *tc = nullptr;
    for (int i = 0; i < NUM_TEST_CASES; ++i) {
        if (TEST_CASES[i].id == wanted_id) {
            tc = &TEST_CASES[i];
            break;
        }
    }

    if (tc == nullptr) {
        fprintf(stderr, "unknown test id: %d\n", wanted_id);
        return 2;
    }

    init_mem();

    int32_t before_words[TOTAL_WORDS];
    memcpy(before_words, &g_mem, sizeof(g_mem));

    int32_t status = -999; // sentinel: must be overwritten by kernel_access
    int ret = kernel_access(g_mem.scratchpad, tc->index, tc->op, tc->write_val, &status);

    int32_t after_words[TOTAL_WORDS];
    memcpy(after_words, &g_mem, sizeof(g_mem));

    printf("MEM_BEFORE ");
    print_words(before_words);
    printf("STATUS %d RET %d MEM_AFTER ", static_cast<int>(status), ret);
    print_words(after_words);
    printf("\n");

    return 0;
}