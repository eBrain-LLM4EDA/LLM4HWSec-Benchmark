// evaluation/table_accessor.cpp
//
// Small helper translation unit used ONLY by the plain (non-TRACE_MODE)
// build. It is the single place in that build where the submission source
// (inputs/lookup_kernel.cpp) is #included, so evaluation/harness_main.cpp
// never has to include it itself and no other translation unit compiles
// inputs/lookup_kernel.cpp again -- avoiding duplicate-symbol link errors
// for `lookup` and `table` regardless of how the submission organizes its
// own internal helpers.
//
// In this build mode the kernel's own guarded TRACE_ACCESS macro resolves
// to whatever no-op the submission itself defines when the macro is not
// already defined (per the public interface contract), so this file does
// not redefine TRACE_ACCESS at all.
//
// IMPORTANT (oracle role): harness_get_table_entry(int i) is the live
// oracle data source used by evaluation/harness_main.cpp's FR1/SR4 checks.
// The submission's `table` array in inputs/lookup_kernel.cpp is declared
// `static const uint8_t table[16]` in the shipped baseline; a hardened
// submission may keep it `static` (internal linkage) as well, so
// harness_main.cpp cannot reliably declare `extern const uint8_t
// table[16];` and link directly against a possibly-internal-linkage
// symbol name from a different translation unit. Instead, this file
// #includes inputs/lookup_kernel.cpp directly -- the one and only place
// it is included in the plain build -- so it has direct, in-TU visibility
// of whatever `table` object the submission defines (regardless of its
// linkage), and re-exposes individual entries through a stable, always-
// externally-linkable `extern "C"` function:
//
//     extern "C" uint8_t harness_get_table_entry(int i) { return table[i]; }
//
// evaluation/harness_main.cpp declares this function as
// `extern "C" uint8_t harness_get_table_entry(int i);` and calls it to
// compute expected = harness_get_table_entry((value^key)&0x0F) for every
// (value,key) pair in FR1/SR4's exhaustive 65536-pair sweep. This means
// the oracle is always derived from the submission's OWN compiled table
// contents -- never an independently hardcoded byte array -- so any
// hardened submission that keeps the pinned 16-entry uint8_t table named
// `table` (regardless of its specific byte values) and faithfully
// implements table[(value^key)&0x0F] against that table will PASS, while
// a mutant that breaks the substitution formula itself (wrong index
// computation, ignoring key, returning a constant, etc.) will still
// produce a detectable mismatch against this live-read oracle.
//
// Build command (plain build):
//   g++ -std=c++11 -O0 -o harness_plain evaluation/table_accessor.cpp evaluation/harness_main.cpp

#include <cstdint>

#include "../inputs/lookup_kernel.cpp"

// Exposed with C linkage so its name is stable regardless of how the
// submission's own internals (namespaces, static helpers, etc.) are
// structured, and regardless of whether the submission's `table` array
// itself has internal (`static`) or external linkage -- this function is
// defined in the same translation unit that includes the submission
// source, so it can read `table[i]` directly either way.
extern "C" uint8_t harness_get_table_entry(int i) {
    return table[i];
}