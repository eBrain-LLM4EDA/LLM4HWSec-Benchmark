#include "stream_accumulator.h"

static int accumulators[256] = {0};
static int current_context = 0;

int process_sample(int context_id, int input, int reset) {
    if (reset) {
        for (int i = 0; i < 256; ++i) {
            accumulators[i] = 0;
        }
        current_context = context_id;
        accumulators[context_id] = input;
        return input;
    }

    if (context_id != current_context) {
        current_context = context_id;
    }

    accumulators[context_id] += input;
    return accumulators[context_id];
}