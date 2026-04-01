/*
 * Example 09: Shared FIFO Buffer with Data Sanitization (SECURE)
 * Fix: Buffer cleared on reset and context switch.
 *      Popped entries overwritten with zero.
 * Mitigates: CWE-226, CWE-1271
 */

#include <ap_int.h>
#include <hls_stream.h>

#define FIFO_DEPTH 16

typedef ap_uint<64> data_t;
typedef ap_uint<4>  ptr_t;
typedef ap_uint<2>  ctx_id_t;

struct fifo_cmd {
    ctx_id_t  context;
    data_t    wdata;
    bool      push;
    bool      pop;
    bool      ctx_switch;
};

struct fifo_resp {
    data_t  rdata;
    bool    valid;
    bool    empty;
    bool    full;
};

// FIX: Helper to clear entire buffer
void sanitize_buffer(data_t buffer[FIFO_DEPTH]) {
    for (int i = 0; i < FIFO_DEPTH; i++) {
#pragma HLS UNROLL
        buffer[i] = 0;
    }
}

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

    // FIX: Reset clears buffer contents AND pointers
    if (reset) {
        sanitize_buffer(buffer);
        head = 0;
        tail = 0;
        count = 0;
        current_ctx = 0;
        return;
    }

    if (!cmd_in.empty()) {
        fifo_cmd cmd = cmd_in.read();
        fifo_resp resp;
        resp.valid = false;
        resp.empty = (count == 0);
        resp.full = (count == FIFO_DEPTH);
        resp.rdata = 0;

        // FIX: Context switch sanitizes entire buffer
        if (cmd.ctx_switch) {
            sanitize_buffer(buffer);
            head = 0;
            tail = 0;
            count = 0;
            current_ctx = cmd.context;
        }

        if (cmd.push && count < FIFO_DEPTH) {
            buffer[tail] = cmd.wdata;
            tail++;
            count++;
        }

        if (cmd.pop && count > 0) {
            resp.rdata = buffer[head];
            buffer[head] = 0;  // FIX: Clear popped entry immediately
            head++;
            count--;
            resp.valid = true;
        }

        resp.empty = (count == 0);
        resp.full = (count == FIFO_DEPTH);
        resp_out.write(resp);
    }
}
