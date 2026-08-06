// packet_kernel.cpp
//
// Packet transformation kernel for a shared hardware accelerator buffer.
// Applies a fixed per-byte transformation to the valid portion of an
// incoming packet payload and writes the result to the output buffer.

void process_packet(const unsigned char in_buf[32], int length, unsigned char out_buf[32])
{
    for (int i = 0; i < 32; i++)
    {
        if (i < length)
        {
            unsigned char shifted = static_cast<unsigned char>(in_buf[i] ^ 0xA5);
            out_buf[i] = static_cast<unsigned char>((shifted + i) & 0xFF);
        }
    }
}