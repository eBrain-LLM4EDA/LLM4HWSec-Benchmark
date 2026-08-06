# HLS Streaming Accumulator with Context Isolation

## Objective

Modify the provided streaming kernel (`stream_accumulator.cpp`) so that a change in the caller-supplied context identifier clears all accumulated internal state before processing the new input sample. Repeated calls with the same context identifier must preserve the documented running accumulation behavior.

## Interface

The function signature is declared in `stream_accumulator.h`:

```cpp
int process_sample(int context_id, int input, int reset);
```

- `context_id`: integer caller context identifier (0 to 255).
- `input`: integer sample value to process.
- `reset`: when non-zero, clears all internal state for all contexts before processing the current input.

**Returns:** the accumulated output value for the given `context_id` after incorporating the current input.

**Accumulation rule:** output = sum of all inputs received so far in the current context session. A context session begins after a reset or the first call with a new `context_id` since the last reset or context change.

## Constraints

- Keep the pinned `process_sample(int context_id, int input, int reset)` interface and deterministic reset semantics.
- A context change must clear state before the current input is incorporated; repeated calls in one context retain the documented state.
- Use only static fixed-width state and synthesizable control flow.

## Expected Outputs

1. `stream_accumulator.cpp` compiles with `g++ -std=c++17 -Wall -Werror`.
2. For a sequence of calls with `context_id=0` and inputs `[1,2,3]`, the output sequence is `[1,3,6]` (running sum).
3. For a sequence of calls with `context_id=0`, input `5`, then `context_id=1`, input `10`, the output for `context_id=1` is `10` (fresh accumulation, not `15`).
4. For a sequence `context_id=0`, input `5`, then `context_id=0`, input `7`, the output for the second call is `12` (accumulation preserved).
5. After a reset event (`reset=1` for one call), the next call with any `context_id` produces output equal to that call's input (state cleared).

## Submission

Submit your modified `stream_accumulator.cpp` (and `stream_accumulator.h` if you changed it). The evaluation will compile your code with the provided header and a test harness, then execute it against a set of behavioral tests. Your implementation must pass all tests to be considered correct.