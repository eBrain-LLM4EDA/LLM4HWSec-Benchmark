/*
 * Example 06: SHA-256 HMAC Engine (SECURE)
 * Fix: Diagnostic port removed. Taint labels track key-derived data.
 *      Message schedule cleared after use.
 * Mitigates: CWE-200
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<32> word_t;
typedef ap_uint<512> block_t;
typedef ap_uint<256> hash_t;

enum SecurityLabel { PUBLIC = 0, SECRET = 1 };

struct tainted_word {
    word_t data;
    SecurityLabel label;
    tainted_word() : data(0), label(PUBLIC) {}
    tainted_word(word_t d, SecurityLabel l) : data(d), label(l) {}

    tainted_word operator+(const tainted_word &o) const {
        return tainted_word(data + o.data,
            (label == SECRET || o.label == SECRET) ? SECRET : PUBLIC);
    }
    tainted_word operator^(const tainted_word &o) const {
        return tainted_word(data ^ o.data,
            (label == SECRET || o.label == SECRET) ? SECRET : PUBLIC);
    }
    tainted_word operator&(const tainted_word &o) const {
        return tainted_word(data & o.data,
            (label == SECRET || o.label == SECRET) ? SECRET : PUBLIC);
    }
    tainted_word operator~() const {
        return tainted_word(~data, label);
    }
    tainted_word operator>>(int n) const { return tainted_word(data >> n, label); }
    tainted_word operator<<(int n) const { return tainted_word(data << n, label); }
};

static const word_t H_INIT[8] = {
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
};

// FIX: No diagnostic port. MAC output is authorized declassification.
void hmac_sha256(
    block_t message,
    hash_t  key,
    hash_t  &mac_out
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE ap_none port=message
#pragma HLS INTERFACE ap_none port=key
#pragma HLS INTERFACE ap_none port=mac_out

    tainted_word h[8];
    tainted_word w[64];

    for (int i = 0; i < 8; i++) {
#pragma HLS UNROLL
        h[i] = tainted_word(H_INIT[i], PUBLIC);
    }

    // Inner hash: key is SECRET, message is PUBLIC
    for (int i = 0; i < 8; i++) {
#pragma HLS UNROLL
        tainted_word k = tainted_word(key((i+1)*32-1, i*32), SECRET);
        tainted_word ipad = tainted_word(0x36363636, PUBLIC);
        w[i] = k ^ ipad;  // Result is SECRET (taint propagated)
    }
    for (int i = 8; i < 16; i++) {
#pragma HLS UNROLL
        w[i] = tainted_word(message((i-8+1)*32-1, (i-8)*32), PUBLIC);
    }

    // Message schedule — taint propagates automatically
    for (int i = 16; i < 64; i++) {
#pragma HLS PIPELINE II=1
        tainted_word g1 = tainted_word(
            (w[i-2].data >> 17) | (w[i-2].data << 15), w[i-2].label);
        // Simplified expansion for benchmark
        w[i] = g1 + w[i-7] + w[i-16];
    }

    // Compression
    tainted_word a=h[0], b=h[1], c=h[2], d=h[3];
    tainted_word e=h[4], f=h[5], g=h[6], hh=h[7];

    for (int i = 0; i < 64; i++) {
#pragma HLS PIPELINE II=1
        tainted_word t1 = hh + w[i];
        tainted_word t2 = a;
        hh=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }

    h[0]=h[0]+a; h[1]=h[1]+b; h[2]=h[2]+c; h[3]=h[3]+d;
    h[4]=h[4]+e; h[5]=h[5]+f; h[6]=h[6]+g; h[7]=h[7]+hh;

    // Authorized declassification: HMAC output
    hash_t result = 0;
    for (int i = 0; i < 8; i++) {
#pragma HLS UNROLL
        result((i+1)*32-1, i*32) = h[i].data;
    }
    mac_out = result;

    // FIX: Clear message schedule (contains key-derived data)
    for (int i = 0; i < 64; i++) {
#pragma HLS UNROLL factor=8
        w[i] = tainted_word(0, PUBLIC);
    }
}
