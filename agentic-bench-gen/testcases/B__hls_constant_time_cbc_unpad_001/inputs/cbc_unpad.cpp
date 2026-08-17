// cbc_unpad.cpp
//
// PKCS#7 padding validation kernel for a CBC-mode block decryption
// pipeline. Given the final decrypted 16-byte block, determines whether
// it carries well-formed PKCS#7 padding and computes the resulting
// unpadded plaintext length.

#include <cstddef>

void pad_check(const unsigned char block[16], int *valid, int *unpadded_len)
{
    unsigned char n = block[15];

    if (n == 0 || n > 16) {
        *valid = 0;
        *unpadded_len = 16;
        return;
    }

    int start = 16 - (int)n;

    for (int i = 15; i >= start; --i) {
        if (block[i] != n) {
            *valid = 0;
            *unpadded_len = 16;
            return;
        }
    }

    *valid = 1;
    *unpadded_len = start;
}