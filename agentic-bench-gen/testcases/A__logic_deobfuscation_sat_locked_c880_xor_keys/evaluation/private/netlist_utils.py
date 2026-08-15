"""
netlist_utils.py

Private helper module for evaluate.py. Parses the fixed structural Verilog
netlist at inputs/locked_c880.v using only generic regex/tokenization over
the documented primitive-instantiation syntax:

    gatetype instname (out, in1[, in2]);

where gatetype is one of: and, nand, or, nor, not, buf, xor, xnor.

No golden values (key indices, dead-bit positions, gate names) are ever
hardcoded here -- everything is derived structurally from whatever text is
present in the netlist file, so this module works identically regardless
of which correct submission is being graded (the netlist under inputs/
never changes across submissions).
"""

import re


_GATE_TYPES = ["and", "nand", "or", "nor", "not", "buf", "xor", "xnor"]

_KEYIN_RE = re.compile(r'keyIn\s*\[\s*(\d+)\s*\]')

_GATE_INST_RE = re.compile(
    r'\b(' + '|'.join(_GATE_TYPES) + r')\s+(\w+)\s*\(([^)]*)\)\s*;'
)

_KEYIN_PORT_RE = re.compile(
    r'input\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*keyIn\s*;'
)

_OUTPUT_DECL_RE = re.compile(r'output\s+([^;]+);')


def _strip_comments(text):
    return re.sub(r'//.*', '', text)


def _parse_key_width(text):
    m = _KEYIN_PORT_RE.search(text)
    if not m:
        raise ValueError(
            "could not locate a 'input [hi:lo] keyIn;' style declaration "
            "for the key bus in the netlist"
        )
    hi = int(m.group(1))
    lo = int(m.group(2))
    return abs(hi - lo) + 1


def _parse_output_nets(text):
    """Collect all net names declared via `output ...;` port declarations."""
    output_nets = set()
    for om in _OUTPUT_DECL_RE.finditer(text):
        names_part = om.group(1)
        # Strip any bit-range annotations like [0:7] just in case.
        names_part = re.sub(r'\[[^\]]*\]', '', names_part)
        # Strip optional type keywords that could precede names.
        names_part = re.sub(r'\b(wire|reg|logic)\b', '', names_part)
        for nm in names_part.split(','):
            nm = nm.strip()
            if nm:
                output_nets.add(nm)
    return output_nets


def _parse_instances(text):
    """
    Parse every primitive gate instantiation of the form
        gatetype instname (out, in1[, in2, ...]);
    Returns a list of dicts: {gate_type, name, output_net, input_nets}
    and the set of all instance names encountered.
    """
    instances = []
    all_instance_names = set()

    for gm in _GATE_INST_RE.finditer(text):
        gtype = gm.group(1)
        iname = gm.group(2)
        args_str = gm.group(3)

        args = [a.strip() for a in args_str.split(',') if a.strip() != '']
        if not args:
            continue

        output_net = args[0]
        input_nets = args[1:]

        all_instance_names.add(iname)
        instances.append({
            'gate_type': gtype.upper(),
            'name': iname,
            'output_net': output_net,
            'input_nets': input_nets,
        })

    return instances, all_instance_names


def _build_key_gate_table(instances):
    """
    For each instance whose input args reference a literal keyIn[<i>],
    record it as the structural key-gate for bit index <i>.
    """
    key_gate_table = {}
    for inst in instances:
        for arg in inst['input_nets']:
            km = _KEYIN_RE.search(arg)
            if km:
                idx = int(km.group(1))
                key_gate_table[idx] = {
                    'gate_type': inst['gate_type'],
                    'gate_name': inst['name'],
                    'output_net': inst['output_net'],
                }
                break  # an instance is expected to reference at most one keyIn bit
    return key_gate_table


def _build_net_consumer_graph(instances):
    """
    Build a mapping net_name -> list of instances that consume that net as
    one of their (non-keyIn) inputs. This lets us walk forward from a gate's
    output net through the rest of the design.
    """
    net_to_consumers = {}
    for inst in instances:
        for arg in inst['input_nets']:
            if _KEYIN_RE.search(arg):
                # keyIn[i] is a primary key input literal, not an internal net
                # with a driving instance in this fanout graph.
                continue
            net_to_consumers.setdefault(arg, []).append(inst)
    return net_to_consumers


def _reaches_any_output(start_net, net_to_consumers, output_nets):
    """BFS/DFS forward from start_net through consuming instances' output
    nets until (a) a primary output net is reached (True) or (b) the
    frontier is exhausted with no output reached (False)."""
    visited = set()
    stack = [start_net]
    while stack:
        net = stack.pop()
        if net in visited:
            continue
        visited.add(net)
        if net in output_nets:
            return True
        for inst in net_to_consumers.get(net, []):
            out_net = inst['output_net']
            if out_net not in visited:
                stack.append(out_net)
    return False


def parse_netlist(path):
    """
    Parse the fixed structural netlist at `path` and return a dict:
        {
          'key_width': int,
          'all_instance_names': set of str,
          'key_gate_table': { key_bit_index(int): {gate_type, gate_name, output_net} },
          'live_indices': sorted list of int,
          'dead_indices': sorted list of int,
        }
    """
    with open(path) as f:
        raw_text = f.read()

    text = _strip_comments(raw_text)

    key_width = _parse_key_width(text)
    output_nets = _parse_output_nets(text)
    if not output_nets:
        raise ValueError(
            "could not locate any 'output ...;' port declarations in the netlist"
        )

    instances, all_instance_names = _parse_instances(text)
    if not instances:
        raise ValueError("no gate primitive instantiations found in the netlist")

    key_gate_table = _build_key_gate_table(instances)
    if not key_gate_table:
        raise ValueError(
            "no gate instances referencing keyIn[<i>] were found; "
            "cannot derive structural key-gate ground truth"
        )

    net_to_consumers = _build_net_consumer_graph(instances)

    live_indices = []
    for idx in range(key_width):
        gt = key_gate_table.get(idx)
        if gt is None:
            # No structural key gate found for this index at all; treat as
            # not live (cannot be confirmed reachable).
            continue
        if _reaches_any_output(gt['output_net'], net_to_consumers, output_nets):
            live_indices.append(idx)

    live_indices = sorted(set(live_indices))
    dead_indices = sorted(set(range(key_width)) - set(live_indices))

    return {
        'key_width': key_width,
        'all_instance_names': all_instance_names,
        'key_gate_table': key_gate_table,
        'live_indices': live_indices,
        'dead_indices': dead_indices,
    }