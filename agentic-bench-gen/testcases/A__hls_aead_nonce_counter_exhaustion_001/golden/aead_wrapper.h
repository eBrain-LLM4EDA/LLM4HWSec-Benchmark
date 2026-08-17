#ifndef AEAD_WRAPPER_H
#define AEAD_WRAPPER_H

/*
 * AEAD wrapper kernel interface.
 *
 * Do not change the name or signature of aead_encrypt_call: it is the
 * pinned entry point for this kernel.
 */

int aead_encrypt_call(const unsigned char *key,
                       const unsigned char *plaintext,
                       unsigned int plaintext_len,
                       unsigned char *ciphertext_out,
                       unsigned char *tag_out);

/*
 * Internal AES-style block primitive used by aead_encrypt_call.
 * Encrypts a single 16-byte block (nonce_block) under the given
 * 16-byte key, writing 16 bytes of output to out_block.
 */
void aes_encrypt_block(const unsigned char *key,
                        const unsigned char *nonce_block,
                        unsigned char *out_block);

#endif /* AEAD_WRAPPER_H */