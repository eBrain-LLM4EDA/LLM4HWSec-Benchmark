# Security Specification: AES-128 IFT

## Applicable CWEs
- **CWE-200**: Exposure of Sensitive Information to an Unauthorized Actor

## Security Properties

### Information Flow Policy
- `key` port: Security domain = SECRET
- `plaintext` port: Security domain = PUBLIC
- `ciphertext` port: Security domain = PUBLIC (authorized declassification only)
- No other output ports permitted

### Taint Propagation Rules
1. `XOR(SECRET, PUBLIC) → SECRET`
2. `XOR(SECRET, SECRET) → SECRET`
3. `SBOX_LOOKUP(index=SECRET) → SECRET`
4. `SHIFT/PERMUTATION(SECRET) → SECRET`
5. Declassification: only at ciphertext output, gated by completion of full cipher

### Prohibited Patterns
- Debug ports carrying key-dependent intermediate values
- Round key arrays accessible from top-level interface
- Untracked mixing of SECRET and PUBLIC domains
