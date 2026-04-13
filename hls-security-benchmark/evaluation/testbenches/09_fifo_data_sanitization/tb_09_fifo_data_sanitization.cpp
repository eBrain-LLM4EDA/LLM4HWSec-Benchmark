/*
 * Testbench: 09_fifo_data_sanitization
 * Tests FIFO push/pop, context switch sanitization, and reset behavior.
 */
#include <iostream>
#include <cstdlib>
#include "ap_int.h"
#include "hls_stream.h"

namespace secure {
    #include "/benchmark/examples/09_fifo_data_sanitization/reference_secure.cpp"
}

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "09_fifo_data_sanitization";

void report(const char* name, bool pass, const char* reason = "") {
    tests_total++;
    if (pass) { tests_passed++; std::cout << "TEST " << EXAMPLE_ID << " " << name << ": PASS\n"; }
    else { std::cout << "TEST " << EXAMPLE_ID << " " << name << ": FAIL " << reason << "\n"; }
}

void test_push_pop() {
    hls::stream<secure::fifo_cmd> cmd;
    hls::stream<secure::fifo_resp> resp;

    // Reset first
    secure::shared_fifo(cmd, resp, true);

    // Push 0xDEAD
    secure::fifo_cmd c;
    c.context = 0; c.wdata = 0xDEAD; c.push = true; c.pop = false; c.ctx_switch = false;
    cmd.write(c);
    secure::shared_fifo(cmd, resp, false);
    resp.read();

    // Pop
    c.push = false; c.pop = true; c.wdata = 0;
    cmd.write(c);
    secure::shared_fifo(cmd, resp, false);
    secure::fifo_resp r = resp.read();

    report("push_pop", r.valid && r.rdata == 0xDEAD, "Should pop 0xDEAD");
}

void test_fifo_ordering() {
    hls::stream<secure::fifo_cmd> cmd;
    hls::stream<secure::fifo_resp> resp;

    secure::shared_fifo(cmd, resp, true);  // reset

    // Push 3 values
    for (int i = 1; i <= 3; i++) {
        secure::fifo_cmd c;
        c.context = 0; c.wdata = i * 100; c.push = true; c.pop = false; c.ctx_switch = false;
        cmd.write(c);
        secure::shared_fifo(cmd, resp, false);
        resp.read();
    }

    // Pop and verify FIFO order
    bool correct = true;
    for (int i = 1; i <= 3; i++) {
        secure::fifo_cmd c;
        c.context = 0; c.wdata = 0; c.push = false; c.pop = true; c.ctx_switch = false;
        cmd.write(c);
        secure::shared_fifo(cmd, resp, false);
        secure::fifo_resp r = resp.read();
        if (!r.valid || r.rdata != (ap_uint<64>)(i * 100)) correct = false;
    }
    report("fifo_order", correct, "FIFO should return items in order");
}

void test_empty_pop() {
    hls::stream<secure::fifo_cmd> cmd;
    hls::stream<secure::fifo_resp> resp;

    secure::shared_fifo(cmd, resp, true);  // reset

    // Pop from empty FIFO
    secure::fifo_cmd c;
    c.context = 0; c.wdata = 0; c.push = false; c.pop = true; c.ctx_switch = false;
    cmd.write(c);
    secure::shared_fifo(cmd, resp, false);
    secure::fifo_resp r = resp.read();

    report("empty_pop", !r.valid, "Pop from empty should return invalid");
}

void test_context_switch_clears() {
    hls::stream<secure::fifo_cmd> cmd;
    hls::stream<secure::fifo_resp> resp;

    secure::shared_fifo(cmd, resp, true);  // reset

    // Push data in context 0
    secure::fifo_cmd c;
    c.context = 0; c.wdata = 0x5EC; c.push = true; c.pop = false; c.ctx_switch = false;
    c.wdata = 0x5EC;  // fix hex
    cmd.write(c);
    secure::shared_fifo(cmd, resp, false);
    resp.read();

    // Switch to context 1 — should clear buffer
    c.context = 1; c.push = false; c.pop = false; c.ctx_switch = true;
    cmd.write(c);
    secure::shared_fifo(cmd, resp, false);
    resp.read();

    // Pop in new context — should be empty
    c.ctx_switch = false; c.pop = true;
    cmd.write(c);
    secure::shared_fifo(cmd, resp, false);
    secure::fifo_resp r = resp.read();

    report("ctx_switch_clears", !r.valid, "Context switch should clear FIFO");
}

int main() {
    test_push_pop();
    test_fifo_ordering();
    test_empty_pop();
    test_context_switch_clears();
    std::cout << "SUMMARY " << EXAMPLE_ID << ": " << tests_passed << "/" << tests_total << " passed\n";
    return (tests_passed == tests_total) ? 0 : 1;
}
