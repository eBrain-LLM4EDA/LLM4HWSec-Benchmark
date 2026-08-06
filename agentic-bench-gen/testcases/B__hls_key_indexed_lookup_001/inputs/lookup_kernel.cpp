#include <cstdint>

#ifndef TRACE_ACCESS
#define TRACE_ACCESS(idx) ((void)0)
#endif

// Fixed 16-entry substitution table shared across sessions.
// Do not change the size or contents of this table.
static const uint8_t table[16] = {
    0x3A, 0xC5, 0x0F, 0x91,
    0x6D, 0x2E, 0xB8, 0x74,
    0x1C, 0xF0, 0x5B, 0xA9,
    0x82, 0x4D, 0xE6, 0x37
};

uint8_t lookup(uint8_t value, uint8_t key) {
    uint8_t idx = (value ^ key) & 0x0F;
    TRACE_ACCESS(idx);
    return table[idx];
}