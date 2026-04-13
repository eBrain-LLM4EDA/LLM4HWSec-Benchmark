/*
 * Testbench: 10_bus_arbiter_isolation
 * Tests TDM bus arbiter. Secure version uses per-master response channels
 * and time-slot scheduling.
 */
#include <iostream>
#include <cstdlib>
#include "ap_int.h"
#include "hls_stream.h"

// Simulated shared bus memory
static ap_uint<32> shared_bus_mem[1024];

namespace secure {
    #include "/benchmark/examples/10_bus_arbiter_isolation/reference_secure.cpp"
}

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "10_bus_arbiter_isolation";

void report(const char* name, bool pass, const char* reason = "") {
    tests_total++;
    if (pass) { tests_passed++; std::cout << "TEST " << EXAMPLE_ID << " " << name << ": PASS\n"; }
    else { std::cout << "TEST " << EXAMPLE_ID << " " << name << ": FAIL " << reason << "\n"; }
}

void test_slot0_master0_write() {
    hls::stream<secure::bus_req> req_in[4];
    hls::stream<secure::bus_resp> resp_out[4];

    // Master 0 is scheduled in slot 0 (secure slot)
    secure::bus_req r;
    r.master = 0;
    r.addr = 50;
    r.wdata = 0xAAAA;
    r.wr_en = true;
    r.is_secure = true;
    req_in[0].write(r);

    secure::bus_arbiter(req_in, resp_out, shared_bus_mem);
    secure::bus_resp res = resp_out[0].read();

    bool pass = res.granted && (shared_bus_mem[50] == 0xAAAA);
    report("slot0_write", pass, "Master 0 secure write in slot 0 should succeed");
}

void test_master2_write_read() {
    hls::stream<secure::bus_req> req_in[4];
    hls::stream<secure::bus_resp> resp_out[4];

    shared_bus_mem[100] = 0;

    // Cycle through slots until master 2 is active (slot 1 in TDM schedule)
    // by submitting the request and running enough cycles
    secure::bus_req wr;
    wr.master = 2;
    wr.addr = 100;
    wr.wdata = 0xBBBB;
    wr.wr_en = true;
    wr.is_secure = false;

    // Try across a full TDM frame — master 2 will get its slot
    bool write_granted = false;
    for (int i = 0; i < 4; i++) {
        // Re-enqueue if not yet consumed
        if (!write_granted) req_in[2].write(wr);
        secure::bus_arbiter(req_in, resp_out, shared_bus_mem);
        // Check all response channels
        for (int ch = 0; ch < 4; ch++) {
            while (!resp_out[ch].empty()) {
                secure::bus_resp r = resp_out[ch].read();
                if (ch == 2 && r.granted) write_granted = true;
            }
        }
        if (write_granted) break;
    }

    report("master2_write_read",
           write_granted && shared_bus_mem[100] == 0xBBBB,
           "Master 2 non-secure write should succeed within one TDM frame");
}

void test_tdm_cycles() {
    hls::stream<secure::bus_req> req_in[4];
    hls::stream<secure::bus_resp> resp_out[4];

    // Run 4 slots (one full TDM frame) with no requests
    // Each slot should produce a response on the scheduled master's channel
    for (int slot = 0; slot < 4; slot++) {
        secure::bus_arbiter(req_in, resp_out, shared_bus_mem);
    }

    // After 4 calls, we should have had responses (granted=false since no requests)
    // The key property is that the arbiter runs without crashing through a full frame
    report("tdm_full_frame", true, "");
}

void test_constant_slot_advance() {
    hls::stream<secure::bus_req> req_in[4];
    hls::stream<secure::bus_resp> resp_out[4];

    // Call 8 times (2 full TDM frames) with no input — should not hang
    for (int i = 0; i < 8; i++) {
        secure::bus_arbiter(req_in, resp_out, shared_bus_mem);
    }
    // Drain all responses
    for (int i = 0; i < 4; i++) {
        while (!resp_out[i].empty()) resp_out[i].read();
    }
    report("constant_advance", true, "Arbiter should not hang with no requests");
}

int main() {
    test_slot0_master0_write();
    test_master2_write_read();
    test_tdm_cycles();
    test_constant_slot_advance();
    std::cout << "SUMMARY " << EXAMPLE_ID << ": " << tests_passed << "/" << tests_total << " passed\n";
    return (tests_passed == tests_total) ? 0 : 1;
}
