# Design Brief: `perm_cone` Permission Decision Cone

## Overview

`perm_cone` is a small combinational logic block extracted from a larger
access-control subsystem. Its job is to compute a single-bit grant/deny
decision based on the requesting agent's declared request level and the
identity of the resource owner. It is a pure combinational function with
no internal state and no clock: the output is determined entirely by the
current values of its inputs.

This cone sits downstream of a request-decoding stage (not included here)
that has already extracted a normalized `req_level` code and `owner_id`
code from an incoming request. `perm_cone` consumes these two fields and
produces the final `grant` signal that downstream logic uses to allow or
block the requested operation.

## Pinout

| Signal       | Direction | Width | Description                                          |
|--------------|-----------|-------|-------------------------------------------------------|
| `req_level`  | input     | 2     | Normalized request-level code for the incoming access request. |
| `owner_id`   | input     | 3     | Normalized identifier of the resource owner associated with the request. |
| `grant`      | output    | 1     | `1` if the request should be granted, `0` if it should be denied. |

Both inputs are combinational and are expected to be stable for the
duration of the evaluation window; `grant` is a purely combinational
function of `req_level` and `owner_id` with no registered behavior in this
cone.

## Implementation Notes

Because this cone sits on a timing- and area-sensitive path, the original
Boolean permission-check expression (written naturally in terms of AND/OR
logic) was restructured during synthesis into an equivalent implementation
built entirely from primitive standard cells: two-input and three-input
NAND gates, two-input NOR gates, and inverters. This kind of NAND/NOR
restructuring is a standard synthesis technique for reducing area and
gate count on small combinational cones, and is reflected directly in the
gate-level netlist provided in `inputs/perm_cone_netlist.v`. Every logic
gate in the netlist is instantiated as an explicit, individually named
primitive-cell instance, which makes the cone straightforward to trace and
simulate gate by gate.

## Your Task

Your job is to verify that the gate-level netlist in
`inputs/perm_cone_netlist.v` correctly implements the intended permission
policy for `perm_cone` across its full input space. The intended
functional behavior is provided exhaustively, for all 32 combinations of
`req_level` and `owner_id`, in `inputs/reference_truth_table.txt`. You
should treat that file as the authoritative specification of what
`grant` should be for every possible input combination, and check the
netlist's actual behavior against it.