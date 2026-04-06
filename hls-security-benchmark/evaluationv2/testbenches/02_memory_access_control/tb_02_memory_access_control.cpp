/*
 * Testbench: 02_memory_access_control
 *
 * Tests functional equivalence between insecure and secure memory controllers.
 * Verifies:
 *   1. Non-secure reads/writes work identically on both versions.
 *   2. Secure version denies unprivileged access to secure region.
 *   3. Secure version allows privileged access to secure region.
 *
 * Compile: g++ -std=c++17 -I../../sim_backend/hls_stubs/ tb_02_memory_access_control.cpp -o tb_02
 */

#include <iostream>
#include <cstdlib>
#include <cassert>
#include <cstring>

// ---- Include HLS stubs ----
#include "ap_int.h"
#include "hls_stream.h"

// ---- We include both DUTs by wrapping them in namespaces ----

// The insecure version
namespace insecure {
    #include "../../examples/02_memory_access_control/insecure.cpp"
}

// The secure version
namespace secure {
    #include "../../examples/02_memory_access_control/reference_secure.cpp"
}

// ---- Test infrastructure ----

static int tests_passed = 0;
static int tests_total = 0;
static const char* EXAMPLE_ID = "02_memory_access_control";

void report(const char* vector_name, bool pass, const char* fail_reason = "") {
    tests_total++;
    if (pass) {
        tests_passed++;
        std::cout << "TEST " << EXAMPLE_ID << " " << vector_name << ": PASS" << std::endl;
    } else {
        std::cout << "TEST " << EXAMPLE_ID << " " << vector_name << ": FAIL "
                  << fail_reason << std::endl;
    }
}


// ---- Test vectors ----

void test_nonsecure_write_read() {
    /*
     * Write to non-secure address (addr=100), then read it back.
     * Both insecure and secure versions should return the same data.
     */

    // --- Insecure ---
    hls::stream<insecure::mem_req> i_req("i_req");
    hls::stream<insecure::mem_resp> i_resp("i_resp");

    insecure::mem_req wr;
    wr.id = 2;  // unprivileged
    wr.addr = 100;
    wr.wdata = 0xDEADBEEF;
    wr.wr_en = true;
    i_req.write(wr);
    insecure::memory_controller(i_req, i_resp);
    i_resp.read();  // discard write response

    insecure::mem_req rd;
    rd.id = 2;
    rd.addr = 100;
    rd.wdata = 0;
    rd.wr_en = false;
    i_req.write(rd);
    insecure::memory_controller(i_req, i_resp);
    insecure::mem_resp i_result = i_resp.read();

    // --- Secure ---
    hls::stream<secure::mem_req> s_req("s_req");
    hls::stream<secure::mem_resp> s_resp("s_resp");

    secure::mem_req s_wr;
    s_wr.id = 2;
    s_wr.addr = 100;
    s_wr.wdata = 0xDEADBEEF;
    s_wr.wr_en = true;
    s_req.write(s_wr);
    secure::memory_controller(s_req, s_resp);
    s_resp.read();

    secure::mem_req s_rd;
    s_rd.id = 2;
    s_rd.addr = 100;
    s_rd.wdata = 0;
    s_rd.wr_en = false;
    s_req.write(s_rd);
    secure::memory_controller(s_req, s_resp);
    secure::mem_resp s_result = s_resp.read();

    // Compare: both should return 0xDEADBEEF, valid=true
    bool pass = (i_result.rdata == s_result.rdata)
             && (s_result.valid == true)
             && (s_result.rdata == 0xDEADBEEF);
    report("nonsecure_write_read", pass,
           pass ? "" : "Non-secure region read mismatch");
}


void test_privileged_secure_access() {
    /*
     * Privileged master (id=0) writes to secure region (addr=800),
     * then reads it back. Should succeed on both versions.
     */
    hls::stream<secure::mem_req> s_req("s_req");
    hls::stream<secure::mem_resp> s_resp("s_resp");

    secure::mem_req wr;
    wr.id = 0;  // privileged
    wr.addr = 800;
    wr.wdata = 0x12345678;
    wr.wr_en = true;
    s_req.write(wr);
    secure::memory_controller(s_req, s_resp);
    s_resp.read();

    secure::mem_req rd;
    rd.id = 0;
    rd.addr = 800;
    rd.wdata = 0;
    rd.wr_en = false;
    s_req.write(rd);
    secure::memory_controller(s_req, s_resp);
    secure::mem_resp result = s_resp.read();

    bool pass = (result.valid == true)
             && (result.rdata == 0x12345678)
             && (result.access_denied == false);
    report("privileged_secure_access", pass,
           pass ? "" : "Privileged access to secure region failed");
}


