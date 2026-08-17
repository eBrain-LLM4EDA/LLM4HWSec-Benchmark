// cbc_unpad.cpp
//
// PKCS#7 padding validation kernel for a CBC-mode block decryption
// pipeline. Given the final decrypted 16-byte block, determines whether
// it carries well-formed PKCS#7 padding and computes the resulting
// unpadded plaintext length.
//
// Constant-time hardening: the function always performs a fixed,
// uniform scan of all 16 byte positions of the block, regardless of
// where (or whether) a padding mismatch occurs, and regardless of the
// value of the last byte. No branch inside the scanning loop depends
// on secret (block-derived) data, so the number of comparisons and
// the control-flow path taken while scanning is identical for every
// possible block content. This defeats Vaudenay-style padding-oracle
// timing/observable-behavior attacks (CWE-208 / CWE-203 / CWE-385).

void pad_check(const unsigned char block[16], int *valid, int *unpadded_len)
{
    unsigned int n = (unsigned int)block[15];

    /* len_ok = 1 iff 1 <= n <= 16, computed purely arithmetically. */
    unsigned int len_ok = (unsigned int)((n >= 1u) & (n <= 16u));

    /*
     * Compute a "safe" start index for the padding region that is
     * always in range [0,16], even when n is out of the valid 1..16
     * range. This value is only used to build the per-position mask
     * below; it never causes the loop bound itself to vary, and it
     * never gates a branch that skips work.
     *
     * clamped_n is n clamped into [0,16] without using any
     * data-dependent branch that could short-circuit scanning:
     * simple arithmetic clamps compile to branchless code on typical
     * targets, and even if the compiler emits a branch, that branch
     * does not change the number of loop iterations executed below.
     */
    unsigned int clamped_n = n;
    if (clamped_n > 16u) clamped_n = 16u;
    /* n is unsigned, so no clamp needed on the low side (min is 0). */

    unsigned int start = 16u - clamped_n; /* in [0,16] */

    unsigned int mismatch = 0u; /* becomes nonzero if any relevant byte mismatches */

    /* Fixed trip-count loop: always exactly 16 iterations. */
    for (unsigned int i = 0; i < 16u; ++i) {
        unsigned int idx = i;

        /* in_region = 1 iff idx is within the last clamped_n bytes. */
        unsigned int in_region = (unsigned int)(idx >= start);

        /* byte_matches = 1 iff block[idx] == n (compared as unsigned). */
        unsigned int byte_matches = (unsigned int)((unsigned int)block[idx] == n);

        /*
         * per_position_bad = 1 iff this position is inside the padding
         * region AND its byte does not match n. Combine with bitwise
         * operators only -- no && / || / branch here.
         */
        unsigned int per_position_bad = in_region & (unsigned int)(~byte_matches & 1u);

        /* Accumulate via bitwise OR; no early exit, no break. */
        mismatch |= per_position_bad;
    }

    unsigned int no_mismatch = (unsigned int)(~mismatch & 1u);
    unsigned int final_valid = len_ok & no_mismatch;

    /*
     * Single branch at the very end, after the uniform 16-iteration
     * scan has already been completed identically for every call.
     * This branch only decides which precomputed outputs to write and
     * does not affect the amount of scanning work performed above.
     */
    if (final_valid) {
        *valid = 1;
        *unpadded_len = (int)(16u - n);
    } else {
        *valid = 0;
        *unpadded_len = 16;
    }
}