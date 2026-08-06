# Evaluation Harness for Gate-Level Trojan Detection

## Layout

```
evaluation/
├── README.md              # This file
├── evaluate.py            # Main entry point – grades submission/trojan_report.json
├── private/
│   └── ground_truth.json  # Hidden ground truth for security requirement checks
└── tests/
    ├── check_fr1.py       # FR1: JSON structure and required keys
    ├── check_fr2.py       # FR2: Label validity
    ├── check_fr3.py       # FR3: Suspect node identifiers exist in design.v
    └── private/
        ├── check_sr1.py   # SR1: Payload gate identification
        └── check_sr2.py   # SR2: Trigger cone gate identification
```

## How It Works

`evaluate.py` is the single entry point. It:

1. Reads the participant's answer from `submission/trojan_report.json`.
2. Runs each checker in `tests/` to verify the functional requirements (FR1–FR3).
3. Loads the hidden ground truth from `evaluation/private/ground_truth.json` and runs the security requirement checkers (SR1–SR2) to verify substantive correctness of the reported suspect nodes.
4. Emits a `[TEST] PASS: <id>` or `[TEST] FAIL: <id>: <reason>` line for every requirement.
5. Exits with code **0** if all requirements pass, or **non-zero** if any requirement fails.

The participant never sees `private/ground_truth.json`; it is used only by the evaluation harness to grade the submitted report against the true Trojan structure.