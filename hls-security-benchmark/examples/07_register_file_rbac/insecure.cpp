/*
 * Example 07: Register File with No Role-Based Access Control (INSECURE)
 * Vulnerability: Any master can read/write any register including security-critical ones.
 *                No privilege levels, no register locking.
 * CWE-284: Improper Access Control
 * CWE-1191: On-Chip Debug and Test Interface With Improper Access Control
 */

#include <ap_int.h>
#include <hls_stream.h>

#define NUM_REGS 64
#define SECURITY_CFG_REG  0   // Security configuration
#define KEY_REG_START     1   // Key storage registers 1-4
#define KEY_REG_END       4
#define STATUS_REG        5   // Status (read-only intended)
#define DEBUG_REG         62  // Debug register
#define TEST_MODE_REG     63  // Test mode control

typedef ap_uint<32> data_t;
typedef ap_uint<6>  reg_addr_t;
typedef ap_uint<3>  master_id_t;

// Privilege levels
#define PRIV_USER    0
#define PRIV_SUPER   1
#define PRIV_SECURE  2

struct reg_req {
    master_id_t  master;
    ap_uint<2>   privilege;   // Claimed privilege (not verified!)
    reg_addr_t   addr;
    data_t       wdata;
    bool         wr_en;
};

struct reg_resp {
    data_t  rdata;
    bool    valid;
};

// BUG: No privilege verification — master self-declares privilege level
// BUG: Debug/test registers accessible without restriction
// BUG: Security config register writable by unprivileged masters
// BUG: Key registers readable by any master
void register_file(
    hls::stream<reg_req> &req_in,
    hls::stream<reg_resp> &resp_out
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE axis port=req_in
#pragma HLS INTERFACE axis port=resp_out

    static data_t regs[NUM_REGS];
#pragma HLS BIND_STORAGE variable=regs type=ram_2p

    if (!req_in.empty()) {
        reg_req r = req_in.read();
        reg_resp resp;

        // VULNERABILITY: No access control at all
        if (r.wr_en) {
            regs[r.addr] = r.wdata;  // BUG: any master writes any register
            resp.rdata = 0;
        } else {
            resp.rdata = regs[r.addr];  // BUG: any master reads any register
        }
        resp.valid = true;

        resp_out.write(resp);
    }
}
