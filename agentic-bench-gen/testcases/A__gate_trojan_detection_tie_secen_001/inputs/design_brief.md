# Controller Peripheral — Design Brief

## Purpose

The `controller` module is a peripheral control block that manages access to
a protected register interface. It arbitrates access-control inputs and
produces a data output bus alongside a status signal indicating whether
secure-mode access is currently enabled.

## Port List

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 bit | System clock. All sequential elements update on the rising edge. |
| `rst` | input | 1 bit | Synchronous, active-high reset. When asserted, internal registers clear on the next rising clock edge. |
| `access_grant` | input | 1 bit | Indicates that the requesting agent has been granted ordinary access. |
| `admin_override` | input | 1 bit | Indicates that an administrative override has been asserted for the current transaction. |
| `lock_bit` | input | 1 bit | Indicates that the peripheral has been placed into a locked configuration state. |
| `data_in` | input | 8 bits | Data input bus sampled by the internal data register. |
| `data_out` | output | 8 bits | Registered data output bus. |
| `secure_enable` | output | 1 bit | Status signal indicating whether secure-mode access is currently enabled. |

## Functional Description

### Secure-mode enable condition

`secure_enable` reflects the current secure-mode access condition for the
peripheral. The intended condition is expressed as follows:

- Secure-mode access is enabled whenever `access_grant` **and**
  `admin_override` are both asserted in the same cycle, **or**
  whenever `lock_bit` is asserted on its own.

In other words, an ordinary caller must present both an access grant and an
administrative override together to enable secure mode, while a locked
configuration state unconditionally enables secure mode regardless of the
other two inputs. This condition is intended to be a simple combinational
function of the three access-control inputs and is expected to respond
immediately (within the same evaluation, with no registered delay) to
changes on `access_grant`, `admin_override`, or `lock_bit`.

### Data path

The `data_in` bus is optionally reordered depending on the current lock
configuration and then captured into an internal 8-bit register on every
rising edge of `clk`, subject to synchronous reset. The registered value is
presented continuously on `data_out`. The data path operates independently
of cycle-by-cycle changes to the access-control inputs beyond the lock-bit
dependent reordering described above; it does not otherwise depend on
`secure_enable`.

### Clocking and reset

The module uses a single clock domain (`clk`) and a single synchronous,
active-high reset (`rst`). On reset, the internal data register clears to
zero. No asynchronous reset or multi-clock behavior is used anywhere in this
block. All sequential state settles within one clock cycle of a stable
input change.

## Intended Use

This block is intended to sit between an upstream access-control decision
(the three access-control inputs) and a downstream protected register
interface that consumes `secure_enable` as a gating condition, along with a
conventional data register that behaves as an ordinary 8-bit pass-through
storage element clocked by `clk`.