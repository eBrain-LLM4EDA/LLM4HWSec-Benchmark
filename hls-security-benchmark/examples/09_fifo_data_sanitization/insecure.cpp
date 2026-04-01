/*
 * Example 09: Shared FIFO Buffer with No Data Sanitization (INSECURE)
 * Vulnerability: FIFO buffer retains data from previous security context.
 *                Context switch does not clear buffer entries.
 *                Uninitialized entries on reset may contain secrets.
 * CWE-226: Sensitive Information in Resource Not Removed Before Reuse
 * CWE-1271: Uninitialized Value on Reset
 */

#include <ap_int.h>
#include <hls_stream.h>

#define FIFO_DEPTH 16

typedef ap_uint<64> data_t;
typedef ap_uint<4>  ptr_t;
typedef ap_uint<2>  ctx_id_t;  // Security context ID

struct fifo_cmd {
    ctx_id_t  context;
    data_t    wdata;
    bool      push;
    bool      pop;
    bool      ctx_switch;  // Indicates new security context
};

struct fifo_resp {
    data_t  rdata;
    bool    valid;
    bool    empty;
    bool    full;
};

// BUG: Buffer not cleared on context switch — old data from previous context readable
// BUG: No initialization on reset — BRAM contents undefined
// BUG: Popped entries not overwritten — stale secret data remains in buffer
void shared_fifo(
    hls::stream<fifo_cmd> &cmd_in,
    hls::stream<fifo_resp> &resp_out,
    bool reset
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE axis port=cmd_in
#pragma HLS INTERFACE axis port=resp_out
#pragma HLS INTERFACE ap_none port=reset

    static data_t buffer[FIFO_DEPTH];
#pragma HLS BIND_STORAGE variable=buffer type=ram_1p
    static ptr_t head = 0;
    static ptr_t tail = 0;
    static ap_uint<5> count = 0;
    static ctx_id_t current_ctx = 0;

    // BUG: Reset only clears pointers, not buffer contents
    if (reset) {
        head = 0;
        tail = 0;
        count = 0;
        current_ctx = 0;
        // VULNERABILITY: buffer[] not cleared — old secrets persist
        return;
    }

    if (!cmd_in.empty()) {
        fifo_cmd cmd = cmd_in.read();
        fifo_resp resp;
        resp.valid = false;
        resp.empty = (count == 0);
        resp.full = (count == FIFO_DEPTH);
        resp.rdata = 0;

        // BUG: Context switch only resets pointers, not buffer data
        if (cmd.ctx_switch) {
            head = 0;
            tail = 0;
            count = 0;
            current_ctx = cmd.context;
            // VULNERABILITY: new context can read old data at buffer positions
        }

        if (cmd.push && count < FIFO_DEPTH) {
            buffer[tail] = cmd.wdata;
            tail++;
            count++;
        }

        if (cmd.pop && count > 0) {
            resp.rdata = buffer[head];
            // BUG: buffer[head] not overwritten — stale data remains
            head++;
            count--;
            resp.valid = true;
        }

        resp.empty = (count == 0);
        resp.full = (count == FIFO_DEPTH);
        resp_out.write(resp);
    }
}
