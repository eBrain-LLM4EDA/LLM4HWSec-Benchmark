// Packet assembly kernel: concatenates a header buffer and a payload
// buffer into a single caller-provided destination buffer, checking that
// the combined length fits within the destination's declared capacity
// before copying.
//
// Hardened version: the combined length of header_len and payload_len is
// computed in a widened, non-wrapping type (unsigned int) before being
// compared against dest_capacity. Since header_len and payload_len are
// each at most 65535, their true sum is at most 131070, which fits
// comfortably in a 32-bit unsigned int without any wraparound. The copy
// loops are bounded by the original 16-bit length fields themselves
// (never by any truncated/wrapped sum), so no out-of-bounds write can
// occur even when the capacity check passes.

#include "packet_assemble.h"

int assemble_packet(const unsigned char *header, unsigned short header_len,
                     const unsigned char *payload, unsigned short payload_len,
                     unsigned char *dest, unsigned short dest_capacity)
{
    // Widen both operands before adding so the sum can never wrap: the
    // maximum possible value is 65535 + 65535 = 131070, which fits well
    // within the range of unsigned int (and size_t) on all supported
    // platforms.
    unsigned int total = (unsigned int)header_len + (unsigned int)payload_len;

    // Compare the widened, non-wrapping sum against the (also widened)
    // capacity. No copy is attempted, and dest is left completely
    // untouched, if the true combined length exceeds the capacity.
    if (total > (unsigned int)dest_capacity) {
        return -1;
    }

    unsigned int pos = 0;

    // Bound the header copy loop strictly by header_len (the original
    // 16-bit field), never by any narrowed/truncated total.
    for (unsigned short i = 0; i < header_len; ++i) {
        dest[pos] = header[i];
        ++pos;
    }

    // Bound the payload copy loop strictly by payload_len (the original
    // 16-bit field), never by any narrowed/truncated total.
    for (unsigned short i = 0; i < payload_len; ++i) {
        dest[pos] = payload[i];
        ++pos;
    }

    return (int)total;
}