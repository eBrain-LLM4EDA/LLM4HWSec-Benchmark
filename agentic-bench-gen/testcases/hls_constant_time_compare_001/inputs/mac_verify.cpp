#include "mac_verify.h"

// Compares a locally-computed authentication tag against a tag supplied
// by an external party. Returns true only if every one of the 16 bytes
// matches; false as soon as we know the tags cannot be equal.
bool verify(const unsigned char computed_tag[16], const unsigned char received_tag[16]) {
    for (int i = 0; i < 16; ++i) {
        if (computed_tag[i] != received_tag[i]) {
            return false;
        }
    }
    return true;
}