/*
 * Example 03: Password/Token Comparison (INSECURE)
 * Vulnerability: Early-exit comparison leaks secret length via timing.
 * CWE-208: Observable Timing Discrepancy
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

// BUG: Early-exit loop — timing reveals number of matching prefix bytes
// BUG: Branch on secret data causes variable execution time
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
        resp.match = true;

        // VULNERABILITY: early exit leaks match position through timing
        for (int i = 0; i < TOKEN_LEN; i++) {
            if (r.candidate[i] != r.reference[i]) {
                resp.match = false;
                break;  // BUG: timing side channel
            }
        }

        resp_out.write(resp);
    }
}
