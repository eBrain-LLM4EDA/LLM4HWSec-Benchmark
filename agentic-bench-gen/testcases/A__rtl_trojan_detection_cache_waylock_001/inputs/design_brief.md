# Design Brief: 2-Way, 8-Set Cache Controller (`cache_ctrl`)

## Overview

`cache_ctrl` implements a small set-associative cache lookup/fill engine
with 8 sets, each holding 2 ways. It supports per-way locking so that a
specific line within a specific set can be pinned in the cache and made
ineligible for replacement until it is explicitly unlocked.

## Request Format

Each cycle, the controller may process one lookup/fill request, described
by:

- `set_idx` (3 bits) — selects one of the 8 sets to operate on.
- `tag_in` (8 bits) — the tag associated with the request.
- `secure_attr` — a per-request attribute accompanying the tag; carried
  alongside the request for policy purposes.
- `req_valid` — asserted when a request is present this cycle.
- `req_is_write` — distinguishes a read/lookup request (`0`) from a
  write/fill-style request (`1`).

## Hit / Miss / Fill Flow

On a request (`req_valid` asserted):

1. The addressed set (`set_idx`) is checked against both ways' stored
   tags. A hit occurs on way *i* if that way is valid and its stored tag
   equals `tag_in`.
2. If a hit occurs, `hit` is asserted and `hit_way` reports which way
   matched (0 or 1). For a write request that hits, the matching way's
   tag entry is updated.
3. If no way hits (a miss) and the request is a read, the controller
   must choose a victim way to fill with the incoming tag. The victim
   way is marked valid and its tag is set to `tag_in`. Its identity is
   reported on `victim_way`.
4. If no way hits and the request is a write, the same victim selection
   and fill process applies as for a read miss.

`hit` and `hit_way` reflect only the outcome of the tag comparison for
the current request and are not affected by lock state.

## Per-Way Lock / Unlock Semantics

Each set has two independent lock bits, one per way, reported together
as `lock_status[1:0]` (bit *i* corresponds to way *i*).

- Asserting `lock_way_req` together with `lock_way_sel` sets the lock
  bit for the selected way (0 or 1) within the set addressed by
  `set_idx` that cycle.
- Asserting `unlock_way_req` together with `unlock_way_sel` clears the
  lock bit for the selected way within the addressed set.
- Lock and unlock requests act on the currently addressed set
  independently of whether a lookup/fill request is also present that
  cycle.

A locked way is intended to remain resident and pinned: once a way is
locked, it must never be evicted or chosen as a victim on subsequent
misses in that set, for any request, until it is explicitly unlocked via
`unlock_way_req`.

## Victim Selection Policy

When a miss requires a fill, the victim way is chosen as follows:

- Among the ways in the addressed set that are **not currently locked**,
  selection follows a round-robin policy: the controller alternates
  which unlocked way it offers up as the next victim, based on the
  outcome of the previous fill in that set.
- If only one way in the set is unlocked, that way is always the victim.
- Locked ways must never be evicted; the round-robin policy only ever
  chooses among currently-unlocked ways.

## Output Timing Contract

All outputs (`hit`, `hit_way`, `victim_way`, `lock_status`) are
registered (Moore-style) and update synchronously on the rising edge of
`clk`:

- `hit` and `hit_way` become valid one cycle after the request
  (`req_valid`, `set_idx`, `tag_in`, `req_is_write`) that defines them is
  presented, and reflect the lookup outcome for that request.
- `victim_way` becomes valid one cycle after a miss requiring a fill is
  presented, and holds its value until the next such event.
- `lock_status` is a registered readback of the current lock bits for
  whichever set is addressed by `set_idx`, valid one cycle after
  `set_idx` is presented, and reflects the lock state as of that read
  (including any lock/unlock request processed the same cycle it was
  addressed).

Outputs hold their last-driven value between defining events and are
reset to their default (cleared) state on assertion of `rst_n`.