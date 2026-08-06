#include <cstdint>

// Overflow-safe DMA range validation.
//
// Determines whether the half-open byte range [base, base+length) is
// entirely contained within the half-open allowed range
// [region_start, region_start+region_size), without ever performing the
// actual memory access.
//
// All boundary arithmetic is widened to uint64_t so that no 32-bit
// wraparound can occur: the maximum possible sum of two uint32_t values
// is 2*UINT32_MAX (~8.6e9), which fits comfortably within the uint64_t
// range (~1.8e19). This eliminates the classic integer-overflow bounds
// check bypass (CWE-190/CWE-191) where base+length or
// region_start+region_size wraps modulo 2^32 and spuriously satisfies a
// naive 32-bit comparison.
extern "C" int validate_dma(uint32_t base, uint32_t length, uint32_t region_start, uint32_t region_size) {
    // Zero-length transfers are never valid, regardless of alignment.
    if (length == 0) {
        return 0;
    }

    const uint64_t base64 = static_cast<uint64_t>(base);
    const uint64_t length64 = static_cast<uint64_t>(length);
    const uint64_t region_start64 = static_cast<uint64_t>(region_start);
    const uint64_t region_size64 = static_cast<uint64_t>(region_size);

    // Widened, non-wrapping end addresses.
    const uint64_t end = base64 + length64;
    const uint64_t region_end = region_start64 + region_size64;

    // Fully contained iff the start is at or after region_start and the
    // exact (non-wrapped) end address does not exceed region_end.
    if (base64 >= region_start64 && end <= region_end) {
        return 1;
    }

    return 0;
}