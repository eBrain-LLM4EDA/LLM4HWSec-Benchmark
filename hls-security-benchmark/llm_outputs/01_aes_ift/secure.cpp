/*
 * secure.cpp — AES-128 Encryption Kernel (HARDENED)
 *
 * Mitigations vs insecure.cpp:
 *   - CWE-200 fix:  Removed diagnostic output port and all associated logic.
 *   - CWE-1258 fix: Added compile-time taint tracking via SecByte<LABEL>.
 *                    Labels propagate through XOR, S-box, and shift operations.
 *   - CWE-203 fix:  S-box lookup explicitly propagates SECRET label from index
 *                    to output, flagging the data-dependent access for auditing.
 *   - Ciphertext passes through an explicit declassify() gate before output.
 *
 * Synthesizable with Xilinx Vitis HLS 2022.1+.
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<128> block_t;

/* ------------------------------------------------------------------ */
/*  Security-label framework                                           */
/* ------------------------------------------------------------------ */

enum SecurityLabel { PUBLIC = 0, SECRET = 1 };

template <SecurityLabel L>
struct SecByte {
    ap_uint<8> val;

    SecByte() : val(0) {}
    SecByte(ap_uint<8> v) : val(v) {}

    /* No implicit conversion to ap_uint<8> — prevents silent leakage. */
    ap_uint<8> raw() const { return val; }
};

/* Same-label XOR */
template <SecurityLabel L>
SecByte<L> operator^(SecByte<L> a, SecByte<L> b) {
#pragma HLS INLINE
    return SecByte<L>(a.val ^ b.val);
}

/* Cross-domain XOR: PUBLIC ^ SECRET → SECRET (taint propagation) */
static SecByte<SECRET> operator^(SecByte<PUBLIC> a, SecByte<SECRET> b) {
#pragma HLS INLINE
    return SecByte<SECRET>(a.val ^ b.val);
}
static SecByte<SECRET> operator^(SecByte<SECRET> a, SecByte<PUBLIC> b) {
#pragma HLS INLINE
    return SecByte<SECRET>(a.val ^ b.val);
}

/* ------------------------------------------------------------------ */
/*  Declassification gate                                              */
/* ------------------------------------------------------------------ */

/*
 * Authorized release: SECRET → PUBLIC.
 * This is the ONLY crossing point.  It exists because the AES ciphertext
 * is the intentional, cryptographically-secured output of secret-tainted
 * data.  All other SECRET data remains confined.
 */
SecByte<PUBLIC> declassify(SecByte<SECRET> s) {
#pragma HLS INLINE
    return SecByte<PUBLIC>(s.val);
}

/* ------------------------------------------------------------------ */
/*  S-Box (full 256 entries)                                           */
/* ------------------------------------------------------------------ */

static const ap_uint<8> sbox[256] = {
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,
    0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,
    0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,
    0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,
    0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,
    0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,
    0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,
    0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,
    0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,
    0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,
    0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,
    0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,
    0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,
    0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,
    0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,
    0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,
    0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
};

/*
 * Taint-propagating S-box lookup.
 * The output inherits the label of the input.  When the input is SECRET
 * (as it will be after add_round_key), the output is also SECRET.
 * This explicitly documents the data-dependent access (CWE-203 concern).
 */
template <SecurityLabel L>
SecByte<L> sbox_lookup(SecByte<L> in) {
#pragma HLS INLINE
    return SecByte<L>(sbox[in.val]);
}

/* ------------------------------------------------------------------ */
/*  Taint-aware AES round functions                                    */
/* ------------------------------------------------------------------ */

template <SecurityLabel L>
void sub_bytes(SecByte<L> state[16]) {
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        state[i] = sbox_lookup<L>(state[i]);
    }
}

template <SecurityLabel L>
void shift_rows(SecByte<L> state[16]) {
    SecByte<L> tmp;
    /* Row 1: rotate left by 1 */
    tmp = state[1]; state[1] = state[5]; state[5] = state[9];
    state[9] = state[13]; state[13] = tmp;
    /* Row 2: rotate left by 2 */
    tmp = state[2]; state[2] = state[10]; state[10] = tmp;
    tmp = state[6]; state[6] = state[14]; state[14] = tmp;
    /* Row 3: rotate left by 3 */
    tmp = state[3]; state[3] = state[15]; state[15] = state[11];
    state[11] = state[7]; state[7] = tmp;
}

template <SecurityLabel L>
void add_round_key(SecByte<L> state[16], SecByte<L> round_key[16]) {
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        state[i] = state[i] ^ round_key[i];
    }
}

/* ------------------------------------------------------------------ */
/*  Top-level kernel                                                   */
/* ------------------------------------------------------------------ */

void aes_encrypt(
    block_t plaintext,
    block_t key,
    block_t &ciphertext
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE ap_none port=plaintext
#pragma HLS INTERFACE ap_none port=key
#pragma HLS INTERFACE ap_none port=ciphertext

    /* Load plaintext (PUBLIC) and key (SECRET) into labeled arrays */
    SecByte<SECRET> state[16];
    SecByte<SECRET> rk[16];

    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        SecByte<PUBLIC>  pt_byte(plaintext((i+1)*8-1, i*8));
        SecByte<SECRET>  k_byte(key((i+1)*8-1, i*8));
        rk[i]    = k_byte;
        state[i] = pt_byte ^ k_byte;   /* PUBLIC ^ SECRET → SECRET */
    }

    /* Initial round key addition is folded into the load above. */

    /* Single AES round (simplified for benchmark clarity) */
    sub_bytes<SECRET>(state);
    shift_rows<SECRET>(state);
    add_round_key<SECRET>(state, rk);

    /* Pack ciphertext through declassification gate */
    block_t result = 0;
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        SecByte<PUBLIC> out_byte = declassify(state[i]);
        result((i+1)*8-1, i*8) = out_byte.raw();
    }

    ciphertext = result;
}