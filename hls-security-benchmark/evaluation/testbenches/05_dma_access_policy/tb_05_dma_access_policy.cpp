/*
 * Testbench: 05_dma_access_policy
 * Tests DMA controller access policy enforcement.
 * Secure version denies unprivileged access to secure MMIO region.
 */
#include <iostream>
#include <cstdlib>
#include "ap_int.h"
#include "hls_stream.h"

// DMA uses volatile data_t *mem — provide a simulated memory
static ap_uint<32> sim_mem[65536];

namespace secure {
    #include "/benchmark/examples/05_dma_access_policy/reference_secure.cpp"
}

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "05_dma_access_policy";

void report(const char* name, bool pass, const char* reason = "") {
    tests_total++;
    if (pass) { tests_passed++; std::cout << "TEST " << EXAMPLE_ID << " " << name << ": PASS\n"; }
    else { std::cout << "TEST " << EXAMPLE_ID << " " << name << ": FAIL " << reason << "\n"; }
}

void test_privileged_secure_transfer() {
    hls::stream<secure::dma_descriptor> desc_in;
    hls::stream<secure::dma_status> status_out;

    // Write source data
    sim_mem[0] = 0xCAFE;
    sim_mem[1] = 0xBEEF;

    secure::dma_descriptor d;
    d.src_addr = 0;
    d.dst_addr = 100;
    d.length = 2;
    d.channel = 0;  // privileged
    desc_in.write(d);

    secure::dma_controller(desc_in, status_out, sim_mem);
    secure::dma_status st = status_out.read();

    bool pass = st.done && !st.error && !st.access_denied;
    pass = pass && (sim_mem[100] == 0xCAFE) && (sim_mem[101] == 0xBEEF);
    report("privileged_transfer", pass, "Privileged DMA transfer failed");
}

void test_unprivileged_dram_allowed() {
    hls::stream<secure::dma_descriptor> desc_in;
    hls::stream<secure::dma_status> status_out;

    sim_mem[200] = 0x1234;
    secure::dma_descriptor d;
    d.src_addr = 200;
    d.dst_addr = 300;
    d.length = 1;
    d.channel = 2;  // unprivileged
    desc_in.write(d);

    secure::dma_controller(desc_in, status_out, sim_mem);
    secure::dma_status st = status_out.read();

    report("unpriv_dram", st.done && !st.access_denied, "Unpriv DRAM transfer should succeed");
}

void test_basic_done() {
    hls::stream<secure::dma_descriptor> desc_in;
    hls::stream<secure::dma_status> status_out;

    secure::dma_descriptor d;
    d.src_addr = 0;
    d.dst_addr = 10;
    d.length = 1;
    d.channel = 0;
    desc_in.write(d);

    secure::dma_controller(desc_in, status_out, sim_mem);
    secure::dma_status st = status_out.read();
    report("basic_done", st.done, "Transfer should complete");
}

int main() {
    test_privileged_secure_transfer();
    test_unprivileged_dram_allowed();
    test_basic_done();
    std::cout << "SUMMARY " << EXAMPLE_ID << ": " << tests_passed << "/" << tests_total << " passed\n";
    return (tests_passed == tests_total) ? 0 : 1;
}
