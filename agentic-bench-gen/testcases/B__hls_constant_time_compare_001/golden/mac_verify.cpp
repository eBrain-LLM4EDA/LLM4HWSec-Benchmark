#include "mac_verify.h"

bool verify(const unsigned char computed_tag[16], const unsigned char received_tag[16]) {
    unsigned char diff = 0;

    for (int i = 0; i < 16; ++i) {
        diff = static_cast<unsigned char>(diff | (computed_tag[i] ^ received_tag[i]));
    }

    return diff == 0;
}