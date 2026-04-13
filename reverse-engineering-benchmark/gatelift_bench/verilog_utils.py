import re
from collections import Counter
from typing import Dict, List, Set, Tuple


def get_module_name(verilog_text: str) -> str:
    match = re.search(r"\bmodule\s+([a-zA-Z_][a-zA-Z0-9_$]*)", verilog_text)
    return match.group(1) if match else "top"


def extract_bus_declarations(verilog_text: str) -> Set[Tuple[str, int, str]]:
    """Return (signal_name, width, direction/type) signatures."""
    signatures: Set[Tuple[str, int, str]] = set()
    pattern = re.compile(
        r"\b(input|output|inout|wire|reg|logic)\b\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*([^;]+);"
    )
    for kind, msb, lsb, tail in pattern.findall(verilog_text):
        width = 1
        if msb and lsb:
            width = abs(int(msb) - int(lsb)) + 1
        for name in tail.split(","):
            clean = name.strip().split()[-1]
            if clean:
                signatures.add((clean, width, kind))
    return signatures


def extract_operator_counter(verilog_text: str) -> Counter:
    """Approximate operator-level structure from assign/always statements."""
    ops = Counter()
    token_map = {
        "+": "add",
        "-": "sub",
        "*": "mul",
        "^": "xor",
        "&": "and",
        "|": "or",
        "<<": "shl",
        ">>": "shr",
        "==": "eq",
        "!=": "neq",
        "<": "lt",
        ">": "gt",
        "?": "mux",
    }

    for token, name in token_map.items():
        ops[name] += verilog_text.count(token)

    gate_re = re.compile(r"\b(and|or|xor|xnor|nand|nor|not|buf)\b", re.IGNORECASE)
    for gate in gate_re.findall(verilog_text):
        ops[gate.lower()] += 1

    return ops


def extract_graph_shape(verilog_text: str) -> Dict[str, int]:
    gate_instances = len(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_$]*\s+[a-zA-Z_][a-zA-Z0-9_$]*\s*\(", verilog_text))
    assign_count = len(re.findall(r"\bassign\b", verilog_text))
    wire_count = len(re.findall(r"\bwire\b", verilog_text))
    return {
        "gate_instances": gate_instances,
        "assign_count": assign_count,
        "wire_count": wire_count,
    }


def keyword_overlap(summary: str, keywords: List[str]) -> Tuple[int, int]:
    lowered = summary.lower()
    hits = sum(1 for k in keywords if k.lower() in lowered)
    return hits, len(keywords)
