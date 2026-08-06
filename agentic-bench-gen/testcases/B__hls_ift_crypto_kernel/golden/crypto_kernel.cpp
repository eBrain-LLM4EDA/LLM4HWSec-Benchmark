#include <cstdint>
#include <cstddef>
#include "crypto_kernel.h"

// Hardened crypto kernel.
//
// Security invariants enforced by construction:
//  - The loop bound is a compile-time constant (16); it never depends on
//    the content of `plaintext` or `key`.
//  - Every iteration performs the identical, data-independent operation:
//    a byte-wise XOR combination written into `ciphertext`. There is no
//    branch, comparison, or memory-access pattern keyed on any byte of
//    `key` or `plaintext`.
//  - `*status` is written exactly once, unconditionally, to the fixed
//    literal 0x00 after the loop completes. No branch, comparison, or
//    lookup involving `key`/`plaintext` participates in computing this
//    value.
//  - No stdout/stderr/file I/O, no static or global mutable state, no
//    dynamic allocation, and no recursion are used anywhere in this
//    function, preventing any additional covert channel.
void crypto_kernel(const unsigned char plaintext[16],
                    const unsigned char key[16],
                    unsigned char ciphertext[16],
                    unsigned char *status)
{
    for (int i = 0; i < 16; i++) {
        ciphertext[i] = static_cast<unsigned char>(plaintext[i] ^ key[i]);
    }

    *status = 0x00;
}