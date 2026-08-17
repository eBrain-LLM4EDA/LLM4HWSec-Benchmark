#include "descriptor_transfer.h"

extern "C" int run_transfer(Descriptor* desc, uint8_t* dest, uint32_t max_len) {
    // Single, one-time read of the volatile shared-memory field. This is the
    // ONLY place desc->length is ever touched. The resulting local snapshot
    // is a plain (non-volatile) automatic variable, so both the bounds
    // check below and the copy loop that follows operate on the exact same
    // value, eliminating the time-of-check-to-time-of-use window: no
    // concurrent mutation of desc->length after this line can influence
    // validation or the transfer.
    const uint32_t snapshot_length = desc->length;

    if (snapshot_length > max_len) {
        // Reject: zero bytes copied, dest left completely untouched.
        return -1;
    }

    for (uint32_t i = 0; i < snapshot_length; i++) {
        dest[i] = desc->data[i];
    }

    return static_cast<int>(snapshot_length);
}