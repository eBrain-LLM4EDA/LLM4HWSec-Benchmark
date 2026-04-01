/*
 * Example 04: Crypto Key Schedule with Isolated Buffers (SECURE)
 * Fix: Separate storage for key schedule and user data.
 *      Key material zeroized after use.
 * Mitigates: CWE-1189
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<32> word_t;
typedef ap_uint<8>  byte_t;
typedef ap_uint<128> block_t;

#define NK 4
#define NR 10
#define NB 4

static const byte_t sbox[256] = { /* abbreviated */ };

word_t sub_word(word_t w) {
    word_t result = 0;
    for (int i = 0; i < 4; i++) {
#pragma HLS UNROLL
        byte_t b = w((i+1)*8-1, i*8);
        result((i+1)*8-1, i*8) = sbox[b];
    }
    return result;
}

word_t rot_word(word_t w) {
    return (w << 8) | (w >> 24);
}

void crypto_engine(
    block_t user_data_in,
    block_t key_in,
    block_t &data_out,
    bool key_load,
    bool process,
    bool zeroize     // FIX: explicit zeroization trigger
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE ap_none port=user_data_in
#pragma HLS INTERFACE ap_none port=key_in
#pragma HLS INTERFACE ap_none port=data_out
#pragma HLS INTERFACE ap_none port=key_load
#pragma HLS INTERFACE ap_none port=process
#pragma HLS INTERFACE ap_none port=zeroize

    // FIX: Separate, isolated storage for key schedule
    static word_t key_schedule[NB * (NR + 1)];
#pragma HLS BIND_STORAGE variable=key_schedule type=ram_1p
    // FIX: Separate buffer for user data
    static word_t data_buf[NB];
#pragma HLS BIND_STORAGE variable=data_buf type=ram_1p

    static const word_t rcon[10] = {
        0x01000000, 0x02000000, 0x04000000, 0x08000000, 0x10000000,
        0x20000000, 0x40000000, 0x80000000, 0x1B000000, 0x36000000
    };

    // FIX: Zeroize key material on command
    if (zeroize) {
        for (int i = 0; i < NB * (NR + 1); i++) {
#pragma HLS UNROLL factor=4
            key_schedule[i] = 0;
        }
        data_out = 0;
        return;
    }

    if (key_load) {
        for (int i = 0; i < NK; i++) {
#pragma HLS UNROLL
            key_schedule[i] = key_in((i+1)*32-1, i*32);
        }
        for (int i = NK; i < NB * (NR + 1); i++) {
#pragma HLS PIPELINE II=1
            word_t temp = key_schedule[i - 1];
            if (i % NK == 0) {
                temp = sub_word(rot_word(temp)) ^ rcon[i / NK - 1];
            }
            key_schedule[i] = key_schedule[i - NK] ^ temp;
        }
    }

    if (process) {
        // FIX: Data stored in isolated buffer
        for (int i = 0; i < NB; i++) {
#pragma HLS UNROLL
            data_buf[i] = user_data_in((i+1)*32-1, i*32);
        }
        // XOR with round key — read from key_schedule, write to data_buf
        for (int i = 0; i < NB; i++) {
#pragma HLS UNROLL
            data_buf[i] ^= key_schedule[i];
        }

        block_t result = 0;
        for (int i = 0; i < NB; i++) {
#pragma HLS UNROLL
            result((i+1)*32-1, i*32) = data_buf[i];
        }
        data_out = result;

        // FIX: Clear data buffer after use
        for (int i = 0; i < NB; i++) {
#pragma HLS UNROLL
            data_buf[i] = 0;
        }
    }
}
