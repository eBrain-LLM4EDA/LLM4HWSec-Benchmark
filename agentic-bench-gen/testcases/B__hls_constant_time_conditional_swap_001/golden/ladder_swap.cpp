#include <cstdint>
#include <cstddef>

// Conditionally exchanges the contents of two coordinate buffers used in
// a ladder step of a scalar-multiplication routine.
//
// P and Q each hold n uint32_t values. When ctrl_bit is 1, the two
// buffers are exchanged element-wise; when ctrl_bit is 0, both buffers
// are left exactly as they were.
//
// This implementation is branchless and constant-time with respect to
// ctrl_bit: the loop trip count and the sequence of memory reads/writes
// performed on P and Q are identical regardless of ctrl_bit's value, and
// no branch (if, ternary, short-circuit && / ||) is conditioned on
// ctrl_bit or any value derived from it.
void conditional_swap(uint32_t *P, uint32_t *Q, int n, unsigned int ctrl_bit)
{
    // Build a full-width mask: all-ones if ctrl_bit is 1, all-zeros if 0.
    // This is computed via unsigned wraparound subtraction, not a branch.
    const uint32_t mask = (uint32_t)0 - (uint32_t)(ctrl_bit & 1u);

    for (int i = 0; i < n; ++i)
    {
        const uint32_t t = mask & (P[i] ^ Q[i]);
        P[i] ^= t;
        Q[i] ^= t;
    }
}