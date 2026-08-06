# Design Brief: Mixed-Scheme Locked Circuit

## Overview

The provided netlist (`locked_netlist.v`) implements a small combinational logic function that has been locked with a 4-bit key. The locking uses a mixture of two common styles:

- **XOR/XNOR-based key gates** – a key bit is XORed or XNORed with an internal signal.
- **MUX-based key gates** – a key bit selects between the true and complemented version of an internal signal.

The circuit has two 2-bit primary inputs (`a[1:0]`, `b[1:0]`), a 4-bit key input (`key[3:0]`), and two 2-bit primary outputs (`y[1:0]`). When the correct key is applied, the outputs match the original (unlocked) functionality. With an incorrect key, the outputs are corrupted.

## Oracle Vectors

The file `oracle_vectors.txt` contains input-output pairs that represent the correct behavior of the circuit when driven with the correct key. Each line has the format:

```
<hex_input> <hex_output>
```

- The hex input encodes the concatenated primary inputs `{a, b}` as a single hexadecimal value (4 bits).
- The hex output encodes the expected `y` value (2 bits) as a single hexadecimal digit.

For example, a line `A 3` means: when `{a, b} = 4'b1010` (i.e., `a=2'b10`, `b=2'b10`), the correct output `y` should be `2'b11`.

You can use these vectors to verify your key recovery by simulating the netlist with your candidate key and checking whether the outputs match the oracle.

## Simulation Tips

- Compile the netlist with a Verilog simulator (e.g., Icarus Verilog: `iverilog -g2012 locked_netlist.v`).
- Write a small testbench that applies the oracle input vectors and your candidate key, then compares the outputs against the expected values.
- A correct key will produce outputs that match **all** oracle vectors exactly.

## Key Width

The key width is 4 bits, as stated in `public_key_width.txt`. Your recovered key must be a 4-bit binary string.