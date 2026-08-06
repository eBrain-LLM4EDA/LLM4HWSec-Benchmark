import re

def parse_netlist(path):
    """Return (cells, nets) sets from a flat gate-level Verilog file."""
    cells = set()
    nets = set()
    try:
        with open(path, "r") as f:
            text = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"{path} not found")

    # Cell instances:  <cell_type> <instance_name> ( ... );
    # e.g.  AOI21 aoi_trig (.A0(...), ...);
    cell_pattern = re.compile(
        r'^\s*([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(', re.MULTILINE
    )
    for m in cell_pattern.finditer(text):
        cells.add(m.group(2))

    # Nets: wire declarations and continuous assignments
    # wire n1, n2, ...;
    wire_pattern = re.compile(r'^\s*wire\s+([^;]+);', re.MULTILINE)
    for m in wire_pattern.finditer(text):
        for name in m.group(1).split(','):
            name = name.strip()
            if name:
                nets.add(name)

    # Also catch nets that appear as port connections (inside parentheses)
    # This is a simple heuristic: any identifier that is not a keyword and
    # appears in a port list could be a net. We'll just add all identifiers
    # that look like net names (lowercase with optional underscores/digits).
    # To avoid false positives, we only add identifiers that appear in
    # port connection lists and are not already known cells.
    port_conn_pattern = re.compile(r'\.\w+\s*\(\s*(\w+)\s*\)')
    for m in port_conn_pattern.finditer(text):
        net_candidate = m.group(1)
        if net_candidate not in cells and re.match(r'^[a-z_]\w*$', net_candidate):
            nets.add(net_candidate)

    return cells, nets