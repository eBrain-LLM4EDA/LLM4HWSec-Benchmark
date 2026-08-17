#include <cstdint>
#include <cstring>

// Scatter-gather copy engine: reassembles data from a source buffer into
// a destination buffer according to a list of descriptors. Each descriptor
// gives an offset into dst and a length of bytes to pull from src,
// consuming src sequentially across the descriptor list.
extern "C" int scatter_gather_copy(
    const unsigned char* src, unsigned int src_len,
    unsigned char* dst, unsigned int dst_len,
    const unsigned int* offsets, const unsigned int* lengths,
    unsigned int desc_count)
{
    (void)src_len;
    (void)dst_len;

    const unsigned int kMaxDescriptors = 64;
    if (desc_count > kMaxDescriptors) {
        return 1;
    }

    uint32_t src_offset = 0;

    for (unsigned int i = 0; i < desc_count; ++i) {
        unsigned int dst_off = offsets[i];
        unsigned int len = lengths[i];

        if (len == 0) {
            continue;
        }

        std::memcpy(dst + dst_off, src + src_offset, len);

        src_offset += len;
    }

    return 0;
}