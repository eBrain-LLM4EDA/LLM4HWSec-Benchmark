// packet_kernel.cpp
//
// Hardened packet transformation kernel.
//
// Security property: every invocation of process_packet writes all 32
// bytes of out_buf, unconditionally. Bytes at indices >= length are
// always explicitly set to 0x00, never left containing stale data from
// a previous call that may have used a longer length. This prevents
// cross-invocation leakage of confidential data through a shared
// output buffer (CWE-459 / CWE-200 / CWE-212).
//
// The loop has a fixed trip count of 32 iterations (bounded by the
// array size), and `length` is used only as a per-iteration
// conditional (i < length), never as a loop bound. No dynamic memory
// allocation, no recursion, no global or static state.

void process_packet(const unsigned char in_buf[32], int length, unsigned char out_buf[32])
{
    for (int i = 0; i < 32; ++i) {
        bool valid = (i < length);
        unsigned char transformed = (unsigned char)(((in_buf[i] ^ 0xA5) + i) & 0xFF);
        out_buf[i] = valid ? transformed : (unsigned char)0x00;
    }
}