/*
 * Example 04: Crypto Key Schedule with Shared Buffer (INSECURE)
 * Vulnerability: Key schedule shares buffer with user-accessible data path.
 *                No compartmentalization between key expansion and data processing.
 * CWE-1189: Improper Isolation of Shared Resources on System-on-a-Chip (SoC)
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<32> word_t;
typedef ap_uint<8>  byte_t;
typedef ap_uint<128> block_t;

#define NK 4   // Key length in 32-bit words (AES-128)
#define NR 10  // Number of rounds
#define NB 4   // Block size in words

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

// BUG: Shared buffer for key schedule AND user data — no isolation
// BUG: Expanded key persists in shared_buf after use — residual secret
// BUG: User can trigger read of key schedule region via data processing path
void crypto_engine(
    block_t user_data_in,
    block_t key_in,
    block_t &data_out,
    bool key_load,
    bool process
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE ap_none port=user_data_in
#pragma HLS INTERFACE ap_none port=key_in
#pragma HLS INTERFACE ap_none port=data_out
#pragma HLS INTERFACE ap_none port=key_load
#pragma HLS INTERFACE ap_none port=process

    // VULNERABILITY: single shared buffer for keys and data
    static word_t shared_buf[64];
#pragma HLS BIND_STORAGE variable=shared_buf type=ram_2p

    static const word_t rcon[10] = {
        0x01000000, 0x02000000, 0x04000000, 0x08000000, 0x10000000,
        0x20000000, 0x40000000, 0x80000000, 0x1B000000, 0x36000000
    };

    if (key_load) {
        // Load key into shared buffer (offsets 0–3)
        for (int i = 0; i < NK; i++) {
#pragma HLS UNROLL
            shared_buf[i] = key_in((i+1)*32-1, i*32);
        }
        // Expand key into shared_buf[4..43]
        for (int i = NK; i < NB * (NR + 1); i++) {
#pragma HLS PIPELINE II=1
            word_t temp = shared_buf[i - 1];
            if (i % NK == 0) {
                temp = sub_word(rot_word(temp)) ^ rcon[i / NK - 1];
            }
            shared_buf[i] = shared_buf[i - NK] ^ temp;
        }
    }

    if (process) {
        // BUG: Data processing uses same buffer — user_data stored at offset 44+
        for (int i = 0; i < NB; i++) {
#pragma HLS UNROLL
            shared_buf[44 + i] = user_data_in((i+1)*32-1, i*32);
        }

        // XOR with first round key (from shared_buf[0..3])
        for (int i = 0; i < NB; i++) {
#pragma HLS UNROLL
            shared_buf[44 + i] ^= shared_buf[i];
        }

        // Output — but attacker could manipulate offsets
        block_t result = 0;
        for (int i = 0; i < NB; i++) {
#pragma HLS UNROLL
            result((i+1)*32-1, i*32) = shared_buf[44 + i];
        }
        data_out = result;
        // BUG: Key material remains in shared_buf after processing
    }
}
