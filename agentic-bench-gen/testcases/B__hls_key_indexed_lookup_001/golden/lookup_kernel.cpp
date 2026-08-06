#include <cstdint>

#ifndef TRACE_ACCESS
#define TRACE_ACCESS(idx) do { (void)(idx); } while (0)
#endif

static const uint8_t table[16] = {
    0x3E, 0x71, 0x0A, 0xC4, 0x5D, 0x92, 0x18, 0xF6,
    0x27, 0xB3, 0x4C, 0x8D, 0x60, 0xDA, 0xE1, 0x55
};

uint8_t lookup(uint8_t value, uint8_t key)
{
    uint8_t idx = (value ^ key) & 0x0F;
    uint8_t result = 0;

    for (int i = 0; i < 16; ++i) {
        TRACE_ACCESS(i);
        uint8_t mask = (uint8_t)(-(int)(i == idx));
        result |= table[i] & mask;
    }

    return result;
}