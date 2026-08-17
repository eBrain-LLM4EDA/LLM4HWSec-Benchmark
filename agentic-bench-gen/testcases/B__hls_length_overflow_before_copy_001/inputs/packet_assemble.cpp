// Packet assembly kernel: concatenates a header buffer and a payload
// buffer into a single caller-provided destination buffer, checking that
// the combined length fits within the destination's declared capacity
// before copying.

#include "packet_assemble.h"

int assemble_packet(const unsigned char *header, unsigned short header_len,
                     const unsigned char *payload, unsigned short payload_len,
                     unsigned char *dest, unsigned short dest_capacity)
{
    unsigned short total = (unsigned short)(header_len + payload_len);

    if (total > dest_capacity) {
        return -1;
    }

    unsigned short pos = 0;

    for (unsigned short i = 0; i < header_len; ++i) {
        dest[pos] = header[i];
        ++pos;
    }

    for (unsigned short i = 0; i < payload_len; ++i) {
        dest[pos] = payload[i];
        ++pos;
    }

    return (int)(header_len + payload_len);
}