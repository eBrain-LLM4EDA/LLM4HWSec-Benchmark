/*
 * Example 10: Bus Arbiter with Temporal Isolation (SECURE)
 * Fix: Time-division multiplexing (TDM) between security domains.
 *      Secure and non-secure traffic in separate time slots.
 *      No cross-domain timing interference. Grant history not exposed.
 * Mitigates: CWE-1189
 */

#include <ap_int.h>
#include <hls_stream.h>

#define NUM_MASTERS 4
#define TDM_SLOTS 4  // Time slots per TDM frame

typedef ap_uint<32> data_t;
typedef ap_uint<32> addr_t;
typedef ap_uint<2>  master_id_t;
typedef ap_uint<2>  slot_t;

struct bus_req {
    master_id_t master;
    addr_t      addr;
    data_t      wdata;
    bool        wr_en;
    bool        is_secure;
};

struct bus_resp {
    data_t      rdata;
    bool        granted;
    // FIX: served_master field removed — no grant history leakage
};

// FIX: TDM schedule — maps time slots to master IDs
// Secure masters get dedicated slots, non-secure get separate slots
// Slot 0,2: secure (master 0,1)  Slot 1,3: non-secure (master 2,3)
static const master_id_t tdm_schedule[TDM_SLOTS] = { 0, 2, 1, 3 };
static const bool tdm_secure[TDM_SLOTS] = { true, false, true, false };

void bus_arbiter(
    hls::stream<bus_req> req_in[NUM_MASTERS],
    hls::stream<bus_resp> resp_out[NUM_MASTERS],  // FIX: per-master response
    volatile data_t *shared_bus
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE axis port=req_in[0]
#pragma HLS INTERFACE axis port=req_in[1]
#pragma HLS INTERFACE axis port=req_in[2]
#pragma HLS INTERFACE axis port=req_in[3]
#pragma HLS INTERFACE axis port=resp_out[0]
#pragma HLS INTERFACE axis port=resp_out[1]
#pragma HLS INTERFACE axis port=resp_out[2]
#pragma HLS INTERFACE axis port=resp_out[3]
#pragma HLS INTERFACE m_axi port=shared_bus offset=slave depth=1024

    static slot_t current_slot = 0;

    // FIX: TDM — each slot serves exactly one master
    master_id_t active_master = tdm_schedule[current_slot];

    bus_resp resp;
    resp.granted = false;
    resp.rdata = 0;

    if (!req_in[active_master].empty()) {
        bus_req r = req_in[active_master].read();

        // FIX: Verify security domain matches slot assignment
        if (r.is_secure == tdm_secure[current_slot]) {
            if (r.wr_en) {
                shared_bus[r.addr] = r.wdata;
            } else {
                resp.rdata = shared_bus[r.addr];
            }
            resp.granted = true;
        }
        // If domain mismatch, request is denied (resp.granted stays false)
    }

    // FIX: Always send response to active master (constant-time per slot)
    resp_out[active_master].write(resp);

    // FIX: Always advance slot — no variable-length arbitration
    current_slot = (current_slot + 1) % TDM_SLOTS;
}
