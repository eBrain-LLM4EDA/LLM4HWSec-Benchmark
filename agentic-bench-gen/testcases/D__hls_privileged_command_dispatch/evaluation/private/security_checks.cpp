#include "dispatcher.h"
#include <cstdio>
#include <cstdint>

void test_SR1() {
    uint32_t state = 0xAAAAAAAA;
    uint8_t status = 0x00;
    int ret = dispatch(CMD_WRITE_CONFIG_LO, PRIV_UNTRUSTED, 0xDEADBEEF, &state, &status);
    if (ret == -1 && status == STATUS_UNAUTHORIZED && state == 0xAAAAAAAA) {
        printf("[TEST] PASS: SR1\n");
    } else {
        printf("[TEST] FAIL: SR1: WRITE_CONFIG_LO with privilege=0 not rejected (ret=%d, status=0x%02X, state=0x%08X)\n", ret, status, state);
    }
}

void test_SR2() {
    uint32_t state = 0xBBBBBBBB;
    uint8_t status = 0x00;
    int ret = dispatch(CMD_WRITE_CONFIG_HI, PRIV_UNTRUSTED, 0xCAFEBABE, &state, &status);
    if (ret == -1 && status == STATUS_UNAUTHORIZED && state == 0xBBBBBBBB) {
        printf("[TEST] PASS: SR2\n");
    } else {
        printf("[TEST] FAIL: SR2: WRITE_CONFIG_HI with privilege=0 not rejected (ret=%d, status=0x%02X, state=0x%08X)\n", ret, status, state);
    }
}

void test_SR3() {
    uint32_t state = 0xFFFF0000;
    uint8_t status = 0xFF;
    int ret = dispatch(CMD_WRITE_CONFIG_LO, PRIV_TRUSTED, 0xDEADBEEF, &state, &status);
    if (ret == 0 && status == STATUS_OK && (state & 0xFFFF) == 0xBEEF) {
        printf("[TEST] PASS: SR3\n");
    } else {
        printf("[TEST] FAIL: SR3: WRITE_CONFIG_LO with privilege=1 failed (ret=%d, status=0x%02X, state=0x%08X)\n", ret, status, state);
    }
}

void test_SR4() {
    uint32_t state = 0x0000FFFF;
    uint8_t status = 0xFF;
    int ret = dispatch(CMD_WRITE_CONFIG_HI, PRIV_TRUSTED, 0xCAFEBABE, &state, &status);
    if (ret == 0 && status == STATUS_OK && (state >> 16) == 0xBABE) {
        printf("[TEST] PASS: SR4\n");
    } else {
        printf("[TEST] FAIL: SR4: WRITE_CONFIG_HI with privilege=1 failed (ret=%d, status=0x%02X, state=0x%08X)\n", ret, status, state);
    }
}