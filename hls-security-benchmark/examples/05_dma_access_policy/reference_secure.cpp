/*
 * Example 05: DMA Controller with Access Policy (SECURE)
 * Fix: Address range validation, channel-based access control,
 *      debug mode removed.
 * Mitigates: CWE-284, CWE-1234
 */

#include <ap_int.h>
#include <hls_stream.h>

typedef ap_uint<32> data_t;
typedef ap_uint<32> addr_t;
typedef ap_uint<16> len_t;
typedef ap_uint<2>  chan_id_t;

#define MMIO_SECURE_START  0x40000000
#define MMIO_SECURE_END    0x4000FFFF
#define DRAM_START         0x80000000
#define DRAM_END           0xFFFFFFFF
#define PRIVILEGED_CHAN    0

struct dma_descriptor {
    addr_t   src_addr;
    addr_t   dst_addr;
    len_t    length;
    chan_id_t channel;
    // FIX: debug_mode field removed entirely
};

struct dma_status {
    bool     done;
    bool     error;
    bool     access_denied;
};

// FIX: Address range check
bool is_secure_mmio(addr_t addr, len_t length) {
    addr_t end_addr = addr + length - 1;
    return (addr >= MMIO_SECURE_START && addr <= MMIO_SECURE_END) ||
           (end_addr >= MMIO_SECURE_START && end_addr <= MMIO_SECURE_END);
}

// FIX: Address bounds check
bool is_valid_range(addr_t addr, len_t length) {
    addr_t end_addr = addr + length - 1;
    return (end_addr >= addr);  // overflow check
}

// FIX: Channel-based access policy
bool channel_authorized(chan_id_t chan, addr_t src, addr_t dst, len_t len) {
    bool src_secure = is_secure_mmio(src, len);
    bool dst_secure = is_secure_mmio(dst, len);
    if (src_secure || dst_secure) {
        return (chan == PRIVILEGED_CHAN);
    }
    return true;
}

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
        stat.access_denied = false;

        // FIX: Validate address ranges
        if (!is_valid_range(desc.src_addr, desc.length) ||
            !is_valid_range(desc.dst_addr, desc.length)) {
            stat.error = true;
            stat.done = true;
            status_out.write(stat);
            return;
        }

        // FIX: Check channel authorization
        if (!channel_authorized(desc.channel, desc.src_addr, desc.dst_addr, desc.length)) {
            stat.access_denied = true;
            stat.done = true;
            status_out.write(stat);
            return;
        }

        for (int i = 0; i < desc.length; i++) {
#pragma HLS PIPELINE II=1
            data_t val = mem[desc.src_addr + i];
            mem[desc.dst_addr + i] = val;
        }

        stat.done = true;
        status_out.write(stat);
    }
}
