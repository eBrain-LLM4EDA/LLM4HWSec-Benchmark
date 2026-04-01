/*
 * Example 08: Modular Exponentiation (SECURE)
 * Fix: Montgomery ladder — constant-time, no data-dependent branching.
 *      Both branches always execute; result selected by mux.
 * Mitigates: CWE-208
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<256> bignum_t;
typedef ap_uint<512> bignum_wide_t;

struct modexp_req {
    bignum_t base;
    bignum_t exponent;
    bignum_t modulus;
};

struct modexp_resp {
    bignum_t result;
};

bignum_t mod_mul(bignum_t a, bignum_t b, bignum_t mod) {
    bignum_wide_t product = (bignum_wide_t)a * (bignum_wide_t)b;
    return product % mod;
}

// FIX: Constant-time conditional swap (no branch)
void cswap(bignum_t &a, bignum_t &b, ap_uint<1> condition) {
#pragma HLS INLINE
    // Branchless swap: mask is all-1s if condition=1, all-0s if condition=0
    bignum_t mask = 0;
    mask = condition ? (bignum_t)(-1) : (bignum_t)(0);
    bignum_t diff = mask & (a ^ b);
    a ^= diff;
    b ^= diff;
}

// FIX: Montgomery ladder — constant operations per bit
void modular_exp(
    hls::stream<modexp_req> &req_in,
    hls::stream<modexp_resp> &resp_out
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE axis port=req_in
#pragma HLS INTERFACE axis port=resp_out

    if (!req_in.empty()) {
        modexp_req r = req_in.read();
        modexp_resp resp;

        bignum_t r0 = 1;
        bignum_t r1 = r.base % r.modulus;

        // FIX: Montgomery ladder — both multiply and square execute every iteration
        for (int i = 255; i >= 0; i--) {
#pragma HLS PIPELINE II=1
            ap_uint<1> bit = r.exponent[i];

            // FIX: Constant-time swap based on bit
            cswap(r0, r1, bit);

            // Always execute both operations
            r1 = mod_mul(r0, r1, r.modulus);
            r0 = mod_mul(r0, r0, r.modulus);

            // Swap back
            cswap(r0, r1, bit);
        }

        resp.result = r0;
        resp_out.write(resp);
    }
}
