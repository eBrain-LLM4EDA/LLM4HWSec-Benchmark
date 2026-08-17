#!/usr/bin/env python3
"""
netlist_utils.py -- shared structural Verilog netlist parsing helper.

Provides parse_netlist(path) which regex-parses a flat structural
Verilog netlist built from the fixed cell_library.v cell set
(AND2, OR2, INV, BUF, DFF, TIEHI, TIELO, MUX2) and returns:

    instances:  dict[instance_name] -> cell_type
    net_driver: dict[net_name]      -> driving instance_name
    net_loads:  dict[net_name]      -> list[instance_name] (readers)

This module intentionally contains no hardcoded instance names; all
facts are derived purely from parsing the netlist text against the
fixed cell-type -> output-port-name convention documented below, which
is fixed by the public cell_library.v port-order contract, not by any
specific design's instance naming.
"""

import re

# Fixed output-port-name table per cell type, driven by the public
# cell_library.v conventions (AND2/OR2/INV/BUF/DFF/TIEHI/TIELO/MUX2).
# Every other named port on an instance of these cell types is treated
# as an input (i.e. a load of whatever net is connected to it).
OUTPUT_PORT_NAME = {
    "AND2": "o",
    "OR2": "o",
    "INV": "o",
    "BUF": "o",
    "DFF": "q",
    "TIEHI": "o",
    "TIELO": "o",
    "MUX2": "o",
}

KNOWN_CELL_TYPES = set(OUTPUT_PORT_NAME.keys())


def strip_comments(text):
    """Remove // line comments and /* */ block comments."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def parse_netlist(path):
    """
    Parse a flat structural Verilog netlist and return:
      instances:  dict[instance_name] -> cell_type
      net_driver: dict[net_name] -> instance_name (driving instance)
      net_loads:  dict[net_name] -> list[instance_name] (instances that
                  read this net on a non-output port)

    Handles multi-line instantiations, named (.port(net)) connections,
    and no-connect () ports. Purely structural; no hardcoded instance
    names beyond the fixed cell-type -> output-port-name table above.
    """
    with open(path, "r") as f:
        raw = f.read()
    text = strip_comments(raw)

    instances = {}
    net_driver = {}
    net_loads = {}

    # Match: CELLTYPE INSTNAME ( ... ) ;
    # Cell type must be one of the known types (word boundary), instance
    # name is a Verilog identifier, body is captured non-greedily up to
    # the matching ");" -- since bodies here don't contain nested
    # parens other than the port list itself, a non-greedy match to the
    # first ");" is sufficient and robust across multi-line formatting.
    inst_pattern = re.compile(
        r"\b(" + "|".join(sorted(KNOWN_CELL_TYPES)) + r")\s+"
        r"([A-Za-z_][A-Za-z0-9_$]*)\s*"
        r"\(([^;]*?)\)\s*;",
        re.DOTALL,
    )

    for m in inst_pattern.finditer(text):
        cell_type = m.group(1)
        inst_name = m.group(2)
        port_body = m.group(3)

        instances[inst_name] = cell_type
        out_port = OUTPUT_PORT_NAME.get(cell_type)

        # Named port connections: .portname ( net_expr )
        # net_expr may be empty (no-connect) or contain a bit-select.
        port_conn_pattern = re.compile(
            r"\.\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\(\s*([^()]*?)\s*\)"
        )
        found_named = False
        for pm in port_conn_pattern.finditer(port_body):
            found_named = True
            port_name = pm.group(1)
            net_expr = pm.group(2).strip()
            if net_expr == "":
                continue  # no-connect
            # Extract base net identifier(s) referenced; a net_expr
            # could itself be a simple identifier, a bit-select
            # identifier[N], or a concatenation {a,b,...}. We take all
            # identifiers referenced (ignoring numeric literals) so
            # each contributes to driver/load maps appropriately.
            net_names = re.findall(r"[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?", net_expr)
            for net in net_names:
                base_net = net.split("[")[0]
                full_net = net
                if port_name == out_port:
                    net_driver[full_net] = inst_name
                    net_driver.setdefault(base_net, inst_name)
                else:
                    net_loads.setdefault(full_net, []).append(inst_name)
                    net_loads.setdefault(base_net, []).append(inst_name)

        if not found_named:
            # Positional connections (rare in this generator, but
            # handle defensively): split on top-level commas.
            parts = [p.strip() for p in port_body.split(",") if p.strip() != ""]
            for idx, net_expr in enumerate(parts):
                net_names = re.findall(r"[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?", net_expr)
                for net in net_names:
                    base_net = net.split("[")[0]
                    # Without a port-name mapping we cannot reliably
                    # tell output vs input positionally beyond "first
                    # port is output" convention used by this cell
                    # library; treat idx==0 as output.
                    if idx == 0:
                        net_driver[net] = inst_name
                        net_driver.setdefault(base_net, inst_name)
                    else:
                        net_loads.setdefault(net, []).append(inst_name)
                        net_loads.setdefault(base_net, []).append(inst_name)

    return instances, net_driver, net_loads