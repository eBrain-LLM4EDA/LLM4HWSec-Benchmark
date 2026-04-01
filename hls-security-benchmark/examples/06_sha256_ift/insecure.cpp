/*
 * Example 06: SHA-256 HMAC Engine (INSECURE)
 * Vulnerability: HMAC key leaks through unprotected hash state output.
 *                No taint propagation through compression function.
 * CWE-200: Exposure of Sensitive Information to an Unauthorized Actor
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<32> word_t;
typedef ap_uint<512> block_t;
typedef ap_uint<256> hash_t;

// SHA-256 initial hash values
static const word_t H_INIT[8] = {
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
};

word_t ch(word_t x, word_t y, word_t z)  { return (x & y) ^ (~x & z); }
word_t maj(word_t x, word_t y, word_t z) { return (x & y) ^ (x & z) ^ (y & z); }

word_t rotr(word_t x, int n) { return (x >> n) | (x << (32 - n)); }
word_t sigma0(word_t x) { return rotr(x,2)  ^ rotr(x,13) ^ rotr(x,22); }
word_t sigma1(word_t x) { return rotr(x,6)  ^ rotr(x,11) ^ rotr(x,25); }
word_t gamma0(word_t x) { return rotr(x,7)  ^ rotr(x,18) ^ (x >> 3);  }
word_t gamma1(word_t x) { return rotr(x,17) ^ rotr(x,19) ^ (x >> 10); }

// BUG: Internal hash state exposed on diagnostic port
// BUG: HMAC key XOR'd with ipad/opad without taint tracking
// BUG: Intermediate state after key processing is observable
void hmac_sha256(
    block_t message,
    hash_t  key,
    hash_t  &mac_out,
    hash_t  &internal_state_out  // VULNERABILITY: leaks key-derived state
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE ap_none port=message
#pragma HLS INTERFACE ap_none port=key
#pragma HLS INTERFACE ap_none port=mac_out
#pragma HLS INTERFACE ap_none port=internal_state_out

    word_t h[8];
    word_t w[64];

    // Initialize hash state
    for (int i = 0; i < 8; i++) {
#pragma HLS UNROLL
        h[i] = H_INIT[i];
    }

    // Inner hash: H(key XOR ipad || message)
    // Simplified: just XOR key into first block
    for (int i = 0; i < 8; i++) {
#pragma HLS UNROLL
        w[i] = key((i+1)*32-1, i*32) ^ 0x36363636;  // ipad
    }
    for (int i = 8; i < 16; i++) {
#pragma HLS UNROLL
        w[i] = message((i-8+1)*32-1, (i-8)*32);
    }

    // Message schedule expansion
    for (int i = 16; i < 64; i++) {
#pragma HLS PIPELINE II=1
        w[i] = gamma1(w[i-2]) + w[i-7] + gamma0(w[i-15]) + w[i-16];
    }

    // Compression (simplified single round for benchmark)
    word_t a=h[0], b=h[1], c=h[2], d=h[3];
    word_t e=h[4], f=h[5], g=h[6], hh=h[7];

    for (int i = 0; i < 64; i++) {
#pragma HLS PIPELINE II=1
        word_t t1 = hh + sigma1(e) + ch(e,f,g) + w[i];
        word_t t2 = sigma0(a) + maj(a,b,c);
        hh=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }

    h[0]+=a; h[1]+=b; h[2]+=c; h[3]+=d;
    h[4]+=e; h[5]+=f; h[6]+=g; h[7]+=hh;

    // Pack output
    hash_t result = 0;
    hash_t dbg = 0;
    for (int i = 0; i < 8; i++) {
#pragma HLS UNROLL
        result((i+1)*32-1, i*32) = h[i];
        dbg((i+1)*32-1, i*32) = w[i];  // BUG: exposes key XOR ipad
    }
    mac_out = result;
    internal_state_out = dbg;  // VULNERABILITY: key-derived data leaked
}
