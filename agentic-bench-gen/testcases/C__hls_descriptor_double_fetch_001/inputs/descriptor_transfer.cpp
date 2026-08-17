#include "descriptor_transfer.h"

int run_transfer(Descriptor* desc, uint8_t* dest, uint32_t max_len) {
    uint32_t requested_length = desc->length;

    if (requested_length > max_len) {
        return -1;
    }

    for (uint32_t i = 0; i < desc->length; i++) {
        dest[i] = desc->data[i];
    }

    return static_cast<int>(desc->length);
}