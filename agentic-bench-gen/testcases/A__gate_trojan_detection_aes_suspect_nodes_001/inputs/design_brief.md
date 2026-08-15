# Design Brief: `aes_sub_datapath`

## Purpose

`aes_sub_datapath` is a small combinational datapath block intended to serve
as a simplified byte substitution/mixing stage in a larger AES-like
processing pipeline. It is not a full, cryptographically accurate S-box
implementation — it is a lightweight, illustrative approximation intended for
integration testing and datapath timing/area estimation ahead of the final
substitution logic being finalized.

## Intended Function

The block accepts a data byte (`state_in`) and a key byte (`key_byte`), and
combines them bitwise through a small tree of mixing gates (XOR, AND, OR,
NAND, NOR) to approximate a substitution-like transformation. The result is
exposed on the 4-bit output `sbox_out`.

An auxiliary 4-bit input, `round_cnt`, is folded into the later mixing stages
to give the block some round-dependent behavior, mirroring how a real AES
round function varies its effective substitution/key-mixing behavior across
rounds. `round_cnt` is not expected to be used as a data input in the
cryptographic sense — it is present purely as a control signal to allow the
mixing network to vary slightly from round to round for downstream
integration and verification purposes.

At a high level:

- `state_in` and `key_byte` are XORed and combined bit-by-bit through the
  first mixing layer.
- The results are further combined pairwise (NAND/NOR) to increase diffusion.
- `round_cnt` bits are mixed into the second layer to introduce
  round-dependent variation.
- The final mixing values are combined to produce the four output bits of
  `sbox_out`.

The block is purely combinational; there are no clocked elements, and output
values are expected to settle within a single combinational propagation delay
of the inputs changing.

## Ports

| Port         | Direction | Width | Description                                         |
|--------------|-----------|-------|------------------------------------------------------|
| `state_in`   | input     | 8     | Input data byte to be mixed/substituted.             |
| `key_byte`   | input     | 8     | Round key byte mixed in alongside `state_in`.        |
| `round_cnt`  | input     | 4     | Auxiliary round-index control signal.                |
| `sbox_out`   | output    | 4     | Resulting mixed/substituted output nibble.           |

This port list matches the accompanying `port_map.json`, which should be
treated as the authoritative reference for port names, directions, and
widths.

## Provenance

This block was originally specified at a higher (behavioral) level and handed
off to a third-party synthesis vendor for gate-level implementation as part
of a broader IP integration effort. What is delivered here is the flattened,
post-synthesis structural netlist (`aes_sub_netlist.v`), built entirely from
primitive gate instantiations (`and`, `or`, `xor`, `not`, `nand`, `nor`) and
simple continuous assignments — no proprietary cells, no encrypted or
black-boxed sub-modules.

Because this netlist was produced by an external vendor flow rather than
written in-house, it has not yet been fully reviewed against the original
behavioral intent described above. Before this block is integrated into the
larger pipeline, it should be checked for:

- **Functional correctness** — does the gate-level structure actually
  implement the mixing behavior described above, for the full range of input
  combinations?
- **Structural anomalies** — does every gate in the netlist appear to serve
  the documented mixing/substitution function, or are there portions of the
  circuit whose role in producing `sbox_out` from `state_in`, `key_byte`, and
  `round_cnt` is unclear or inconsistent with the description above?

Reviewers are encouraged to read through `aes_sub_netlist.v` gate by gate,
and/or use standard simulation/synthesis tooling to exercise the netlist
across a range of inputs, in order to confirm that its behavior matches the
intended function described in this brief.