# Dual-Counter Timeout Module – Design Brief

## Overview

The `timeout_module` implements a redundant dual-counter safety mechanism. Two independent counters increment in lockstep, and their values are continuously compared. A timeout signal is asserted after both counters have reached a configured threshold while remaining equal. If the counters ever disagree, an error flag is raised.

This architecture is intended to provide a degree of fault detection: a discrepancy between the two counters indicates a potential fault in one of the counting paths.

## Port Description

| Port      | Direction | Width | Description                                                                 |
|-----------|-----------|-------|-----------------------------------------------------------------------------|
| `clk`     | input     | 1     | System clock. All sequential elements are synchronous to the rising edge.   |
| `rst_n`   | input     | 1     | Active-low asynchronous reset.                                              |
| `start`   | input     | 1     | When high, enables counting (provided timeout has not already occurred).    |
| `timeout` | output    | 1     | Asserts high when the timeout condition is met.                             |
| `error`   | output    | 1     | Asserts high if the two counters ever become unequal.                       |

## Functional Behavior

1. **Reset**: When `rst_n` is low, both counters are cleared to zero, and the `timeout` and `error` outputs are deasserted.

2. **Counting**: While `start` is high and `timeout` is not yet asserted, both counters increment by one on every rising clock edge. The counters are identical in width and implementation.

3. **Timeout Condition**: The `timeout` output is set to `1` when both counters have reached or exceeded the `TIMEOUT_CYCLES` parameter value **and** the counters are equal. Once asserted, `timeout` remains high until a reset occurs.

4. **Error Detection**: If at any clock edge the two counter values differ, the `error` output is asserted and remains high until reset. This indicates a mismatch between the redundant counting paths.

## Internal Architecture

- **Enable Generation**: A single enable signal is derived from the `start` input and the `timeout` state. This enable is distributed to both counter instances.

- **Counter Instances**: Two identical `counter` modules are instantiated. Each is a simple synchronous up-counter with enable.

- **Equality Comparator**: A combinational comparator checks whether the two counter outputs are equal on every cycle.

- **Threshold Detection**: Combinational logic determines whether both counters have reached the `TIMEOUT_CYCLES` threshold.

- **Output Registers**: The `timeout` and `error` outputs are registered and updated on the rising edge of `clk`.

## Parameter

- `TIMEOUT_CYCLES` (default: 1000): The number of clock cycles after which the timeout should occur, assuming fault-free operation and both counters remaining synchronized.

## Intended Use

This module is designed for applications where a reliable timeout is critical, and where a single counter could be susceptible to undetected faults. By duplicating the counter and cross-checking their values, the design aims to detect faults that affect only one of the two counting paths.