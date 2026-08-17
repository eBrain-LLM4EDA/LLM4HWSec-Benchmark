#include <cstdint>
#include <cstddef>

// Conditionally exchanges the contents of two coordinate buffers used in
// a ladder step of a scalar-multiplication routine.
//
// P and Q each hold n uint32_t values. When ctrl_bit is 1, the two
// buffers are exchanged element-wise; when ctrl_bit is 0, both buffers
// are left exactly as they were.
void conditional_swap(uint32_t *P, uint32_t *Q, int n, unsigned int ctrl_bit)
{
    // Only perform the exchange when the control value selects it.
    if (ctrl_bit & 1u)
    {
        for (int i = 0; i < n; ++i)
        {
            uint32_t t = P[i];
            P[i] = Q[i];
            Q[i] = t;
        }
    }
    // Otherwise, nothing to do: buffers remain unchanged.
}