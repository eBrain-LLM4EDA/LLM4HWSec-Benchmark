// evaluation/harness_main.cpp
//
// Harness for lookup_kernel.cpp. Two build modes:
//
//   Plain build (no -DTRACE_MODE):
//     g++ -std=c++11 -O0 -o harness_plain evaluation/table_accessor.cpp evaluation/harness_main.cpp
//   In this mode, evaluation/table_accessor.cpp is the ONLY translation unit
//   that #includes inputs/lookup_kernel.cpp; this file merely declares the
//   pinned `lookup` entry point as an `extern` symbol and links against it.
//   TRACE_ACCESS in the kernel compiles to whatever no-op the kernel itself
//   defines (per the public interface contract) in this mode. This build is
//   used for FR1/SR4 (exhaustive output correctness).
//
//   IMPORTANT (fix): FR1/SR4 do NOT compare against an independently
//   hardcoded 16-byte constant array. The public interface only pins the
//   table's name (`table`), element type (`uint8_t`), and size (16
//   entries) -- it does NOT require a hardened submission to keep the
//   exact byte values the baseline happened to ship with. Hardcoding an
//   external oracle array here would falsely reject any correct hardened
//   submission that (legitimately) keeps different table contents.
//
//   Instead, the reference for each (value,key) pair is derived from the
//   SAME `table` object the submission itself defines, read back through
//   harness_get_table_entry(int i) (an extern "C" accessor defined in
//   evaluation/table_accessor.cpp, the sole translation unit that
//   #includes inputs/lookup_kernel.cpp in the plain build, so it can see
//   the submission's `table` symbol regardless of whether that symbol has
//   internal or external linkage in the submission's own source). This
//   file declares:
//
//       extern "C" uint8_t harness_get_table_entry(int i);
//
//   and computes expected = harness_get_table_entry((value ^ key) & 0x0F)
//   for every one of the 65536 (value,key) pairs. This is the SAME table
//   contents the submission's own lookup() must have used, so FR1/SR4
//   PASS for any submission that faithfully implements
//   table[(value^key)&0x0F] against its own table -- regardless of what
//   specific bytes that table holds -- while still FAILing any mutant
//   that breaks the substitution formula itself (e.g. ignores key, uses
//   only value, off-by-one masks, wrong xor order, returns a constant,
//   etc.), since such a mutant's return value will differ from
//   harness_get_table_entry((value^key)&0x0F) for at least one pair.
//
//   Trace build (-DTRACE_MODE):
//     g++ -std=c++11 -DTRACE_MODE -O0 -o harness_trace evaluation/harness_main.cpp
//   In this mode this file is compiled ALONE (no other translation unit is
//   passed to the compiler) and #includes inputs/lookup_kernel.cpp directly
//   as source -- exactly once -- after redefining TRACE_ACCESS, so every
//   table access the kernel performs is captured into a global trace
//   buffer we can inspect. No other file re-includes the kernel source in
//   this build, avoiding any duplicate-symbol or duplicate-include hazard
//   regardless of how the submission structures its own helper
//   declarations/definitions.
//
// Usage: harness <mode> where mode is one of: fr1, trace, fr3count
//
//   fr1:      exhaustively iterate value=0..255, key=0..255, print
//             "FR1_MISMATCH <value> <key> <got>" for every mismatch found
//             against harness_get_table_entry((value^key)&0x0F) -- i.e.
//             the submission's OWN compiled table contents, read live --
//             then print "FR1_MISMATCHES <n>" and "FR1_TOTAL 65536".
//
//   trace:    requires TRACE_MODE build. Reads pairs from stdin, one pair per
//             line as "<value> <key>". For each pair, resets the trace
//             buffer, calls lookup(value,key), and prints a line:
//             "TRACE <idx> <count> <comma-separated-indices>"
//             where <idx> is the 0-based input line number.
//
//   fr3count: requires TRACE_MODE build. Same stdin format as 'trace' but
//             prints only:
//             "COUNT <idx> <count>"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

#ifdef TRACE_MODE

// Global trace buffer capturing every table index touched during the most
// recent call to lookup(). Sized generously; the kernel under test is
// expected to touch at most 16 indices, but we allow headroom to detect
// buggy/mutant kernels that read far more than that without crashing.
static int g_trace[4096];
static int g_trace_len = 0;

// Redefine TRACE_ACCESS before including the kernel source so every access
// the kernel performs gets recorded. The kernel file itself only defines
// TRACE_ACCESS if it is not already defined (guarded by #ifndef), so this
// definition takes precedence when we include the kernel source here.
#define TRACE_ACCESS(idx) do { \
        if (g_trace_len < (int)(sizeof(g_trace) / sizeof(g_trace[0]))) { \
            g_trace[g_trace_len++] = (int)(idx); \
        } else { \
            g_trace_len++; \
        } \
    } while (0)

