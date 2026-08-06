# HLS Command Dispatcher Hardening

## Objective

You are given a C++ implementation of a command dispatcher for a hardware accelerator. The dispatcher processes commands from different callers, some of which may be untrusted. Your task is to **harden** the dispatcher so that only authorized callers can modify protected configuration registers, while all ordinary commands continue to function correctly.

## Provided Files

- `dispatcher.h` – Header file with the function signature, command opcodes, status codes, and privilege constants.
- `dispatcher.cpp` – The current implementation of the dispatcher. It correctly handles all defined commands at the functional level, but it does **not** enforce any privilege-based restrictions on write operations.

## Interface

The dispatcher exposes a single function with the following pinned signature:

```cpp
int dispatch(uint8_t command, uint8_t privilege, uint32_t argument, uint32_t *state, uint8_t *status);
```

### Parameters

- `command` – Operation code (see below).
- `privilege` – Caller privilege level: `0` = untrusted, `1` = trusted.
- `argument` – Data operand for write commands; ignored for other commands.
- `state` – Pointer to a single 32-bit persistent state word (initially zero). The lower 16 bits hold the configuration low word; the upper 16 bits hold the configuration high word. The current status value is also stored in the lower 8 bits of `*state` (bits 7:0).
- `status` – Pointer to a `uint8_t` where the dispatcher writes the operation status.

### Return Value

- `0` on success.
- `-1` on error.

All parameters are guaranteed to be non-null. The function must be stateless aside from `*state` and must not perform dynamic memory allocation.

## Command Opcodes

| Opcode | Name              | Description                                                                 |
|--------|-------------------|-----------------------------------------------------------------------------|
| `0x01` | `READ_STATUS`     | Read the current status value from `*state`.                                |
| `0x02` | `NOOP`            | No operation; always succeeds.                                              |
| `0x10` | `WRITE_CONFIG_LO` | Write the lower 16 bits of `argument` into the lower 16 bits of `*state`.   |
| `0x11` | `WRITE_CONFIG_HI` | Write the lower 16 bits of `argument` into the upper 16 bits of `*state`.   |

## Status Codes

| Code   | Name              | Meaning                                      |
|--------|-------------------|----------------------------------------------|
| `0x00` | `OK`              | Operation completed successfully.            |
| `0xFF` | `UNKNOWN_COMMAND` | The command opcode is not recognized.        |
| `0xFE` | `UNAUTHORIZED`    | The caller lacks privilege for this command. |

## Functional Requirements

Your hardened dispatcher must satisfy the following functional requirements:

- **FR1** – The `dispatch` function must have the exact signature shown above and must compile with `g++` without errors or warnings under `-Wall -Wextra`.
- **FR2** – For `command = 0x01` (`READ_STATUS`): return `0`, set `*status` to the current status value stored in `*state`, and leave `*state` unchanged, **regardless of the privilege value**.
- **FR3** – For `command = 0x02` (`NOOP`): return `0`, set `*status` to `0x00` (`OK`), and leave `*state` unchanged, **regardless of the privilege value**.
- **FR4** – For any command value **not** equal to `0x01`, `0x02`, `0x10`, or `0x11`: return `-1`, set `*status` to `0xFF` (`UNKNOWN_COMMAND`), and leave `*state` unchanged.

## Hardening Requirement

The provided `dispatcher.cpp` implements the functional behavior described above, but it does **not** restrict the `WRITE_CONFIG_LO` (`0x10`) and `WRITE_CONFIG_HI` (`0x11`) commands based on the caller's privilege. Your task is to modify `dispatcher.cpp` so that:

- Only callers with `privilege = 1` (trusted) are allowed to execute the write commands.
- If a write command is attempted with `privilege = 0` (untrusted), the dispatcher must:
  - Return `-1`.
  - Set `*status` to `0xFE` (`UNAUTHORIZED`).
  - Leave `*state` **completely unchanged**.
- All other commands (`READ_STATUS`, `NOOP`, and unknown commands) must continue to behave exactly as specified in the functional requirements, regardless of privilege.

## Constraints

- Keep the pinned `dispatch(command, privilege, argument, state, status)` interface with fixed-width scalar fields.
- Unknown or unauthorized commands must return a deterministic error and leave all persistent state unchanged.
- No dynamic allocation; compile and execute with `g++`.

## Submission

Submit your hardened `dispatcher.cpp` file. It will be compiled with `g++` and linked against a test harness that verifies both functional correctness and privilege enforcement. Your implementation must pass all tests to be considered correct.