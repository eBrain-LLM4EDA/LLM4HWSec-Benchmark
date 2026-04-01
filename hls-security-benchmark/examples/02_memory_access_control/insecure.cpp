/*
 * Example 02: Memory Interface Access Control (INSECURE)
 * Vulnerability: No access control on shared memory interface.
 *                Any requestor can read/write any address region.
 * CWE-284: Improper Access Control
 */

#include <ap_int.h>
#include <hls_stream.h>

#define MEM_SIZE 1024
#define SECURE_REGION_START 768
#define SECURE_REGION_END 1023

typedef ap_uint<32> data_t;
typedef ap_uint<10> addr_t;
typedef ap_uint<2>  req_id_t;  // 4 possible requestors

struct mem_req {
    req_id_t id;
    addr_t   addr;
    data_t   wdata;
    bool     wr_en;
};

struct mem_resp {
    data_t   rdata;
    bool     valid;
};

// BUG: No access control check — any requestor can access secure region
// BUG: No privilege level enforcement
// BUG: Write to secure region not restricted
void memory_controller(
    hls::stream<mem_req> &req_in,
    hls::stream<mem_resp> &resp_out
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE axis port=req_in
#pragma HLS INTERFACE axis port=resp_out

    static data_t memory[MEM_SIZE];
#pragma HLS BIND_STORAGE variable=memory type=ram_2p

    if (!req_in.empty()) {
        mem_req r = req_in.read();
        mem_resp resp;

        // VULNERABILITY: No access control — all requestors treated equally
        if (r.wr_en) {
            memory[r.addr] = r.wdata;  // BUG: any ID can write secure region
            resp.rdata = 0;
            resp.valid = true;
        } else {
            resp.rdata = memory[r.addr];  // BUG: any ID can read secure region
            resp.valid = true;
        }

        resp_out.write(resp);
    }
}
