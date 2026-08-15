#include <cstdint>

#ifndef BUFFER_SIZE
constexpr int32_t BUFFER_SIZE = 64;
#endif

static const int32_t STATUS_SUCCESS = 0;
static const int32_t STATUS_ERROR_OUT_OF_RANGE = 1;

static const int32_t OP_READ = 0;
static const int32_t OP_WRITE = 1;

int kernel_access(int32_t scratchpad[BUFFER_SIZE], int32_t index, int32_t op,
                   int32_t write_val, int32_t *status) {
    // Validate index strictly within [0, BUFFER_SIZE) before touching the
    // array. Both bounds are checked explicitly and independently to avoid
    // any reliance on unsigned wraparound or pointer arithmetic tricks.
    if (index < 0 || index >= BUFFER_SIZE) {
        *status = STATUS_ERROR_OUT_OF_RANGE;
        return 0;
    }

    if (op == OP_READ) {
        *status = STATUS_SUCCESS;
        return scratchpad[index];
    } else if (op == OP_WRITE) {
        scratchpad[index] = write_val;
        *status = STATUS_SUCCESS;
        return write_val;
    }

    // Unrecognized op value: reject without touching scratchpad.
    *status = STATUS_ERROR_OUT_OF_RANGE;
    return 0;
}