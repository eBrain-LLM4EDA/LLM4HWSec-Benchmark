# Locking Scheme Description

The provided netlist implements a **point-function locking scheme** (SARLock style). The lock consists of a key comparator that monitors the primary inputs of the circuit. The comparator performs an equality check against a hidden 6-bit key.

## How It Works

- The comparator is built from **XNOR gates** followed by a **tree of AND gates**.
- Each XNOR gate compares one selected input bit against the corresponding key bit. An XNOR outputs `1` when the input bit matches the key bit.
- The AND tree combines all XNOR outputs. The tree output is `1` only when **all** input bits match their respective key bits — i.e., when the full 6-bit input pattern equals the hidden key.
- The comparator output is XORed with exactly **one functional output bit** of the circuit.

## Effect on Circuit Behavior

- For **all input patterns except one**, the comparator output is `0`, and the circuit behaves as the original (unlocked) design.
- For the **single protected input pattern** that matches the hidden key, the comparator output becomes `1`, and the XOR gate flips the target output bit, corrupting the result.

Because the lock corrupts the output on at most one input pattern, conventional SAT-based attacks that rely on many discriminating inputs are ineffective. Recovering the key requires structural analysis of the comparator cone and/or identification of the protected input pattern using oracle access.