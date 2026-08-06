#ifndef CRYPTO_KERNEL_H
#define CRYPTO_KERNEL_H

// Fixed interface for the crypto_kernel HLS component.
// Do not modify this declaration.
void crypto_kernel(const unsigned char plaintext[16],
                    const unsigned char key[16],
                    unsigned char ciphertext[16],
                    unsigned char *status);

#endif // CRYPTO_KERNEL_H