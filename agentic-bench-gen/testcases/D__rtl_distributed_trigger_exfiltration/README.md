# RTL Hardware Trojan Detection

## Objective

Analyze the provided RTL design and identify any suspicious logic that could leak internal state or cause unintended behavior. Submit a report detailing all findings.

## Input Artifacts

The design consists of four Verilog files located in the `inputs/` directory:

- `top.v` – Top-level module
- `counter.v` – Counter submodule
- `command_decoder.v` – Command decoder submodule
- `error_handler.v` – Error handler submodule

All modules are synthesizable with `iverilog -g2012` and the total design is under 250 lines of Verilog.

## Constraints

- Do **not** modify the input RTL files.
- Submit only the analysis report.

## Submission

Place your analysis report at `submission/trojan_report.json`. The file must be valid JSON and conform to the following schema:

```json
{
  "trojan_detected": true | false,
  "findings": [
    {
      "module": "string",
      "signal": "string",
      "rationale": "string",
      "confidence": 0.0 .. 1.0
    }
  ],
  "overall_confidence": 0.0 .. 1.0
}
```

- `trojan_detected` (boolean): `true` if any malicious or suspicious logic is found, `false` otherwise.
- `findings` (array of objects): a list of identified suspicious logic blocks. Each object must have:
  - `module` (string): the name of the module containing the finding.
  - `signal` (string): the specific signal or logic path identified.
  - `rationale` (string): a detailed explanation of why this logic is suspicious, including its potential impact.
  - `confidence` (number): a score between 0.0 and 1.0 indicating confidence in the finding.
- `overall_confidence` (number): a score between 0.0 and 1.0 indicating overall confidence in the analysis.