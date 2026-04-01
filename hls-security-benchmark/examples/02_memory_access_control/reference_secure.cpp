/*
 * Example 02: Memory Interface Access Control (SECURE)
 * Fix: Address-range access control per requestor ID.
 *      Secure region restricted to privileged requestor (ID=0).
 * Mitigates: CWE-284
 */

#include <ap_int.h>
#include <hls_stream.h>

#define MEM_SIZE 1024
#define SECURE_REGION_START 768
#define SECURE_REGION_END 1023

typedef ap_uint<32> data_t;
typedef ap_uint<10> addr_t;
typedef ap_uint<2>  req_id_t;

// Access control policy: which requestor IDs can access secure region
#define PRIVILEGED_ID 0

struct mem_req {
    req_id_t id;
    addr_t   addr;
    data_t   wdata;
    bool     wr_en;
};

struct mem_resp {
    data_t   rdata;
    bool     valid;
    bool     access_denied;
};

// FIX: Inline access control check
bool is_secure_region(addr_t addr) {
    return (addr >= SECURE_REGION_START && addr <= SECURE_REGION_END);
}

bool has_privilege(req_id_t id, addr_t addr) {
    if (is_secure_region(addr)) {
        return (id == PRIVILEGED_ID);
    }
    return true;  // Non-secure region: all requestors allowed
}

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
        resp.access_denied = false;

        // FIX: Access control check before any memory operation
        if (!has_privilege(r.id, r.addr)) {
            resp.rdata = 0;          // Return zero, not memory contents
            resp.valid = false;
            resp.access_denied = true;
        } else if (r.wr_en) {
            memory[r.addr] = r.wdata;
            resp.rdata = 0;
            resp.valid = true;
        } else {
            resp.rdata = memory[r.addr];
            resp.valid = true;
        }

        resp_out.write(resp);
    }
}
