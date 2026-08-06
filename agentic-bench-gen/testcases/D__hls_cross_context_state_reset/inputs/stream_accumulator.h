#ifndef STREAM_ACCUMULATOR_H
#define STREAM_ACCUMULATOR_H

/**
 * Process a sample for a given context, maintaining a running accumulation.
 *
 * @param context_id  Caller context identifier (0 to 255).
 * @param input       Integer sample value to process.
 * @param reset       When non-zero, clears all internal state for all contexts
 *                    before processing the current input.
 * @return            The accumulated output value for the given context_id
 *                    after incorporating the current input.
 *
 * Accumulation rule: output = sum of all inputs received so far in the
 * current context session. A context session begins after a reset or the
 * first call with a new context_id since the last reset or context change.
 */
int process_sample(int context_id, int input, int reset);

#endif // STREAM_ACCUMULATOR_H