# TMR Voter Block — Design Brief

## Purpose

This block implements Triple Modular Redundancy (TMR) around a small
combinational logic function. The intent is straightforward: three
independent replica instances each compute the same function of the shared
primary inputs, and a majority voter combines their three outputs so that
any single replica producing a wrong value (due to a transient fault,
stuck-at defect, or similar) does not corrupt the block's final output. As
long as no more than one of the three replicas misbehaves at a time, the
voter's 2-of-3 majority logic should mask the fault and the top-level output
should remain correct.

## Top-level module: `tmr_top`

Port list:

| Port | Direction | Width | Description |
|---|---|---|---|
| `a` | input | 1 bit | Primary input, shared by all three replicas |
| `b` | input | 1 bit | Primary input, shared by all three replicas |
| `c` | input | 1 bit | Primary input, shared by all three replicas |
| `voted_out` | output | 1 bit | Final voted output of the TMR block |

## Structure

The block is expected to contain exactly four functional instances:

- Three replica instances, each an instantiation of `replica_cell`:
  - `u_replica_a`
  - `u_replica_b`
  - `u_replica_c`

  Each replica instance takes the same three primary inputs (`a`, `b`, `c`)
  and produces one output bit. In this design the replica outputs are named
  `net_repa_out`, `net_repb_out`, and `net_repc_out` respectively, matching
  the instance that drives them.

- One majority voter instance, `u_voter3`, an instantiation of `voter3`.
  The voter has three single-bit inputs — referred to in the netlist as
  `voter_a`, `voter_b`, and `voter_c` — and one output, `voted_out`, which is
  also the top-level output of `tmr_top`.

Any additional glue/routing cells present in the netlist (buffers, fanout
regeneration cells, etc.) exist purely to satisfy physical/routing needs and
should not alter the logical source of any signal.

## Wiring invariant

For the redundancy scheme to provide its fault-masking guarantee, each of
the voter's three inputs must originate from a distinct one of the three
replica outputs:

- `voter_a` should be driven (directly or through simple buffering) from
  `net_repa_out`, the output of `u_replica_a`.
- `voter_b` should be driven from `net_repb_out`, the output of
  `u_replica_b`.
- `voter_c` should be driven from `net_repc_out`, the output of
  `u_replica_c`.

This one-to-one correspondence between replica and voter input is the
entire basis for the block's ability to tolerate a single-replica fault: if
each voter input traces back to a different replica, no single faulty
replica can ever account for more than one of the voter's three inputs, and
the majority vote reliably outputs the correct value.

## Notes for integration

- All three replica instances are expected to be structurally identical
  (same submodule, same connectivity pattern to the shared primary inputs),
  differing only in which voter input they ultimately feed.
- The voter is a standard 2-of-3 majority function and should not require
  any modification for this application.
- When reviewing or resynthesizing this netlist, confirm that the number of
  replica instances (3) and voter instances (1) matches this brief, and that
  each voter input net can be traced back to the correct, distinct replica
  output net described above.