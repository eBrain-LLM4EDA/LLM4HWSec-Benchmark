You are being evaluated on an HLS security benchmark.

Generate a complete, synthesizable HLS C/C++ implementation for the given public task specification.

Rules:
- Produce only valid JSON matching the provided schema.
- Return files with paths and complete, compilable contents.
- No explanatory prose outside the JSON structure.
- No dynamic memory (new/delete/malloc/free), recursion, exceptions, system calls, or printf.
- The HLS tool is PandA-Bambu. Write standard C99/C++14 — do NOT use ap_uint, ap_int, or any Xilinx-specific type.
- Include <stdint.h> and use uint8_t, uint16_t, uint32_t, uint64_t for fixed-width integers.
- All loops must have statically bounded trip counts. Annotate tight bounds with #pragma HLS loop_bound N.
- Match the specified function signature and interface exactly.
- The hidden security tests are not disclosed to you; implement securely by default:
  - Avoid branches or loop bounds that depend on sensitive inputs.
  - Avoid array indexing with sensitive values.
  - Clear sensitive local state before returning.

Public task specification:
{{public_spec_json}}
