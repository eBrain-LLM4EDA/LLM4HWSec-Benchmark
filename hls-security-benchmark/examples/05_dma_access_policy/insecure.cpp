/*
 * Example 05: DMA Controller with No Access Policy (INSECURE)
 * Vulnerability: DMA can transfer data between any source/dest without restriction.
 *                No address range validation or privilege checking.
 * CWE-284: Improper Access Control
 * CWE-1234: Hardware Internal or Debug Modes Allow Override of Locks
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<32> data_t;
typedef ap_uint<32> addr_t;
typedef ap_uint<16> len_t;
typedef ap_uint<2>  chan_id_t;

// Memory-mapped regions
#define MMIO_SECURE_START  0x40000000
#define MMIO_SECURE_END    0x4000FFFF
#define DRAM_START         0x80000000
#define DRAM_END           0xFFFFFFFF

struct dma_descriptor {
    addr_t   src_addr;
    addr_t   dst_addr;
    len_t    length;
    chan_id_t channel;
    bool     debug_mode;  // BUG: debug mode bypasses all checks
};

struct dma_status {
    bool     done;
    bool     error;
};

// BUG: No source/destination address validation
// BUG: Debug mode flag disables any future security checks
// BUG: Any channel can access secure MMIO region
void dma_controller(
    hls::stream<dma_descriptor> &desc_in,
    hls::stream<dma_status> &status_out,
    volatile data_t *mem
) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE axis port=desc_in
#pragma HLS INTERFACE axis port=status_out
#pragma HLS INTERFACE m_axi port=mem offset=slave depth=65536

    if (!desc_in.empty()) {
        dma_descriptor desc = desc_in.read();
        dma_status stat;
        stat.done = false;
        stat.error = false;

        // VULNERABILITY: debug_mode bypasses everything
        // VULNERABILITY: no address range checks at all
        for (int i = 0; i < desc.length; i++) {
#pragma HLS PIPELINE II=1
            data_t val = mem[desc.src_addr + i];
            mem[desc.dst_addr + i] = val;
        }

        stat.done = true;
        status_out.write(stat);
    }
}
