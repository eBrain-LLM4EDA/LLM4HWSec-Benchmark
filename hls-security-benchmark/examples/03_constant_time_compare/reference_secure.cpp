/*
 * Example 03: Password/Token Comparison (SECURE)
 * Fix: Constant-time comparison — no early exit, fixed iteration count.
 * Mitigates: CWE-208
 */

#include <ap_int.h>
#include <hls_stream.h>

#define TOKEN_LEN 32

typedef ap_uint<8> byte_t;

struct compare_req {
    byte_t candidate[TOKEN_LEN];
    byte_t reference[TOKEN_LEN];
};

struct compare_resp {
    bool match;
};

// FIX: Constant-time comparison — always iterates all TOKEN_LEN bytes
void token_compare(
    hls::stream<compare_req> &req_in,
    hls::stream<compare_resp> &resp_out
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE axis port=req_in
#pragma HLS INTERFACE axis port=resp_out

    if (!req_in.empty()) {
        compare_req r = req_in.read();
        compare_resp resp;

        // FIX: Accumulate XOR differences — no early exit
        byte_t diff = 0;
        for (int i = 0; i < TOKEN_LEN; i++) {
#pragma HLS UNROLL  // Fixed latency: all bytes compared in parallel
            diff |= (r.candidate[i] ^ r.reference[i]);
        }

        // Single branch at the end — same cycle count regardless of match position
        resp.match = (diff == 0);

        resp_out.write(resp);
    }
}
