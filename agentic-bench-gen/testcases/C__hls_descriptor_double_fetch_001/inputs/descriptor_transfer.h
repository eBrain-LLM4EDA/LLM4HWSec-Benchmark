#ifndef DESCRIPTOR_TRANSFER_H
#define DESCRIPTOR_TRANSFER_H

#include <cstdint>

struct Descriptor {
    volatile uint32_t length;
    uint8_t data[256];
};

extern "C" int run_transfer(Descriptor* desc, uint8_t* dest, uint32_t max_len);

#endif // DESCRIPTOR_TRANSFER_H