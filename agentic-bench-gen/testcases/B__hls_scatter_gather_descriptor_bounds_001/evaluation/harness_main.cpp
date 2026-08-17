#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstring>

extern "C" int scatter_gather_copy(
    const unsigned char* src, unsigned int src_len,
    unsigned char* dst, unsigned int dst_len,
    const unsigned int* offsets, const unsigned int* lengths,
    unsigned int desc_count);

// Physical buffer sizes with room for canary regions after the logical
// region. Canary bytes are set to a sentinel and checked unchanged after
// the call, to detect out-of-bounds writes/reads.

static void fill_sequential(unsigned char* buf, unsigned int n, unsigned int start = 0) {
    for (unsigned int i = 0; i < n; ++i) buf[i] = (unsigned char)((start + i) & 0xFF);
}

static bool all_zero(const unsigned char* buf, unsigned int n) {
    for (unsigned int i = 0; i < n; ++i) if (buf[i] != 0) return false;
    return true;
}

static bool canary_intact(const unsigned char* buf, unsigned int start, unsigned int n, unsigned char sentinel) {
    for (unsigned int i = 0; i < n; ++i) if (buf[start + i] != sentinel) return false;
    return true;
}

// ---- FR1: full in-order copy, 3 descriptors, dst_len=30 ----
static void probe_FR1() {
    const unsigned int DST_LEN = 30;
    const unsigned int CANARY = 16;
    unsigned char dst[DST_LEN + CANARY];
    memset(dst, 0, DST_LEN);
    memset(dst + DST_LEN, 0xAA, CANARY);

    unsigned char src[DST_LEN];
    fill_sequential(src, DST_LEN, 0);

    unsigned int offsets[3] = {0, 10, 20};
    unsigned int lengths[3] = {10, 10, 10};

    int status = scatter_gather_copy(src, DST_LEN, dst, DST_LEN, offsets, lengths, 3);

    unsigned char expected[DST_LEN];
    fill_sequential(expected, DST_LEN, 0);

    bool dst_ok = (status == 0) && (memcmp(dst, expected, DST_LEN) == 0);
    bool canary_ok = canary_intact(dst, DST_LEN, CANARY, 0xAA);

    printf("RESULT FR1 status=%d dst_ok=%d canary_ok=%d\n", status, dst_ok ? 1 : 0, canary_ok ? 1 : 0);
}

// ---- FR2: 2 descriptors, contiguous sequential source consumption ----
static void probe_FR2() {
    const unsigned int DST_LEN = 10;
    const unsigned int CANARY = 16;
    unsigned char dst[DST_LEN + CANARY];
    memset(dst, 0, DST_LEN);
    memset(dst + DST_LEN, 0xAA, CANARY);

    unsigned char src[DST_LEN];
    fill_sequential(src, DST_LEN, 0);

    unsigned int offsets[2] = {0, 5};
    unsigned int lengths[2] = {5, 5};

    int status = scatter_gather_copy(src, DST_LEN, dst, DST_LEN, offsets, lengths, 2);

    unsigned char expected[DST_LEN];
    fill_sequential(expected, DST_LEN, 0);

    bool dst_ok = (status == 0) && (memcmp(dst, expected, DST_LEN) == 0);
    bool canary_ok = canary_intact(dst, DST_LEN, CANARY, 0xAA);

    printf("RESULT FR2 status=%d dst_ok=%d canary_ok=%d\n", status, dst_ok ? 1 : 0, canary_ok ? 1 : 0);
}

// ---- FR3: trivial call to prove linkage/compile/run works ----
static void probe_FR3() {
    const unsigned int DST_LEN = 8;
    unsigned char dst[DST_LEN];
    memset(dst, 0, DST_LEN);

    unsigned char src[DST_LEN];
    fill_sequential(src, DST_LEN, 0);

    unsigned int offsets[1] = {0};
    unsigned int lengths[1] = {4};

    int status = scatter_gather_copy(src, DST_LEN, dst, DST_LEN, offsets, lengths, 1);

    // We don't require particular correctness here beyond "it ran and returned".
    bool dst_ok = 1;
    bool canary_ok = 1;
    (void)status;

    printf("RESULT FR3 status=%d dst_ok=%d canary_ok=%d\n", status, dst_ok ? 1 : 0, canary_ok ? 1 : 0);
}

