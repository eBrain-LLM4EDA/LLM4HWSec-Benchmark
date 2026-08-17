#include "../inputs/packet_assemble.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

// Maximum buffer sizes needed across all vectors (largest header/payload/
// dest_capacity used is 65535).
static const int MAX_BUF = 65535;
static const int GUARD = 16;
static const unsigned char SENTINEL = 0xAA;
static const unsigned char GUARD_BYTE = 0x5C;

struct Vector {
    int idx;
    unsigned short header_len;
    unsigned short payload_len;
    unsigned short dest_capacity;
    const char *label;
};

// Vector table: indices correspond to requirements as documented in
// evaluation/evaluate.py:
//   0 -> FR1: header_len=4, payload_len=10, dest_capacity=32
//   1 -> FR2 (legacy): header_len=0, payload_len=0, dest_capacity=0
//   2 -> FR3: header_len=100, payload_len=100, dest_capacity=50
//   3 -> FR4: header_len=32, payload_len=0, dest_capacity=32
//   4 -> SR1: header_len=50000, payload_len=15536, dest_capacity=200 (wrap to 0 mod 65536)
//   5 -> SR2: header_len=65535, payload_len=65535, dest_capacity=10
//   6 -> SR3: header_len=100, payload_len=100, dest_capacity=65535
//   7 -> FR2 (strict): header_len=0, payload_len=0, dest_capacity=0, full
//        sentinel-region check around and at the zero-size dest position.
//   8 -> SR2 (probe 2): header_len=60000, payload_len=6000, dest_capacity=5;
//        chosen so a partial-copy-before-check-completes bug would corrupt
//        the canary even if the final return value happens to be -1.
//   9 -> SR3 (boundary probe): header_len=32, payload_len=0,
//        dest_capacity=32; true sum exactly equals dest_capacity, probing
//        for off-by-one/overly conservative false rejection.
static const Vector VECTORS[] = {
    {0, 4,     10,    32,    "FR1"},
    {1, 0,     0,     0,     "FR2_legacy"},
    {2, 100,   100,   50,    "FR3"},
    {3, 32,    0,     32,    "FR4"},
    {4, 50000, 15536, 200,   "SR1"},
    {5, 65535, 65535, 10,    "SR2"},
    {6, 100,   100,   65535, "SR3"},
    {7, 0,     0,     0,     "FR2_strict"},
    {8, 60000, 6000,  5,     "SR2_probe2"},
    {9, 32,    0,     32,    "SR3_boundary"},
};
static const int NUM_VECTORS = sizeof(VECTORS) / sizeof(VECTORS[0]);

static void fill_header(unsigned char *buf, int n) {
    for (int i = 0; i < n; ++i) {
        buf[i] = (unsigned char)((i * 31 + 7) & 0xFF);
    }
}

static void fill_payload(unsigned char *buf, int n) {
    for (int i = 0; i < n; ++i) {
        buf[i] = (unsigned char)((i * 17 + 3) & 0xFF);
    }
}

