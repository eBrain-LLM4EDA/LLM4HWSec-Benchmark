#ifndef PACKET_ASSEMBLE_H
#define PACKET_ASSEMBLE_H

/**
 * Assemble a packet by concatenating a header buffer and a payload buffer
 * into a caller-provided destination buffer.
 *
 * @param header        Pointer to header_len bytes to copy first.
 * @param header_len    Number of valid bytes in header (0..65535).
 * @param payload       Pointer to payload_len bytes to copy after the header.
 * @param payload_len   Number of valid bytes in payload (0..65535).
 * @param dest          Output buffer of at least dest_capacity bytes.
 * @param dest_capacity Declared capacity of dest, in bytes (0..65535).
 *
 * @return The exact number of bytes written to dest (header_len +
 *         payload_len) on success. Returns -1 without writing anything to
 *         dest when the combined length of header_len and payload_len
 *         exceeds dest_capacity.
 */
int assemble_packet(const unsigned char *header, unsigned short header_len,
                     const unsigned char *payload, unsigned short payload_len,
                     unsigned char *dest, unsigned short dest_capacity);

#endif /* PACKET_ASSEMBLE_H */