void test_unprivileged_secure_read_denied() {
    /*
     * Unprivileged master (id=2) attempts to read secure region (addr=800).
     * Secure version should deny; insecure would allow.
     */
    hls::stream<secure::mem_req> s_req("s_req");
    hls::stream<secure::mem_resp> s_resp("s_resp");

    // First, write with privileged master so there's data
    secure::mem_req wr;
    wr.id = 0;
    wr.addr = 800;
    wr.wdata = 0xSECRE77;
    wr.wr_en = true;
    s_req.write(wr);
    secure::memory_controller(s_req, s_resp);
    s_resp.read();

    // Now unprivileged read
    secure::mem_req rd;
    rd.id = 2;  // unprivileged
    rd.addr = 800;
    rd.wdata = 0;
    rd.wr_en = false;
    s_req.write(rd);
    secure::memory_controller(s_req, s_resp);
    secure::mem_resp result = s_resp.read();

    // Should be denied: rdata=0, valid=false, access_denied=true
    bool pass = (result.rdata == 0)
             && (result.valid == false)
             && (result.access_denied == true);
    report("unprivileged_secure_read_denied", pass,
           pass ? "" : "Unprivileged read to secure region was not denied");
}


void test_unprivileged_secure_write_denied() {
    /*
     * Unprivileged master (id=3) attempts to write secure region (addr=900).
     */
    hls::stream<secure::mem_req> s_req("s_req");
    hls::stream<secure::mem_resp> s_resp("s_resp");

    secure::mem_req wr;
    wr.id = 3;
    wr.addr = 900;
    wr.wdata = 0xBAD00BAD;
    wr.wr_en = true;
    s_req.write(wr);
    secure::memory_controller(s_req, s_resp);
    secure::mem_resp result = s_resp.read();

    bool pass = (result.valid == false) && (result.access_denied == true);
    report("unprivileged_secure_write_denied", pass,
           pass ? "" : "Unprivileged write to secure region was not denied");
}


void test_boundary_addresses() {
    /*
     * Test boundary: addr=767 (last non-secure) should be allowed,
     *                addr=768 (first secure) should be denied for unpriv.
     */
    hls::stream<secure::mem_req> s_req("s_req");
    hls::stream<secure::mem_resp> s_resp("s_resp");

    // addr=767: should succeed
    secure::mem_req rd1;
    rd1.id = 2;
    rd1.addr = 767;
    rd1.wdata = 0;
    rd1.wr_en = false;
    s_req.write(rd1);
    secure::memory_controller(s_req, s_resp);
    secure::mem_resp r1 = s_resp.read();
    bool pass1 = (r1.valid == true) && (r1.access_denied == false);

    // addr=768: should be denied
    secure::mem_req rd2;
    rd2.id = 2;
    rd2.addr = 768;
    rd2.wdata = 0;
    rd2.wr_en = false;
    s_req.write(rd2);
    secure::memory_controller(s_req, s_resp);
    secure::mem_resp r2 = s_resp.read();
    bool pass2 = (r2.valid == false) && (r2.access_denied == true);

    report("boundary_767_allowed", pass1,
           pass1 ? "" : "Addr 767 should be allowed for unpriv");
    report("boundary_768_denied", pass2,
           pass2 ? "" : "Addr 768 should be denied for unpriv");
}


void test_all_requestors_nonsecure() {
    /*
     * All 4 requestors write/read non-secure region.
     * All should succeed identically.
     */
    bool all_pass = true;
    for (int id = 0; id < 4; id++) {
        hls::stream<secure::mem_req> s_req("s_req");
        hls::stream<secure::mem_resp> s_resp("s_resp");

        secure::mem_req wr;
        wr.id = id;
        wr.addr = 200 + id;
        wr.wdata = 0xA000 + id;
        wr.wr_en = true;
        s_req.write(wr);
        secure::memory_controller(s_req, s_resp);
        s_resp.read();

        secure::mem_req rd;
        rd.id = id;
        rd.addr = 200 + id;
        rd.wdata = 0;
        rd.wr_en = false;
        s_req.write(rd);
        secure::memory_controller(s_req, s_resp);
        secure::mem_resp result = s_resp.read();

        if (result.rdata != (0xA000 + id) || !result.valid) {
            all_pass = false;
        }
    }
    report("all_requestors_nonsecure", all_pass,
           all_pass ? "" : "Some requestors failed non-secure access");
}


// ---- Main ----

int main() {
    test_nonsecure_write_read();
    test_privileged_secure_access();
    test_unprivileged_secure_read_denied();
    test_unprivileged_secure_write_denied();
    test_boundary_addresses();
    test_all_requestors_nonsecure();

    std::cout << "SUMMARY " << EXAMPLE_ID << ": "
              << tests_passed << "/" << tests_total << " passed" << std::endl;

    return (tests_passed == tests_total) ? 0 : 1;
}
