#!/usr/bin/env python3
"""Generate a GateLift-Bench case from source RTL using Yosys flattening."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def _run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(msg or f"Command failed: {' '.join(cmd)}")


def _infer_keywords(intent: str):
    candidates = [
        "adder",
        "multiplier",
        "alu",
        "fsm",
        "counter",
        "uart",
        "aes",
        "sha",
        "branch",
        "datapath",
        "state",
        "control",
        "combinational",
        "sequential",
    ]
    lowered = intent.lower()
    out = [c for c in candidates if c in lowered]
    return out or ["hardware", "rtl"]


def generate_case(source_rtl: Path, top_module: str, output_root: Path, case_id: str, tier: int, intent: str):
    if not shutil.which("yosys"):
        raise RuntimeError("yosys is required but not found in PATH")

    case_dir = output_root / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    gt_path = case_dir / "ground_truth_rtl.v"
    prompt_path = case_dir / "prompt_netlist.v"
    metadata_path = case_dir / "metadata.json"
    source_copy = case_dir / "source_rtl.v"

    source_copy.write_text(source_rtl.read_text(encoding="utf-8"), encoding="utf-8")
    gt_path.write_text(source_rtl.read_text(encoding="utf-8"), encoding="utf-8")

    with tempfile.TemporaryDirectory() as td:
        ys = Path(td) / "flatten.ys"
        ys.write_text(
            "\n".join(
                [
                    f"read_verilog {source_copy}",
                    f"hierarchy -top {top_module}",
                    "synth",
                    "flatten",
                    "opt",
                    f"write_verilog {prompt_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        _run(["yosys", "-q", str(ys)])

    metadata = {
        "id": case_id,
        "tier": tier,
        "top_module": top_module,
        "intent_summary": intent,
        "semantic_keywords": _infer_keywords(intent),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(f"Created case at: {case_dir}")
    print(f"  ground truth: {gt_path}")
    print(f"  prompt netlist: {prompt_path}")
    print(f"  metadata: {metadata_path}")


def build_parser():
    parser = argparse.ArgumentParser(description="Generate GateLift-Bench case from source RTL")
    parser.add_argument("--source", required=True, help="Path to source RTL Verilog file")
    parser.add_argument("--top", required=True, help="Top module name")
    parser.add_argument("--case-id", required=True, help="Case directory name, for example tier1_foo")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], required=True, help="Difficulty tier")
    parser.add_argument("--intent", required=True, help="Human intent summary sentence")
    parser.add_argument("--output-root", default="examples", help="Benchmark examples root directory")
    return parser


def main():
    args = build_parser().parse_args()
    generate_case(
        source_rtl=Path(args.source).resolve(),
        top_module=args.top,
        output_root=Path(args.output_root).resolve(),
        case_id=args.case_id,
        tier=args.tier,
        intent=args.intent,
    )


if __name__ == "__main__":
    main()
