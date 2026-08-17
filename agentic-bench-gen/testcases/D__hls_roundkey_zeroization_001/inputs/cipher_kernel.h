#ifndef CIPHER_KERNEL_H
#define CIPHER_KERNEL_H

void encrypt_block(const unsigned char key[16],
                    const unsigned char plaintext[16],
                    unsigned char ciphertext[16]);

#endif