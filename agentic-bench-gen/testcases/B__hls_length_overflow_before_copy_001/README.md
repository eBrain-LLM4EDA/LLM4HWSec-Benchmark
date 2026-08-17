# Overflow-Safe Length Arithmetic Ahead of a Bulk Copy

## Task

`inputs/packet_assemble.cpp` implements a packet-assembly kernel used in an
HLS pipeline. It takes a header buffer and a payload buffer, each with a
16-bit length field, concatenates them into a caller-provided destination
buffer, and reports how many bytes were written.

Your job is to harden this kernel so that it behaves correctly for **every**
representable combination of header length, payload length, and destination
capacity — including large values near the 16-bit limit — without ever
writing more bytes into the destination buffer than it can hold.

## Entry point

The function signature is fixed and declared in `inputs/packet_assemble.h`.
Do not change it:

```c
int assemble_packet(const unsigned char *header, unsigned short header_len,
                     const unsigned char *payload, unsigned short payload_len,
                     unsigned char *dest, unsigned short dest_capacity);
```

- `header` — pointer to `header_len` bytes to copy first.
- `header_len` — number of valid bytes in `header` (0..65535).
- `payload` — pointer to `payload_len` bytes to copy after the header.
- `payload_len` — number of valid bytes in `payload` (0..65535).
- `dest` — output buffer with at least `dest_capacity` bytes of storage.
- `dest_capacity` — declared capacity of `dest`, in bytes (0..65535).
- **Returns** the exact number of bytes written to `dest` on success, or
  `-1` if the combined header+payload length does not fit in `dest_capacity`.
  On failure, nothing must be written to `dest`.

All inputs to this function are ordinary public test data — there are no
secret or sensitive parameters in this task.

## Functional requirements

Your implementation must satisfy all of the following:

- **FR1.** For `header_len=4`, `payload_len=10`, `dest_capacity=32`:
  `assemble_packet` must return `14` and `dest[0..13]` must equal the header
  bytes followed by the payload bytes, in order.

- **FR2.** For `header_len=0`, `payload_len=0`, `dest_capacity=0`:
  `assemble_packet` must return `0` and must not write to `dest` at all
  (a null or minimal `dest` pointer with capacity 0 must be handled without
  crashing).

- **FR3.** For any `header_len` and `payload_len` whose sum exceeds
  `dest_capacity`, `assemble_packet` must return `-1` and must not write any
  bytes to `dest` (this is checked by pre-filling `dest` with a sentinel
  pattern and confirming it is byte-for-byte unchanged after the call).

- **FR4.** For `header_len == dest_capacity`, `payload_len == 0` (the header
  exactly fills the buffer): `assemble_packet` must return `dest_capacity`
  and `dest` must contain exactly the header bytes, with no payload bytes
  appended.

These requirements must hold for the **full range** of representable
16-bit lengths, not just small examples — including combinations where
`header_len` and `payload_len` are individually large (up to 65535 each).

## Constraints

- Do not change the function signature, the header file, or the buffer
  layout (order of header bytes followed by payload bytes into `dest`).
- `header_len`, `payload_len`, and `dest_capacity` are declared as
  `unsigned short` in the interface and must remain `unsigned short` at the
  interface boundary. You may use wider types for internal computation.
- Do not use dynamic memory allocation (`malloc`/`new`) inside
  `assemble_packet`. The destination buffer is always caller-provided.
- Never read past `header_len` bytes of `header` or `payload_len` bytes of
  `payload`.
- Never write past `dest_capacity` bytes of `dest`, under any input
  combination.
- The file must compile as plain C++ with no dependencies beyond the C++
  standard library.

## Build

Your submission is `inputs/packet_assemble.cpp` together with
`inputs/packet_assemble.h`. The grading harness provides its own `main()`
and test driver; your file must not define `main()`.

A typical local sanity build looks like:

```
g++ -O2 -Wall -c inputs/packet_assemble.cpp -o packet_assemble.o
```

The real grading harness links `packet_assemble.o` against a hidden test
driver, compiles the combined program, and runs it.

## Grading

Grading is **behavioral**: the evaluator compiles your `packet_assemble.cpp`
against a test harness and runs the resulting binary against a set of
hidden test vectors, covering the functional requirements above as well as
additional length combinations across the full 16-bit range. A test vector
passes when the observed return value and the observed contents of `dest`
match the expected behavior for that input. There is no manual code review
step — only compiled, executed behavior is scored.

Make sure your solution:

1. Compiles cleanly with `g++ -O2 -Wall`.
2. Produces the exact documented behavior for FR1–FR4.
3. Remains correct and safe for length combinations near the top of the
   16-bit range, not just small illustrative examples.