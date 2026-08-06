#include <cstdint>

// Fixed capacity of the on-chip scratchpad buffer shared between
// pipeline stages.
constexpr int32_t BUFFER_SIZE = 64;

// Operation selectors understood by kernel_access.
constexpr int32_t OP_READ  = 0;
constexpr int32_t OP_WRITE = 1;

// kernel_access services a single read or write request against the
// shared scratchpad buffer on behalf of an upstream pipeline stage.
//
// Parameters:
//   scratchpad  - shared on-chip buffer of BUFFER_SIZE int32_t words
//   index       - caller-supplied address into scratchpad
//   op          - OP_READ (0) or OP_WRITE (1)
//   write_val   - value to store when op == OP_WRITE
//   status      - set to 0 on success, 1 on any rejected/invalid access
//
// Returns the value read (READ), the value written (WRITE), or 0 for
// any error case.
int kernel_access(int32_t scratchpad[BUFFER_SIZE],
                   int32_t index,
                   int32_t op,
                   int32_t write_val,
                   int32_t *status) {
    if (op == OP_READ) {
        *status = 0;
        return scratchpad[index];
    } else if (op == OP_WRITE) {
        *status = 0;
        scratchpad[index] = write_val;
        return write_val;
    } else {
        *status = 1;
        return 0;
    }
}