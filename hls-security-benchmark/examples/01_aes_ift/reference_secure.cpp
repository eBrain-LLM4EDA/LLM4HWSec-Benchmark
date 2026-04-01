/*
 * Example 01: AES-128 Encryption Kernel (SECURE)
 * Fix: Information flow tracking via taint labels.
 *      Debug port removed. Key material cannot reach public outputs.
 * Mitigates: CWE-200
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<128> block_t;
typedef ap_uint<8> byte_t;

// Security label enum for information flow tracking
enum SecurityLabel { PUBLIC = 0, SECRET = 1 };

// Taint-tracked byte: carries data + its security label
struct tainted_byte {
    byte_t data;
    SecurityLabel label;

    tainted_byte() : data(0), label(PUBLIC) {}
    tainted_byte(byte_t d, SecurityLabel l) : data(d), label(l) {}

    // Taint propagation: XOR propagates the higher security label
    tainted_byte operator^(const tainted_byte &other) const {
        SecurityLabel new_label = (label == SECRET || other.label == SECRET) ? SECRET : PUBLIC;
        return tainted_byte(data ^ other.data, new_label);
    }
};

static const byte_t sbox[256] = {
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,
    0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    // ... remaining entries omitted for brevity
};

void sub_bytes(tainted_byte state[16]) {
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        // S-box lookup: result inherits the taint of the index
        state[i] = tainted_byte(sbox[state[i].data], state[i].label);
    }
}

void shift_rows(tainted_byte state[16]) {
    tainted_byte tmp;
    tmp = state[1]; state[1] = state[5]; state[5] = state[9];
    state[9] = state[13]; state[13] = tmp;
    tmp = state[2]; state[2] = state[10]; state[10] = tmp;
    tmp = state[6]; state[6] = state[14]; state[14] = tmp;
    tmp = state[3]; state[3] = state[15]; state[15] = state[11];
    state[11] = state[7]; state[7] = tmp;
}

void add_round_key(tainted_byte state[16], tainted_byte round_key[16]) {
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        state[i] = state[i] ^ round_key[i];  // Taint propagation via operator^
    }
}

// SECURITY CHECK: Assert no SECRET data flows to PUBLIC output
bool check_output_declassification(tainted_byte state[16], bool authorized) {
    if (!authorized) {
        for (int i = 0; i < 16; i++) {
            if (state[i].label == SECRET) {
                return false;  // Block: secret data on public channel
            }
        }
    }
    return true;
}

// FIX: Debug port removed. Output is implicitly declassified (ciphertext is
//      the intentional, authorized release of key-dependent data).
void aes_encrypt(
    block_t plaintext,
    block_t key,
    block_t &ciphertext
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE ap_none port=plaintext
#pragma HLS INTERFACE ap_none port=key
#pragma HLS INTERFACE ap_none port=ciphertext

    tainted_byte state[16];
    tainted_byte rk[16];

    // Load with taint labels: plaintext=PUBLIC, key=SECRET
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        state[i] = tainted_byte(plaintext((i+1)*8-1, i*8), PUBLIC);
        rk[i]    = tainted_byte(key((i+1)*8-1, i*8), SECRET);
    }

    add_round_key(state, rk);  // state becomes SECRET (taint propagation)

    sub_bytes(state);
    shift_rows(state);
    add_round_key(state, rk);

    // Authorized declassification: ciphertext is the intended output
    // In a real design, this would be gated by a declassification policy
    block_t result = 0;
    for (int i = 0; i < 16; i++) {
#pragma HLS UNROLL
        result((i+1)*8-1, i*8) = state[i].data;
    }
    ciphertext = result;

    // No debug_out port — key material cannot leak
}