// ---- FR4: desc_count=0, no writes, offsets/lengths may be null ----
static void probe_FR4() {
    const unsigned int DST_LEN = 12;
    const unsigned int CANARY = 16;
    unsigned char dst[DST_LEN + CANARY];
    memset(dst, 0, DST_LEN);
    memset(dst + DST_LEN, 0xAA, CANARY);

    unsigned char src[4] = {1, 2, 3, 4};

    int status = scatter_gather_copy(src, 4, dst, DST_LEN, nullptr, nullptr, 0);

    bool dst_ok = (status == 0) && all_zero(dst, DST_LEN);
    bool canary_ok = canary_intact(dst, DST_LEN, CANARY, 0xAA);

    printf("RESULT FR4 status=%d dst_ok=%d canary_ok=%d\n", status, dst_ok ? 1 : 0, canary_ok ? 1 : 0);
}

// ---- SR1: 32-bit overflow wraparound descriptor ----
static void probe_SR1() {
    const unsigned int DST_LEN = 64;
    const unsigned int CANARY = 32;
    unsigned char dst[DST_LEN + CANARY];
    memset(dst, 0, DST_LEN);
    memset(dst + DST_LEN, 0xAA, CANARY);

    unsigned char src[64];
    fill_sequential(src, 64, 0);

    // offsets[0] + lengths[0] overflows 32-bit unsigned arithmetic:
    // 0xFFFFFFF0 + 0x20 = 0x100000010, wraps to 0x10 in 32-bit math.
    unsigned int offsets[1] = {0xFFFFFFF0u};
    unsigned int lengths[1] = {0x20u};

    int status = scatter_gather_copy(src, 64, dst, DST_LEN, offsets, lengths, 1);

    bool dst_ok = all_zero(dst, DST_LEN);
    bool canary_ok = canary_intact(dst, DST_LEN, CANARY, 0xAA);

    printf("RESULT SR1 status=%d dst_ok=%d canary_ok=%d\n", status, dst_ok ? 1 : 0, canary_ok ? 1 : 0);
}

// ---- SR2: valid, invalid, valid descriptors -> whole batch rejected ----
static void probe_SR2() {
    const unsigned int DST_LEN = 20;
    const unsigned int CANARY = 16;
    unsigned char dst[DST_LEN + CANARY];
    memset(dst, 0, DST_LEN);
    memset(dst + DST_LEN, 0xAA, CANARY);

    unsigned char src[64];
    fill_sequential(src, 64, 0);

    // descriptor0: valid, small (offset=0, len=4)
    // descriptor1: invalid (offset=dst_len-2=18, len=10 -> offset+len=28 > 20)
    // descriptor2: valid (offset=8, len=4)
    unsigned int offsets[3] = {0, DST_LEN - 2, 8};
    unsigned int lengths[3] = {4, 10, 4};

    int status = scatter_gather_copy(src, 64, dst, DST_LEN, offsets, lengths, 3);

    bool dst_ok = all_zero(dst, DST_LEN);
    bool canary_ok = canary_intact(dst, DST_LEN, CANARY, 0xAA);

    printf("RESULT SR2 status=%d dst_ok=%d canary_ok=%d\n", status, dst_ok ? 1 : 0, canary_ok ? 1 : 0);
}

// ---- SR3: cumulative source length exceeds src_len ----
static void probe_SR3() {
    const unsigned int SRC_LEN = 8;
    const unsigned int SRC_CANARY = 16;
    unsigned char src[SRC_LEN + SRC_CANARY];
    fill_sequential(src, SRC_LEN, 0);
    memset(src + SRC_LEN, 0xBB, SRC_CANARY);

    const unsigned int DST_LEN = 32;
    const unsigned int DST_CANARY = 16;
    unsigned char dst[DST_LEN + DST_CANARY];
    memset(dst, 0, DST_LEN);
    memset(dst + DST_LEN, 0xAA, DST_CANARY);

    // Both destination offsets are in-bounds individually, but cumulative
    // source consumption (8 + 8 = 16) exceeds src_len (8).
    unsigned int offsets[2] = {0, 8};
    unsigned int lengths[2] = {8, 8};

    int status = scatter_gather_copy(src, SRC_LEN, dst, DST_LEN, offsets, lengths, 2);

    bool dst_ok = all_zero(dst, DST_LEN);
    bool dst_canary_ok = canary_intact(dst, DST_LEN, DST_CANARY, 0xAA);
    bool src_canary_ok = canary_intact(src, SRC_LEN, SRC_CANARY, 0xBB);
    bool canary_ok = dst_canary_ok && src_canary_ok;

    printf("RESULT SR3 status=%d dst_ok=%d canary_ok=%d\n", status, dst_ok ? 1 : 0, canary_ok ? 1 : 0);
}

