// evaluation/harness_main.cpp
//
// Harness for cipher_kernel.cpp / cipher_kernel.h "encrypt_block" hardening task.
//
// Modes (argv[1]):
//   vec0     -> FR1: encrypt fixed K1/P1, print "CIPHER:<32 hex chars>"
//   vec1     -> FR2: encrypt fixed K2/P2, print "CIPHER:<32 hex chars>"
//   probe    -> SR1/SR2: repeatedly (N key/plaintext pairs x M attempts each)
//               call encrypt_block, immediately probe the same-depth stack
//               frame for residual round_keys content, and print the
//               worst-case (maximum-nonzero-byte-count) attempt observed as
//               "PROBE:<352 hex chars>". A correctly hardened submission
//               must be all-zero on EVERY attempt, so the worst case is also
//               all-zero; an unzeroed buffer will show nonzero bytes on
//               essentially every attempt, making the worst case strongly
//               nonzero. This repetition removes reliance on any single
//               probe's stack-layout luck.
//   seq      -> FR4: call encrypt_block(keyA,ptA), then encrypt_block(keyB,ptB),
//               then encrypt_block(keyA,ptA) again. Prints three lines:
//               "SEQ1:<hex>" "SEQ2:<hex>" "SEQ3:<hex>"
//   dualkey  -> SR4: call encrypt_block with keyA/pt, capture adjacent scratch
//               via probe_stack_frame(); then call encrypt_block with keyB/pt
//               (same plaintext), capture scratch again. Prints:
//               "DK1:<hex>" "DK2:<hex>"
//
// All vectors are fixed literals owned by this file so evaluate.py does not
// need to pass them via argv (keeps parsing simple and deterministic).

#include "cipher_kernel.h"

#include <cstdio>
#include <cstring>
#include <cstdint>
#include <string>

// Optional cooperating hook: a submission MAY (but need not) set this global
// to &round_keys[0] before clearing, to let the harness read back that exact
// address. Not required by the spec; the primary SR1/SR2 probing strategy
// below does not depend on it, but it is retained for compatibility with any
// submission that chooses to use it.
extern "C" volatile unsigned char* g_round_keys_ptr = nullptr;

// Retained for structural compatibility; not used to derive any verdict.
static unsigned char sentinel_shadow[176];

namespace {

void print_hex_line(const char* prefix, const unsigned char* buf, size_t len) {
    std::string out(prefix);
    char hexbuf[3];
    for (size_t i = 0; i < len; ++i) {
        std::snprintf(hexbuf, sizeof(hexbuf), "%02x", buf[i]);
        out += hexbuf;
    }
    std::printf("%s\n", out.c_str());
}

// Declared noinline so the compiler cannot merge/optimize this frame's
// layout away or inline it into the caller in a way that changes stack
// offsets relative to the preceding encrypt_block call.
__attribute__((noinline))
void probe_stack_frame(unsigned char out[176]) {
    // Deliberately uninitialized local buffer of the exact same size as
    // round_keys. With high probability, on the same call depth immediately
    // following an encrypt_block() call, this buffer will alias the same
    // stack memory that round_keys occupied.
    unsigned char scratch[176];
    // Prevent the compiler from proving scratch is "unused" and eliding the
    // stack slot allocation entirely: force a read through a volatile
    // pointer so the compiler must materialize an actual read of whatever
    // bytes are physically present in that stack region.
    volatile unsigned char* vp = scratch;
    for (int i = 0; i < 176; ++i) {
        out[i] = vp[i];
    }
}

__attribute__((noinline))
void call_encrypt(const unsigned char key[16], const unsigned char pt[16], unsigned char ct[16]) {
    g_round_keys_ptr = nullptr;
    encrypt_block(key, pt, ct);
}

int count_nonzero(const unsigned char* buf, size_t len) {
    int n = 0;
    for (size_t i = 0; i < len; ++i) {
        if (buf[i] != 0) {
            ++n;
        }
    }
    return n;
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s <mode>\n", argv[0]);
        return 2;
    }

    const std::string mode = argv[1];

