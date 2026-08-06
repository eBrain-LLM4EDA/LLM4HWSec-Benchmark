#ifndef CRYPTO_KERNEL_H_
#define CRYPTO_KERNEL_H_

void crypto_kernel(const unsigned char plaintext[16],
                    const unsigned char key[16],
                    unsigned char ciphertext[16],
                    unsigned char *status);

#endif // CRYPTO_KERNEL_H_