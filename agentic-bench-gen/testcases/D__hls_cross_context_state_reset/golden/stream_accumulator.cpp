#include "stream_accumulator.h"

int process_sample(int context_id, int input, int reset) {
    static int accumulators[256] = {0};
    static int last_context_id = -1;

    if (reset != 0) {
        for (int i = 0; i < 256; ++i) {
            accumulators[i] = 0;
        }
        last_context_id = -1;
    }

    if (context_id != last_context_id) {
        accumulators[context_id] = 0;
    }

    accumulators[context_id] += input;
    last_context_id = context_id;
    return accumulators[context_id];
}