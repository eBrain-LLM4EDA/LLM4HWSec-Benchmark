/*
 * Example 10: Bus Arbiter with No Temporal Isolation (INSECURE)
 * Vulnerability: Shared bus arbiter allows timing interference between
 *                security domains. High-priority secure traffic can be
 *                observed via bus contention timing by low-priority masters.
 * CWE-1189: Improper Isolation of Shared Resources on SoC
 */

#include <ap_int.h>
#include <hls_stream.h>

#define NUM_MASTERS 4

typedef ap_uint<32> data_t;
typedef ap_uint<32> addr_t;
typedef ap_uint<2>  master_id_t;

struct bus_req {
    master_id_t master;
    addr_t      addr;
    data_t      wdata;
    bool        wr_en;
    bool        is_secure;  // Security domain tag
};

struct bus_resp {
    data_t      rdata;
    bool        granted;
    master_id_t served_master;
};

struct bus_grant {
    master_id_t master;
    bool        valid;
};

// BUG: Priority arbiter — secure master always wins, creating observable contention
// BUG: Non-secure master can infer secure traffic by measuring grant latency
// BUG: No time partitioning — secure and non-secure share same time slots
// BUG: Grant history exposed in response (served_master field)
void bus_arbiter(
    hls::stream<bus_req> req_in[NUM_MASTERS],
    hls::stream<bus_resp> &resp_out,
    volatile data_t *shared_bus
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE axis port=req_in[0]
#pragma HLS INTERFACE axis port=req_in[1]
#pragma HLS INTERFACE axis port=req_in[2]
#pragma HLS INTERFACE axis port=req_in[3]
#pragma HLS INTERFACE axis port=resp_out
#pragma HLS INTERFACE m_axi port=shared_bus offset=slave depth=1024

    bus_resp resp;
    resp.granted = false;
    resp.rdata = 0;
    resp.served_master = 0;

    // VULNERABILITY: Fixed-priority arbitration — secure master (0) always first
    // Non-secure masters experience variable latency based on secure traffic
    for (int i = 0; i < NUM_MASTERS; i++) {
        if (!req_in[i].empty()) {
            bus_req r = req_in[i].read();

            if (r.wr_en) {
                shared_bus[r.addr] = r.wdata;
            } else {
                resp.rdata = shared_bus[r.addr];
            }

            resp.granted = true;
            resp.served_master = r.master;  // BUG: leaks which master was served
            resp_out.write(resp);
            break;  // BUG: first-come priority — creates contention side channel
        }
    }
}