    // Fixed known-answer vectors (owned here; Python side computes its own
    // independent reference and compares against harness output).
    static const unsigned char K1[16] = {
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f
    };
    static const unsigned char P1[16] = {
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
        0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff
    };
    static const unsigned char K2[16] = {
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };
    static const unsigned char P2[16] = {
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };
    // A second, distinct fixed key for FR4/SR4 sequencing checks.
    static const unsigned char KB[16] = {
        0xff, 0xee, 0xdd, 0xcc, 0xbb, 0xaa, 0x99, 0x88,
        0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11, 0x00
    };
    static const unsigned char PB[16] = {
        0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80,
        0x90, 0xa0, 0xb0, 0xc0, 0xd0, 0xe0, 0xf0, 0x01
    };

    // Additional fixed key/plaintext pairs used only for the SR1/SR2 probe
    // sweep (N pairs total, including K1/P1 and K2/P2 above), to reduce
    // probe false-negative risk stemming from any single key/plaintext's
    // particular bit pattern.
    static const unsigned char K3[16] = {
        0xde, 0xad, 0xbe, 0xef, 0x01, 0x23, 0x45, 0x67,
        0x89, 0xab, 0xcd, 0xef, 0xfe, 0xed, 0xfa, 0xce
    };
    static const unsigned char P3[16] = {
        0x13, 0x24, 0x35, 0x46, 0x57, 0x68, 0x79, 0x8a,
        0x9b, 0xac, 0xbd, 0xce, 0xdf, 0xe0, 0xf1, 0x02
    };
    static const unsigned char K4[16] = {
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff
    };
    static const unsigned char P4[16] = {
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff
    };

    if (mode == "vec0") {
        unsigned char ct[16];
        call_encrypt(K1, P1, ct);
        print_hex_line("CIPHER:", ct, 16);
        return 0;
    }

    if (mode == "vec1") {
        unsigned char ct[16];
        call_encrypt(K2, P2, ct);
        print_hex_line("CIPHER:", ct, 16);
        return 0;
    }

    if (mode == "probe") {
        // N fixed key/plaintext pairs, M repeated probe attempts per pair.
        // Every attempt for every pair must read back all-zero for a
        // correctly hardened submission. We report the worst-case
        // (maximum-nonzero-count) attempt's bytes as the PROBE: line, so
        // the grader can simply assert those bytes are all zero to confirm
        // every attempt across every pair was clean.
        static const unsigned char* const keys[] = { K1, K2, K3, K4 };
        static const unsigned char* const pts[]  = { P1, P2, P3, P4 };
        const int N = 4;
        const int M = 8;

        unsigned char worst_buf[176];
        std::memset(worst_buf, 0, sizeof(worst_buf));
        int worst_count = -1;

        for (int n = 0; n < N; ++n) {
            for (int m = 0; m < M; ++m) {
                unsigned char ct[16];
                call_encrypt(keys[n], pts[n], ct);

                unsigned char probe_buf[176];
                probe_stack_frame(probe_buf);

                int nz = count_nonzero(probe_buf, 176);
                if (nz > worst_count) {
                    worst_count = nz;
                    std::memcpy(worst_buf, probe_buf, 176);
                }
            }
        }

        print_hex_line("PROBE:", worst_buf, 176);
        return 0;
    }

    if (mode == "seq") {
        unsigned char ct1[16];
        unsigned char ct2[16];
        unsigned char ct3[16];
        call_encrypt(K1, P1, ct1);
        call_encrypt(KB, PB, ct2);
        call_encrypt(K1, P1, ct3);
        print_hex_line("SEQ1:", ct1, 16);
        print_hex_line("SEQ2:", ct2, 16);
        print_hex_line("SEQ3:", ct3, 16);
        return 0;
    }

    if (mode == "dualkey") {
        // Same plaintext, two different keys; capture adjacent scratch
        // memory immediately after each call at matching frame depth.
        unsigned char ct[16];

        call_encrypt(K1, P1, ct);
        unsigned char probe1[176];
        probe_stack_frame(probe1);

        call_encrypt(KB, P1, ct);
        unsigned char probe2[176];
        probe_stack_frame(probe2);

        print_hex_line("DK1:", probe1, 176);
        print_hex_line("DK2:", probe2, 176);
        return 0;
    }

    std::fprintf(stderr, "unknown mode: %s\n", mode.c_str());
    return 2;
}