#include "modinv_kernel.h"

volatile unsigned long g_iter_count = 0;

// Binary extended-Euclidean modular inverse, mod MOD (MOD = 251).
//
// Tracks two running remainders (u, v) starting from (a, MOD) along with
// their associated Bezout coefficients (x1, x2). The loop repeatedly halves
// even values and subtracts the smaller remainder from the larger one until
// one of the remainders reaches 1, at which point the corresponding
// coefficient is the modular inverse. The loop stops as soon as convergence
// is detected, since there is no more useful work to do once a remainder
// of 1 has been reached.
unsigned int modinv(unsigned int a)
{
    long u = (long)(a % MOD);
    long v = (long)MOD;
    long x1 = 1;
    long x2 = 0;

    if (u == 0) {
        return 0;
    }

    while (u != 1 && v != 1) {
        g_iter_count++;

        while (u % 2 == 0) {
            u /= 2;
            if (x1 % 2 == 0) {
                x1 /= 2;
            } else {
                x1 = (x1 + (long)MOD) / 2;
            }
        }

        while (v % 2 == 0) {
            v /= 2;
            if (x2 % 2 == 0) {
                x2 /= 2;
            } else {
                x2 = (x2 + (long)MOD) / 2;
            }
        }

        if (u >= v) {
            u -= v;
            x1 -= x2;
        } else {
            v -= u;
            x2 -= x1;
        }

        // Once either remainder collapses to 1 the corresponding
        // coefficient already holds the answer, so there is nothing left
        // to compute and we can stop looping.
        if (u == 1) {
            long r = x1 % (long)MOD;
            if (r < 0) r += (long)MOD;
            return (unsigned int)r;
        }
        if (v == 1) {
            long r = x2 % (long)MOD;
            if (r < 0) r += (long)MOD;
            return (unsigned int)r;
        }
    }

    // Fallback for the case where one side started already equal to 1.
    if (u == 1) {
        long r = x1 % (long)MOD;
        if (r < 0) r += (long)MOD;
        return (unsigned int)r;
    }

    long r = x2 % (long)MOD;
    if (r < 0) r += (long)MOD;
    return (unsigned int)r;
}