// ---- SR4: exact-boundary handling (offset+length==dst_len valid; +1 invalid) ----
static void probe_SR4() {
    const unsigned int DST_LEN = 16;
    const unsigned int CANARY = 16;

    unsigned char src[64];
    fill_sequential(src, 64, 0);

    // Sub-case A: offset = dst_len - length (exact fit at the tail).
    bool subA_ok;
    {
        unsigned char dst[DST_LEN + CANARY];
        memset(dst, 0, DST_LEN);
        memset(dst + DST_LEN, 0xAA, CANARY);

        unsigned int length = 4;
        unsigned int offset = DST_LEN - length; // 12
        unsigned int offsets[1] = {offset};
        unsigned int lengths[1] = {length};

        int status = scatter_gather_copy(src, 64, dst, DST_LEN, offsets, lengths, 1);

        unsigned char expected[DST_LEN];
        memset(expected, 0, DST_LEN);
        memcpy(expected + offset, src, length);

        bool copy_ok = (status == 0) && (memcmp(dst, expected, DST_LEN) == 0);
        bool canary_ok = canary_intact(dst, DST_LEN, CANARY, 0xAA);
        subA_ok = copy_ok && canary_ok;
    }

    // Sub-case B: offset = dst_len - length + 1 (one byte over the end).
    bool subB_ok;
    {
        unsigned char dst[DST_LEN + CANARY];
        memset(dst, 0, DST_LEN);
        memset(dst + DST_LEN, 0xAA, CANARY);

        unsigned int length = 4;
        unsigned int offset = DST_LEN - length + 1; // 13
        unsigned int offsets[1] = {offset};
        unsigned int lengths[1] = {length};

        int status = scatter_gather_copy(src, 64, dst, DST_LEN, offsets, lengths, 1);

        bool dst_ok = all_zero(dst, DST_LEN);
        bool canary_ok = canary_intact(dst, DST_LEN, CANARY, 0xAA);
        subB_ok = (status != 0) && dst_ok && canary_ok;
    }

    // Combine both sub-cases into a single overall status/dst_ok/canary_ok
    // triple for the RESULT line: status is nonzero if either sub-case
    // failed to behave as expected (encoded as 0 = both correct, else 1).
    int status = (subA_ok && subB_ok) ? 0 : 1;
    int dst_ok = (subA_ok && subB_ok) ? 1 : 0;
    int canary_ok = 1;

    printf("RESULT SR4 status=%d dst_ok=%d canary_ok=%d subA_ok=%d subB_ok=%d\n",
           status, dst_ok, canary_ok, subA_ok ? 1 : 0, subB_ok ? 1 : 0);
}

int main(int argc, char** argv) {
    if (argc < 2) {
        printf("RESULT NONE status=1 dst_ok=0 canary_ok=0\n");
        return 0;
    }

    const char* probe = argv[1];

    if (strcmp(probe, "FR1") == 0) probe_FR1();
    else if (strcmp(probe, "FR2") == 0) probe_FR2();
    else if (strcmp(probe, "FR3") == 0) probe_FR3();
    else if (strcmp(probe, "FR4") == 0) probe_FR4();
    else if (strcmp(probe, "SR1") == 0) probe_SR1();
    else if (strcmp(probe, "SR2") == 0) probe_SR2();
    else if (strcmp(probe, "SR3") == 0) probe_SR3();
    else if (strcmp(probe, "SR4") == 0) probe_SR4();
    else {
        printf("RESULT UNKNOWN status=1 dst_ok=0 canary_ok=0\n");
    }

    return 0;
}