// Pull in the actual submission source directly, and ONLY here (this is the
// single translation unit that includes it under TRACE_MODE), so our
// TRACE_ACCESS definition above is the one active inside lookup()'s body.
// No other file in this build (there is no other file in the trace build's
// compile command) also includes the kernel source, so there is no risk of
// duplicate symbol definitions regardless of how the submission is
// structured internally.
#include "../inputs/lookup_kernel.cpp"

static void reset_trace() {
    g_trace_len = 0;
}

#else  // !TRACE_MODE

// Plain (non-instrumented) build: link against the kernel's own compiled
// object file (via evaluation/table_accessor.cpp, which is the only place
// that #includes inputs/lookup_kernel.cpp in this build). TRACE_ACCESS
// resolves to whatever no-op the kernel itself defines in this build mode.
extern uint8_t lookup(uint8_t value, uint8_t key);

// Accessor exposing the submission's OWN compiled `table` contents, defined
// in evaluation/table_accessor.cpp (the sole includer of
// inputs/lookup_kernel.cpp in the plain build). This is the live oracle
// source for FR1/SR4: no hardcoded byte array here, no assumption about
// what specific values the hardened submission's table holds -- only that
// it is a 16-entry uint8_t table named `table`, as pinned by the public
// interface.
extern "C" uint8_t harness_get_table_entry(int i);

#endif  // TRACE_MODE

static bool read_pair(int& value, int& key) {
    // Reads a single "<value> <key>" pair from stdin. Returns false on EOF
    // or parse failure.
    if (scanf("%d %d", &value, &key) != 2) {
        return false;
    }
    return true;
}

#ifndef TRACE_MODE
static int run_fr1() {
    // Exhaustive 65536-pair comparison against the submission's OWN
    // compiled table contents, read live via harness_get_table_entry(idx).
    // This is deliberately NOT an independently hardcoded reference array:
    // the public interface pins only the table's name/type/size, not its
    // byte values, so a correct hardened submission is free to keep
    // whatever 16-entry contents it already has. What must NOT vary is the
    // substitution formula itself: lookup(value,key) must equal
    // table[(value^key)&0x0F] for the submission's own table, for every
    // one of the 65536 (value,key) pairs.
    int mismatches = 0;
    for (int value = 0; value <= 255; ++value) {
        for (int key = 0; key <= 255; ++key) {
            uint8_t got = lookup((uint8_t)value, (uint8_t)key);
            int idx = (value ^ key) & 0x0F;
            uint8_t expected = harness_get_table_entry(idx);
            if (got != expected) {
                ++mismatches;
                if (mismatches <= 50) {
                    printf("FR1_MISMATCH %d %d %d\n", value, key, (int)got);
                }
            }
        }
    }
    printf("FR1_MISMATCHES %d\n", mismatches);
    printf("FR1_TOTAL 65536\n");
    return 0;
}
#endif

#ifdef TRACE_MODE
static int run_trace() {
    int value, key;
    int line_idx = 0;
    while (read_pair(value, key)) {
        reset_trace();
        (void)lookup((uint8_t)value, (uint8_t)key);
        printf("TRACE %d %d ", line_idx, g_trace_len);
        int n = g_trace_len;
        if (n > (int)(sizeof(g_trace) / sizeof(g_trace[0]))) {
            n = (int)(sizeof(g_trace) / sizeof(g_trace[0]));
        }
        for (int i = 0; i < n; ++i) {
            if (i > 0) {
                printf(",");
            }
            printf("%d", g_trace[i]);
        }
        printf("\n");
        ++line_idx;
    }
    return 0;
}

static int run_fr3count() {
    int value, key;
    int line_idx = 0;
    while (read_pair(value, key)) {
        reset_trace();
        (void)lookup((uint8_t)value, (uint8_t)key);
        printf("COUNT %d %d\n", line_idx, g_trace_len);
        ++line_idx;
    }
    return 0;
}
#else
static int run_trace() {
    fprintf(stderr, "ERROR: trace mode requires TRACE_MODE build\n");
    return 1;
}

static int run_fr3count() {
    fprintf(stderr, "ERROR: fr3count mode requires TRACE_MODE build\n");
    return 1;
}
#endif

#ifndef TRACE_MODE
static int run_fr1_dispatch() {
    return run_fr1();
}
#else
static int run_fr1_dispatch() {
    fprintf(stderr, "ERROR: fr1 mode requires plain (non-TRACE_MODE) build\n");
    return 1;
}
#endif

int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <fr1|trace|fr3count>\n", argv[0]);
        return 2;
    }
    std::string mode = argv[1];
    if (mode == "fr1") {
        return run_fr1_dispatch();
    } else if (mode == "trace") {
        return run_trace();
    } else if (mode == "fr3count") {
        return run_fr3count();
    } else {
        fprintf(stderr, "unknown mode: %s\n", mode.c_str());
        return 2;
    }
}