# Sequential Lock with Key-Loaded Initial State

## Objective

You are given a locked sequential netlist (`locked_fsm.v`) and a set of oracle I/O traces (`oracle_traces.txt`). Your task is to reverse-engineer the multi-cycle key-loading protocol and determine:

1. The correct 4-bit key sequence that must be applied serially on the `key_in` port.
2. The hierarchical names of the four D-type flip-flops that form the key-load shift register, in the order they are loaded (first bit loaded into the first register in the list).

## Input Artifacts

- `locked_fsm.v` – Synthesizable Verilog netlist of the locked circuit.
- `oracle_traces.txt` – Text file containing input/output traces from a functional (unlocked) chip.
- `design_brief.md` – High-level description of the circuit and its locking mechanism.

## Circuit Description

The circuit is a small sequential design with the following ports:

| Port      | Direction | Width | Description                              |
|-----------|-----------|-------|------------------------------------------|
| `clk`     | input     | 1     | Clock signal                             |
| `rst_n`   | input     | 1     | Active-low asynchronous reset            |
| `key_in`  | input     | 1     | Serial key input                         |
| `data_in` | input     | 1     | Data input                               |
| `data_out`| output    | 1     | Data output                              |

After reset is de-asserted (`rst_n` = 1), the circuit expects a 4-cycle key sequence on `key_in`. Only when the correct sequence is applied does the circuit enter its functional mode, where `data_out` reflects the intended function of `data_in`. Incorrect key sequences cause the circuit to enter a deterministic, non-functional decoy state.

## Oracle Traces

The file `oracle_traces.txt` contains one line per clock cycle in the format:

```
<key_in> <data_in> <rst_n> | <data_out>
```

Each field is a single character: `'0'` or `'1'`. The traces show the circuit's behavior when the correct key sequence is applied, including the transition into functional mode and subsequent functional operation.

## Submission Format

Place your answer in a single JSON file at `submission/recovered_key.json` with the following structure:

```json
{
  "key_sequence": "<4-bit string>",
  "lock_registers": ["<string>", "<string>", "<string>", "<string>"]
}
```

- `key_sequence` must be a string of exactly four characters, each `'0'` or `'1'`.
- `lock_registers` must be a list of exactly four strings, each a valid hierarchical signal name from the netlist (e.g., `"top.lock_reg[0]"`). The order must correspond to the serial loading order: the first bit of the key sequence is loaded into the first register in the list.

## Constraints

- The netlist is synthesizable and compiles cleanly with `iverilog -g2012`.
- The circuit has a single clock domain and an active-low asynchronous reset.
- The key sequence is exactly 4 bits long.
- The functional behavior is only observable after the correct key sequence has been applied while reset is de-asserted.