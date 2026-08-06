# Clock-Glitch Vulnerability Analysis in Authentication FSM

## Objective

You are given a Verilog RTL design of a simple authentication finite-state machine (FSM), a fault model describing a single-cycle clock glitch, and a normal-operation trace. Your task is to analyze these artifacts and identify the vulnerable clock cycle and the critical registers where a skipped register update can allow an attacker to bypass authentication and gain unauthorized access.

## Input Artifacts

All input files are located in the `inputs/` directory:

- **`auth_fsm.v`** – Verilog RTL of the authentication FSM. It contains the state register and a result register that control the authentication flow.
- **`fault_model.json`** – A JSON file describing the fault injection capability: a single clock glitch that causes exactly one register update to be skipped during a chosen clock cycle, while combinational logic continues to evaluate normally.
- **`normal_trace.txt`** – A cycle-by-cycle trace of the FSM operating under normal conditions (no fault) for a successful authentication sequence. It shows the values of the state and result registers at each cycle.

## Expected Output

You must produce a single JSON file at `submission/vulnerability_report.json` with the following structure:

```json
{
  "vulnerable_cycle": <integer>,
  "state_register": "<string>",
  "result_register": "<string>",
  "explanation": "<string>"
}
```

- **`vulnerable_cycle`** – The clock cycle index (integer) where injecting the glitch causes the authentication bypass.
- **`state_register`** – The exact signal name (string) of the state register in `auth_fsm.v` whose update, if skipped, contributes to the vulnerability.
- **`result_register`** – The exact signal name (string) of the result register in `auth_fsm.v` whose stale value enables the bypass.
- **`explanation`** – A non-empty string briefly describing the mechanism by which the skipped update leads to unauthorized access.

## Constraints

- Your analysis must be based solely on the provided input artifacts.
- The fault model describes a single clock cycle where one register update is skipped while combinational logic continues to evaluate.
- The normal trace represents the expected cycle-by-cycle behavior without faults.

## Submission

Place your answer in `submission/vulnerability_report.json`. A starter file with placeholder values is provided; replace it with your findings.