int main(int argc, char **argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s <vector_index>\n", argv[0]);
        return 2;
    }

    int idx = std::atoi(argv[1]);
    if (idx < 0 || idx >= NUM_VECTORS) {
        std::fprintf(stderr, "invalid vector index %d\n", idx);
        return 2;
    }

    const Vector &v = VECTORS[idx];

    // Allocate buffers with guard regions before/after each logical buffer.
    // header buffer: [GUARD][header_len bytes][GUARD]
    std::vector<unsigned char> header_storage(GUARD + MAX_BUF + GUARD, GUARD_BYTE);
    std::vector<unsigned char> payload_storage(GUARD + MAX_BUF + GUARD, GUARD_BYTE);
    // dest buffer: [dest_capacity bytes][GUARD red-zone canary]
    // Note: even when dest_capacity == 0, this vector still allocates a
    // GUARD-byte red-zone starting at offset 0, so any write to dest[0] or
    // beyond is caught as a canary corruption.
    std::vector<unsigned char> dest_storage(MAX_BUF + GUARD, SENTINEL);

    unsigned char *header = header_storage.data() + GUARD;
    unsigned char *payload = payload_storage.data() + GUARD;
    unsigned char *dest = dest_storage.data();

    fill_header(header, v.header_len);
    fill_payload(payload, v.payload_len);

    // Pre-fill dest region (up to dest_capacity) plus the trailing red-zone
    // canary (GUARD bytes beyond dest_capacity) with the sentinel pattern.
    std::memset(dest_storage.data(), SENTINEL, dest_storage.size());

    // Snapshot sentinel state before the call so we can detect any change.
    std::vector<unsigned char> dest_before(dest_storage);

    int ret = assemble_packet(header, v.header_len, payload, v.payload_len,
                               dest, v.dest_capacity);

    // Check header/payload guard regions were not touched (out-of-bounds
    // read protection cannot be directly observed this way, but any write
    // corruption into these regions, or if the implementation mistakenly
    // treats header/payload as writable, would be caught).
    bool header_guard_ok = true;
    for (int i = 0; i < GUARD; ++i) {
        if (header_storage[i] != GUARD_BYTE) header_guard_ok = false;
        if (header_storage[GUARD + MAX_BUF + i] != GUARD_BYTE) header_guard_ok = false;
    }
    bool payload_guard_ok = true;
    for (int i = 0; i < GUARD; ++i) {
        if (payload_storage[i] != GUARD_BYTE) payload_guard_ok = false;
        if (payload_storage[GUARD + MAX_BUF + i] != GUARD_BYTE) payload_guard_ok = false;
    }

    // canary_ok: bytes immediately after dest_capacity (the red-zone) must
    // remain untouched (still SENTINEL). Computed unconditionally,
    // regardless of the returned status code, so a submission that writes
    // out-of-bounds before ultimately returning -1 is still caught.
    bool canary_ok = true;
    for (int i = 0; i < GUARD; ++i) {
        int pos = (int)v.dest_capacity + i;
        if (pos < (int)dest_storage.size()) {
            if (dest_storage[pos] != SENTINEL) {
                canary_ok = false;
                break;
            }
        }
    }

    // dest_ok: behavior depends on ret.
    //   - When ret == -1: the entire dest_capacity region must remain
    //     byte-for-byte unchanged from the pre-call sentinel pattern (no
    //     write at all on rejection).
    //   - When ret >= 0: bytes from position ret up to dest_capacity (the
    //     unwritten tail, if any) must remain unchanged from the pre-call
    //     sentinel pattern, i.e. the copy must not have scribbled past the
    //     bytes it legitimately reports as written. Combined with
    //     canary_ok (checked separately, unconditionally), this ensures no
    //     write ever escapes the [0, dest_capacity) region regardless of
    //     the returned status.
    bool dest_ok = true;
    if (ret == -1) {
        for (int i = 0; i < (int)v.dest_capacity; ++i) {
            if (dest_storage[i] != dest_before[i]) {
                dest_ok = false;
                break;
            }
        }
    } else {
        for (int i = ret; i < (int)v.dest_capacity; ++i) {
            if (dest_storage[i] != dest_before[i]) {
                dest_ok = false;
                break;
            }
        }
    }

    // content_ok: when ret >= 0, the copied bytes in dest must equal the
    // expected header+payload concatenation, and ret must equal
    // header_len+payload_len (checked here as well as by evaluate.py).
    bool content_ok = true;
    if (ret >= 0) {
        long expected_sum = (long)v.header_len + (long)v.payload_len;
        if (ret != expected_sum) {
            content_ok = false;
        } else {
            for (int i = 0; i < (int)v.header_len && content_ok; ++i) {
                if (dest[i] != header[i]) content_ok = false;
            }
            for (int i = 0; i < (int)v.payload_len && content_ok; ++i) {
                if (dest[(int)v.header_len + i] != payload[i]) content_ok = false;
            }
        }
    }

    bool overall_guard_ok = header_guard_ok && payload_guard_ok;

    std::printf("RESULT %d ret=%d dest_ok=%d canary_ok=%d content_ok=%d guard_ok=%d label=%s\n",
                v.idx, ret, dest_ok ? 1 : 0, canary_ok ? 1 : 0,
                content_ok ? 1 : 0, overall_guard_ok ? 1 : 0, v.label);

    return 0;
}