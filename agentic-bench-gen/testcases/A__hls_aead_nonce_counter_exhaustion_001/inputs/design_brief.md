# AEAD Wrapper — Design Brief

## Purpose

`aead_encrypt_call` is a small AEAD-style encryption kernel. Each call
encrypts a caller-supplied plaintext under a caller-supplied key and
produces both ciphertext and an authentication tag.

The kernel derives a fresh per-call nonce by combining a fixed,
compiled-in base nonce with an internal 32-bit call counter. This
combined nonce block feeds the internal AES-style block primitive
(`aes_encrypt_block`), which is used both to generate the keystream
used for encryption and to derive the authentication tag. The counter
advances by exactly one on every call that actually produces
ciphertext, so that consecutive calls with the same key and plaintext
still produce distinct outputs.

## Interface

```
int aead_encrypt_call(const unsigned char *key,
                       const unsigned char *plaintext,
                       unsigned int plaintext_len,
                       unsigned char *ciphertext_out,
                       unsigned char *tag_out);
```

This signature is fixed and declared in `aead_wrapper.h`; it must not
be altered.

### Parameters

- `key` — pointer to a 16-byte AES key. The same 16 bytes are reused
  across all calls made by a given process; the kernel does not
  rotate or derive a new key internally.
- `plaintext` — pointer to `plaintext_len` bytes of data to encrypt.
- `plaintext_len` — length of `plaintext` in bytes. Valid range is
  `0 <= plaintext_len <= 4096`.
- `ciphertext_out` — caller-allocated buffer of at least
  `plaintext_len` bytes. When the call succeeds, exactly
  `plaintext_len` bytes are written here (zero bytes when
  `plaintext_len == 0`).
- `tag_out` — caller-allocated buffer of at least 16 bytes. When the
  call succeeds, exactly 16 bytes are written here, regardless of
  `plaintext_len`.

### Internal state

The kernel keeps a single piece of state across calls within a
process: a 32-bit call counter. The counter is combined with the
fixed base nonce (defined internally in `aead_wrapper.cpp`) to build
the 16-byte nonce block passed into `aes_encrypt_block` for that call.
On a call that produces ciphertext, the counter is advanced by
exactly one before the function returns, so the next call uses a
different nonce block.

There is no function exposed to reset or inspect the counter
directly; its starting value is determined at compile time.

### Test seam: `AEAD_TEST_COUNTER_START`

To make it practical to exercise the kernel's behavior near the top
of the counter's range without issuing billions of calls, the
starting value of the internal counter is controlled by an optional
compile-time macro:

```
#ifndef AEAD_TEST_COUNTER_START
#define AEAD_TEST_COUNTER_START 0u
#endif
```

- If `AEAD_TEST_COUNTER_START` is not defined at compile time, the
  counter starts at `0`, matching normal production behavior.
- A test build may override this value, e.g.
  `-DAEAD_TEST_COUNTER_START=0xFFFFFFFDu`, to start the counter close
  to the top of its 32-bit range and observe behavior over just a
  handful of subsequent calls.

Any implementation of `aead_encrypt_call` must continue to honor this
macro exactly as described: default to `0`, and otherwise initialize
the counter to the given value on process start.

## Counter range boundary

The counter is a 32-bit unsigned value. It has a finite range, and at
some point a call will be made for which no new, previously-unused
counter value remains available to build the nonce block from.

Correct handling of this boundary means the function must, before
doing any encryption work for a given call, determine whether a
genuinely fresh counter value is available to use for that call:

- If a fresh counter value is available, the function proceeds
  normally: it builds the nonce block from that counter value,
  performs the encryption and tag computation, advances the counter,
  writes `plaintext_len` bytes to `ciphertext_out` and 16 bytes to
  `tag_out`, and returns `0`.
- If no fresh counter value is available, the function must not
  perform the encryption or tag computation at all for that call. It
  must return a nonzero value instead of `0`, and it must not advance
  the counter any further. Every subsequent call must behave the same
  way — returning the same nonzero result, with the counter state
  unchanged.

## Output contract

`ciphertext_out` and `tag_out` are only written to when
`aead_encrypt_call` returns `0`. Callers should treat the contents of
`ciphertext_out` and `tag_out` as undefined and unwritten whenever the
return value is nonzero, and should check the return value before
relying on those buffers. Implementations must make this contract
hold exactly: no partial writes, and no writes at all, on any call
that returns a nonzero value.