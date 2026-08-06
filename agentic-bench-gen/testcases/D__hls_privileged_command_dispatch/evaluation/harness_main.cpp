#include "dispatcher.h"
#include <cstdio>
#include <cstdint>

// Forward declarations of security check functions (defined in private/security_checks.cpp)
void test_SR1();
void test_SR2();
void test_SR3();
void test_SR4();

int main() {
    // FR1: Compilation and linkage is implicitly tested by this harness existing.
    // We'll emit a PASS marker for FR1 since we reached main().
    printf("[TEST] PASS: FR1\n");

    // FR2: READ_STATUS
    {
        uint32_t state = 0x12345678;
        uint8_t status = 0xFF;
        int ret = dispatch(CMD_READ_STATUS, PRIV_UNTRUSTED, 0, &state, &status);
        if (ret == 0 && status == (state & 0xFF) && state == 0x12345678) {
            printf("[TEST] PASS: FR2\n");
        } else {
            printf("[TEST] FAIL: FR2: READ_STATUS failed (ret=%d, status=0x%02X, state=0x%08X)\n", ret, status, state);
        }
    }

    // FR3: NOOP
    {
        uint32_t state = 0xDEADBEEF;
        uint8_t status = 0xFF;
        int ret = dispatch(CMD_NOOP, PRIV_TRUSTED, 0, &state, &status);
        if (ret == 0 && status == STATUS_OK && state == 0xDEADBEEF) {
            printf("[TEST] PASS: FR3\n");
        } else {
            printf("[TEST] FAIL: FR3: NOOP failed (ret=%d, status=0x%02X, state=0x%08X)\n", ret, status, state);
        }
    }

    // FR4: Unknown command
    {
        uint32_t state = 0xCAFEBABE;
        uint8_t status = 0x00;
        int ret = dispatch(0xFF, PRIV_UNTRUSTED, 0, &state, &status);
        if (ret == -1 && status == STATUS_UNKNOWN_COMMAND && state == 0xCAFEBABE) {
            printf("[TEST] PASS: FR4\n");
        } else {
            printf("[TEST] FAIL: FR4: Unknown command not rejected (ret=%d, status=0x%02X, state=0x%08X)\n", ret, status, state);
        }
    }

    // Run security checks (SR1-SR4) from private implementation
    test_SR1();
    test_SR2();
    test_SR3();
    test_SR4();

    return 0;
}