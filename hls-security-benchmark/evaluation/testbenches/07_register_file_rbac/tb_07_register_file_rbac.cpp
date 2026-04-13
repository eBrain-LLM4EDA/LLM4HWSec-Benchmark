/*
 * Testbench: 07_register_file_rbac
 * Tests register file access control.
 * Secure version has production_mode and hardware privilege table.
 */
#include <iostream>
#include <cstdlib>
#include "ap_int.h"
#include "hls_stream.h"

namespace secure {
    #include "/benchmark/examples/07_register_file_rbac/reference_secure.cpp"
}

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "07_register_file_rbac";

void report(const char* name, bool pass, const char* reason = "") {
    tests_total++;
    if (pass) { tests_passed++; std::cout << "TEST " << EXAMPLE_ID << " " << name << ": PASS\n"; }
    else { std::cout << "TEST " << EXAMPLE_ID << " " << name << ": FAIL " << reason << "\n"; }
}

void test_secure_master_key_write_read() {
    hls::stream<secure::reg_req> req;
    hls::stream<secure::reg_resp> resp;
    secure::reg_req r;

    // Master 0 (SECURE) writes key register 1
    r.master = 0; r.addr = 1; r.wdata = 0xDEADBEEF; r.wr_en = true;
    req.write(r);
    secure::register_file(req, resp, true);
    secure::reg_resp wr_resp = resp.read();

    // Master 0 reads it back
    r.master = 0; r.addr = 1; r.wdata = 0; r.wr_en = false;
    req.write(r);
    secure::register_file(req, resp, true);
    secure::reg_resp rd_resp = resp.read();

    bool pass = wr_resp.valid && rd_resp.valid && (rd_resp.rdata == 0xDEADBEEF);
    report("secure_key_rw", pass, "Secure master should read/write key registers");
}

void test_user_key_denied() {
    hls::stream<secure::reg_req> req;
    hls::stream<secure::reg_resp> resp;
    secure::reg_req r;

    // Master 2 (USER) tries to read key register 1
    r.master = 2; r.addr = 1; r.wdata = 0; r.wr_en = false;
    req.write(r);
    secure::register_file(req, resp, true);
    secure::reg_resp rd_resp = resp.read();

    report("user_key_denied", rd_resp.access_denied && rd_resp.rdata == 0,
           "User should be denied access to key registers");
}

void test_user_general_read() {
    hls::stream<secure::reg_req> req;
    hls::stream<secure::reg_resp> resp;
    secure::reg_req r;

    // Master 0 writes general register 10
    r.master = 0; r.addr = 10; r.wdata = 0x42; r.wr_en = true;
    req.write(r);
    secure::register_file(req, resp, true);
    resp.read();

    // Master 2 (USER) reads general register 10 — should be allowed (read-only)
    r.master = 2; r.addr = 10; r.wdata = 0; r.wr_en = false;
    req.write(r);
    secure::register_file(req, resp, true);
    secure::reg_resp rd_resp = resp.read();

    report("user_general_read", rd_resp.valid && rd_resp.rdata == 0x42,
           "User should be able to read general registers");
}

void test_user_general_write_denied() {
    hls::stream<secure::reg_req> req;
    hls::stream<secure::reg_resp> resp;
    secure::reg_req r;

    // Master 2 (USER) tries to write general register — should be denied
    r.master = 2; r.addr = 10; r.wdata = 0xFF; r.wr_en = true;
    req.write(r);
    secure::register_file(req, resp, true);
    secure::reg_resp wr_resp = resp.read();

    report("user_general_write_denied", wr_resp.access_denied,
           "User should not be able to write general registers");
}

void test_debug_locked_production() {
    hls::stream<secure::reg_req> req;
    hls::stream<secure::reg_resp> resp;
    secure::reg_req r;

    // Master 0 (SECURE) tries to access debug register in production mode
    r.master = 0; r.addr = 62; r.wdata = 0; r.wr_en = false;
    req.write(r);
    secure::register_file(req, resp, true);  // production_mode = true
    secure::reg_resp rd_resp = resp.read();

    report("debug_locked_prod", rd_resp.access_denied,
           "Debug register should be locked in production mode");
}

int main() {
    test_secure_master_key_write_read();
    test_user_key_denied();
    test_user_general_read();
    test_user_general_write_denied();
    test_debug_locked_production();
    std::cout << "SUMMARY " << EXAMPLE_ID << ": " << tests_passed << "/" << tests_total << " passed\n";
    return (tests_passed == tests_total) ? 0 : 1;
}
