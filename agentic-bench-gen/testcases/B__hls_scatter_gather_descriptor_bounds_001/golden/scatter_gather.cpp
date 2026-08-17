#include <cstdint>
#include <cstring>

// Scatter-gather copy engine: reassembles data from a source buffer into
// a destination buffer according to a list of descriptors. Each descriptor
// gives an offset into dst and a length of bytes to pull from src,
// consuming src sequentially across the descriptor list.
//
// Hardened implementation: performs a full validation pass over every
// descriptor, using 64-bit widened arithmetic to avoid unsigned wraparound,
// before committing any writes to dst. Only if the entire batch validates
// does it perform the actual copies.
extern "C" int scatter_gather_copy(
    const unsigned char* src, unsigned int src_len,
    unsigned char* dst, unsigned int dst_len,
    const unsigned int* offsets, const unsigned int* lengths,
    unsigned int desc_count)
{
    if (desc_count == 0) {
        return 0;
    }

    const unsigned int kMaxDescriptors = 64;
    if (desc_count > kMaxDescriptors) {
        return 1;
    }

    const uint64_t dst_len64 = static_cast<uint64_t>(dst_len);
    const uint64_t src_len64 = static_cast<uint64_t>(src_len);

    // Validation pass: check every descriptor against dst bounds and the
    // cumulative source read position against src bounds, using 64-bit
    // arithmetic so no sum can silently wrap around.
    uint64_t running_src_offset = 0;

    for (unsigned int i = 0; i < desc_count; ++i) {
        const uint64_t dst_off = static_cast<uint64_t>(offsets[i]);
        const uint64_t len = static_cast<uint64_t>(lengths[i]);

        // Destination bounds check: offset + length must not exceed dst_len.
        // offset == dst_len with length == 0 is fine; offset+length == dst_len
        // is the exact-fit boundary and is valid; offset+length > dst_len is not.
        if (dst_off > dst_len64) {
            return 2;
        }
        const uint64_t dst_end = dst_off + len; // safe: both operands < 2^33
        if (dst_end > dst_len64) {
            return 3;
        }

        // Source bounds check: cumulative read position must not exceed src_len.
        const uint64_t src_end = running_src_offset + len; // safe widened sum
        if (src_end > src_len64) {
            return 4;
        }

        running_src_offset = src_end;
    }

    // All descriptors validated; perform the actual copies.
    uint64_t src_offset = 0;
    for (unsigned int i = 0; i < desc_count; ++i) {
        const unsigned int dst_off = offsets[i];
        const unsigned int len = lengths[i];

        if (len == 0) {
            continue;
        }

        std::memcpy(dst + dst_off, src + src_offset, len);
        src_offset += len;
    }

    return 0;
}