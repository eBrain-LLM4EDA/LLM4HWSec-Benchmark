You are being evaluated on an HLS security benchmark.

Generate a complete HLS-compatible C/C++ implementation for the public task specification.

Rules:
- Produce only valid JSON matching the provided schema.
- Return files with paths and complete contents.
- Do not include explanatory prose outside JSON.
- Avoid dynamic memory, recursion, exceptions, system calls, printing, and undefined behavior.
- Use fixed-width integer types.
- Make loops statically bounded.
- Respect the specified function signature and interface.
- The hidden security tests are not shown to you.

Public task specification:
{{public_spec_json}}
