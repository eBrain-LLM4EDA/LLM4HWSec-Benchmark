#include <cstdint>

// Validates that a requested DMA transfer window [base, base+length)
// lies entirely within the allowed region [region_start, region_start+region_size).
//
// Returns 1 if the transfer is fully contained within the region, 0 otherwise.
extern "C" int validate_dma(uint32_t base, uint32_t length,
                             uint32_t region_start, uint32_t region_size) {
    uint32_t end = base + length;
    uint32_t region_end = region_start + region_size;

    if (base >= region_start && end <= region_end) {
        return 1;
    }

    return 0;
}