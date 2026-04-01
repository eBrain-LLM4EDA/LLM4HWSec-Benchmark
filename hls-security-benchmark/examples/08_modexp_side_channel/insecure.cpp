/*
 * Example 08: Modular Exponentiation (INSECURE)
 * Vulnerability: Square-and-multiply with data-dependent branching.
 *                Execution time and power profile leak exponent bits.
 * CWE-208: Observable Timing Discrepancy
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<256> bignum_t;
typedef ap_uint<512> bignum_wide_t;

struct modexp_req {
    bignum_t base;
    bignum_t exponent;  // SECRET
    bignum_t modulus;
};

struct modexp_resp {
    bignum_t result;
};

// Modular multiplication (simplified for benchmark)
bignum_t mod_mul(bignum_t a, bignum_t b, bignum_t mod) {
    bignum_wide_t product = (bignum_wide_t)a * (bignum_wide_t)b;
    return product % mod;
}

// BUG: Classic square-and-multiply — branches on each exponent bit
// BUG: Multiply only executed when bit=1 — timing/power side channel
// BUG: Loop exits early on leading zeros
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

        bignum_t result = 1;
        bignum_t base = r.base % r.modulus;

        // VULNERABILITY: data-dependent branching on secret exponent
        for (int i = 255; i >= 0; i--) {
            result = mod_mul(result, result, r.modulus);  // Square always

            if (r.exponent[i] == 1) {  // BUG: branch on secret bit
                result = mod_mul(result, base, r.modulus);  // Multiply only when bit=1
            }
            // BUG: timing differs between bit=0 and bit=1 iterations
        }

        resp.result = result;
        resp_out.write(resp);
    }
}
