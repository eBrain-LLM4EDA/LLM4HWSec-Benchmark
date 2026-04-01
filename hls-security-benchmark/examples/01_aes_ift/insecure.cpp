/*
 * Example 01: AES-128 Encryption Kernel (INSECURE)
 * Vulnerability: Secret key material leaks to public output port.
 *                No information flow tracking between security domains.
 * CWE-200: Exposure of Sensitive Information to an Unauthorized Actor
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<128> block_t;
typedef ap_uint<8> byte_t;

// S-Box lookup (abbreviated for benchmark)
static const byte_t sbox[256] = {
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,
    0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    // ... remaining 240 entries omitted for brevity
};

void sub_bytes(byte_t state[16]) {
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        state[i] = sbox[state[i]];
    }
}

void shift_rows(byte_t state[16]) {
    byte_t tmp;
    // Row 1: shift left by 1
    tmp = state[1]; state[1] = state[5]; state[5] = state[9];
    state[9] = state[13]; state[13] = tmp;
    // Row 2: shift left by 2
    tmp = state[2]; state[2] = state[10]; state[10] = tmp;
    tmp = state[6]; state[6] = state[14]; state[14] = tmp;
    // Row 3: shift left by 3
    tmp = state[3]; state[3] = state[15]; state[15] = state[11];
    state[11] = state[7]; state[7] = tmp;
}

void add_round_key(byte_t state[16], byte_t round_key[16]) {
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        state[i] ^= round_key[i];
    }
}

// BUG: Debug port exposes internal state including key-derived values
// BUG: No taint tracking — key material mixes with plaintext without labels
// BUG: Round key array accessible from top-level interface without restriction
void aes_encrypt(
    block_t plaintext,
    block_t key,
    block_t &ciphertext,
    block_t &debug_out   // VULNERABILITY: leaks intermediate key-dependent state
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE ap_none port=plaintext
#pragma HLS INTERFACE ap_none port=key
#pragma HLS INTERFACE ap_none port=ciphertext
#pragma HLS INTERFACE ap_none port=debug_out

    byte_t state[16];
    byte_t rk[16];

    // Load plaintext into state
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        state[i] = plaintext((i+1)*8-1, i*8);
        rk[i] = key((i+1)*8-1, i*8);
    }

    // Initial round key addition
    add_round_key(state, rk);

    // Simplified: 1 round for benchmark clarity
    sub_bytes(state);
    shift_rows(state);
    add_round_key(state, rk);

    // Pack output
    block_t result = 0;
    block_t dbg = 0;
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        result((i+1)*8-1, i*8) = state[i];
        dbg((i+1)*8-1, i*8) = rk[i];  // BUG: exposes round key on debug port
    }
    ciphertext = result;
    debug_out = dbg;  // VULNERABILITY: secret key exposed
}
