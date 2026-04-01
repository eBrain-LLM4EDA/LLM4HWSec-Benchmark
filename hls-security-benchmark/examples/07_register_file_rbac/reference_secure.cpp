/*
 * Example 07: Register File with Role-Based Access Control (SECURE)
 * Fix: Hardware-enforced privilege table per master ID.
 *      Debug/test registers locked in production mode.
 *      Key registers read-restricted. Status register write-protected.
 * Mitigates: CWE-284, CWE-1191
 */

#include <ap_int.h>
#include <hls_stream.h>

#define NUM_REGS 64
#define SECURITY_CFG_REG  0
#define KEY_REG_START     1
#define KEY_REG_END       4
#define STATUS_REG        5
#define DEBUG_REG         62
#define TEST_MODE_REG     63

typedef ap_uint<32> data_t;
typedef ap_uint<6>  reg_addr_t;
typedef ap_uint<3>  master_id_t;

#define PRIV_USER    0
#define PRIV_SUPER   1
#define PRIV_SECURE  2

struct reg_req {
    master_id_t  master;
    reg_addr_t   addr;
    data_t       wdata;
    bool         wr_en;
};

struct reg_resp {
    data_t  rdata;
    bool    valid;
    bool    access_denied;
};

// FIX: Hardware privilege table — maps master_id to privilege level
// This is set at synthesis time or by secure boot, NOT by the master itself
static const ap_uint<2> master_privilege_table[8] = {
    PRIV_SECURE, // Master 0: secure processor
    PRIV_SUPER,  // Master 1: supervisor
    PRIV_USER,   // Master 2: user core A
    PRIV_USER,   // Master 3: user core B
    PRIV_USER,   // Master 4: DMA
    PRIV_USER,   // Master 5: peripheral
    PRIV_USER,   // Master 6: unused
    PRIV_USER    // Master 7: unused
};

// FIX: Access policy function
// Returns: 0=denied, 1=read-only, 2=read-write
ap_uint<2> get_access(master_id_t master, reg_addr_t addr, bool production_mode) {
    ap_uint<2> priv = master_privilege_table[master];

    // Security config register: SECURE write, SUPER+ read
    if (addr == SECURITY_CFG_REG) {
        if (priv == PRIV_SECURE) return 2;      // read-write
        if (priv >= PRIV_SUPER) return 1;        // read-only
        return 0;                                 // denied
    }

    // Key registers: SECURE only
    if (addr >= KEY_REG_START && addr <= KEY_REG_END) {
        if (priv == PRIV_SECURE) return 2;
        return 0;
    }

    // Status register: read-only for all, write only by SECURE
    if (addr == STATUS_REG) {
        if (priv == PRIV_SECURE) return 2;
        return 1;
    }

    // Debug/test registers: SECURE only, and disabled in production
    if (addr == DEBUG_REG || addr == TEST_MODE_REG) {
        if (production_mode) return 0;           // FIX: locked in production
        if (priv == PRIV_SECURE) return 2;
        return 0;
    }

    // General registers: SUPER+ can write, all can read
    if (priv >= PRIV_SUPER) return 2;
    return 1;  // USER: read-only for general regs
}

void register_file(
    hls::stream<reg_req> &req_in,
    hls::stream<reg_resp> &resp_out,
    bool production_mode  // FIX: set by secure boot, locks debug/test
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE axis port=req_in
#pragma HLS INTERFACE axis port=resp_out
#pragma HLS INTERFACE ap_none port=production_mode

    static data_t regs[NUM_REGS];
#pragma HLS BIND_STORAGE variable=regs type=ram_2p

    if (!req_in.empty()) {
        reg_req r = req_in.read();
        reg_resp resp;
        resp.access_denied = false;

        ap_uint<2> access = get_access(r.master, r.addr, production_mode);

        if (r.wr_en) {
            if (access >= 2) {
                regs[r.addr] = r.wdata;
                resp.rdata = 0;
                resp.valid = true;
            } else {
                resp.rdata = 0;
                resp.valid = false;
                resp.access_denied = true;
            }
        } else {
            if (access >= 1) {
                resp.rdata = regs[r.addr];
                resp.valid = true;
            } else {
                resp.rdata = 0;
                resp.valid = false;
                resp.access_denied = true;
            }
        }

        resp_out.write(resp);
    }
}
