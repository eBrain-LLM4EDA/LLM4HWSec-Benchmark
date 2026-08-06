"""
Private static-analysis helper for the secure-boot RTL.

This module parses ``inputs/secure_boot_check.v`` using regular
expressions only (no simulation/elaboration is required) in order to
derive ground-truth facts that ``evaluate.py`` cross-references against
a submitted ``vulnerability_report.json``.

Every fact returned here is *derived* from the literal text of the RTL
file at evaluation time -- nothing is hardcoded as a literal register or
state name. This keeps the checker robust to any future edit of the
(fixed, non-participant-editable) RTL file, and documents exactly how
the "ground truth" is computed so the logic is auditable.

Public functions:
    extract_registers(text)          -> list[{"name","width","line"}]
    extract_fsm_states(text)         -> set[str]
    find_output_gating_signal(text)  -> dict with keys:
        output_signal, auth_signal, state_signal, done_state, compare_state
"""

import re


# ---------------------------------------------------------------------
# Low-level helpers: locate clocked always-blocks with correct begin/end
# nesting (Verilog has no braces, so naive substring search on "end"
# would also match "endcase"/"endmodule"; word-boundary tokens avoid
# that).
# ---------------------------------------------------------------------

_TOKEN_RE = re.compile(r'\bbegin\b|\bend\b')


def _find_block_end(text, start_pos):
    """Return the index just past the 'end' that closes the first
    'begin' encountered at or after start_pos, honoring nesting."""
    depth = 0
    started = False
    for m in _TOKEN_RE.finditer(text, start_pos):
        if m.group() == 'begin':
            depth += 1
            started = True
        else:
            depth -= 1
        if started and depth == 0:
            return m.end()
    return len(text)


def extract_always_blocks(text, edge='posedge'):
    """Return a list of dicts describing every always-block whose
    sensitivity list uses the given edge (default posedge), each with
    keys: clock (the signal name), start, end, text."""
    blocks = []
    header_re = re.compile(
        r'always\s*@\s*\(\s*' + re.escape(edge) + r'\s+(\w+)\s*\)',
        re.IGNORECASE,
    )
    for m in header_re.finditer(text):
        clock_name = m.group(1)
        end_pos = _find_block_end(text, m.end())
        block_text = text[m.start():end_pos]
        blocks.append({
            'clock': clock_name,
            'start': m.start(),
            'end': end_pos,
            'text': block_text,
        })
    return blocks


# ---------------------------------------------------------------------
# 1. extract_registers
# ---------------------------------------------------------------------

# Matches a 'reg' declaration whether it appears as a standalone
# statement ("reg [31:0] sig_shift;") or as part of a module port
# declaration ("output reg        done"), by requiring only that the
# identifier be followed (after optional whitespace/newlines) by one of
# ';', ',' or ')' rather than requiring an immediate terminating ';'.
_REG_DECL_RE = re.compile(
    r'\breg\b\s*(\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*([a-zA-Z_]\w*)\s*(?=[;,)])'
)


def extract_registers(text):
    """Return a list of {"name","width","line"} for every reg that is
    declared with 'reg' (optionally ranged) AND is actually assigned via
    '<=' inside a posedge-clk always block. 'line' is the 1-indexed line
    number of the first such assignment found inside a posedge-clk
    always block."""
    declarations = {}
    order = []
    for m in _REG_DECL_RE.finditer(text):
        msb, lsb, name = m.group(2), m.group(3), m.group(4)
        if msb is not None and lsb is not None:
            width = abs(int(msb) - int(lsb)) + 1
        else:
            width = 1
        if name not in declarations:
            declarations[name] = width
            order.append(name)

    clk_blocks = [
        b for b in extract_always_blocks(text, edge='posedge')
        if b['clock'] == 'clk'
    ]

    registers = []
    for name in order:
        width = declarations[name]
        assign_re = re.compile(
            r'\b' + re.escape(name) + r'\b\s*(\[[^\]]*\])?\s*<='
        )
        first_line = None
        for b in clk_blocks:
            m = assign_re.search(b['text'])
            if m:
                abs_pos = b['start'] + m.start()
                line_no = text.count('\n', 0, abs_pos) + 1
                if first_line is None or line_no < first_line:
                    first_line = line_no
        if first_line is not None:
            registers.append({'name': name, 'width': width, 'line': first_line})

    registers.sort(key=lambda r: r['line'])
    return registers


# ---------------------------------------------------------------------
# 2. extract_fsm_states
# ---------------------------------------------------------------------

_LOCALPARAM_RE = re.compile(
    r'localparam\s*(\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*(\w+)\s*='
)


def _find_state_case(text, reg_names):
    """Locate the first `case (X)` block whose selector X is one of the
    given register names and whose body has at least one non-default
    label. Returns (var, labels_set) or (None, None)."""
    case_re = re.compile(r'\bcase\s*\(\s*(\w+)\s*\)')
    for m in case_re.finditer(text):
        var = m.group(1)
        if var not in reg_names:
            continue
        end_idx = text.find('endcase', m.end())
        if end_idx == -1:
            continue
        body = text[m.end():end_idx]
        labels = set(re.findall(r'(?m)^\s*([a-zA-Z_]\w*)\s*:', body))
        labels.discard('default')
        if labels:
            return var, labels
    return None, None


def extract_fsm_states(text):
    """Return the set of localparam names that (a) are used as case
    labels of the register that the top-level FSM case-statement
    switches on, and (b) share that register's declared bit-width."""
    registers = extract_registers(text)
    reg_names = {r['name'] for r in registers}
    reg_width_by_name = {r['name']: r['width'] for r in registers}

    localparams = []
    for m in _LOCALPARAM_RE.finditer(text):
        msb, lsb, name = m.group(2), m.group(3), m.group(4)
        width = (abs(int(msb) - int(lsb)) + 1) if (msb is not None and lsb is not None) else None
        localparams.append({'name': name, 'width': width})

    state_var, labels = _find_state_case(text, reg_names)
    if state_var is None:
        return set()

    state_width = reg_width_by_name.get(state_var)
    result = set()
    for lp in localparams:
        if lp['name'] in labels:
            if state_width is None or lp['width'] is None or lp['width'] == state_width:
                result.add(lp['name'])
    return result


# ---------------------------------------------------------------------
# 3. find_output_gating_signal
# ---------------------------------------------------------------------

_ASSIGN_RE = re.compile(r'assign\s+(\w+)\s*=\s*([^;]+);')


def _find_compare_state(text, auth_signal, state_var, fsm_states):
    """Within the always-block that assigns auth_signal, find the
    branch that computes it from an equality test between two operands
    that are NOT the state register itself (i.e. the real signature
    comparison), and return the FSM state literal that gates that
    branch (e.g. 'COMPARE')."""
    blocks = extract_always_blocks(text, edge='posedge')
    assign_pattern = re.compile(
        r'\b' + re.escape(auth_signal) + r'\s*<=\s*\(\s*(\w+)\s*==\s*(\w+)\s*\)'
    )
    state_pattern = re.compile(
        r'\b' + re.escape(state_var) + r'\s*==\s*(\w+)\s*\)'
    )

    for block in blocks:
        btext = block['text']
        if not re.search(r'\b' + re.escape(auth_signal) + r'\s*<=', btext):
            continue

        segments = re.split(r'\b(?:else\s+if|if)\b', btext)
        for seg in segments:
            assign_m = assign_pattern.search(seg)
            if not assign_m:
                continue
            operand_a, operand_b = assign_m.group(1), assign_m.group(2)
            if operand_a == state_var or operand_b == state_var:
                # This branch just re-checks state, not a real
                # signature/data comparison; skip it.
                continue
            state_m = state_pattern.search(seg)
            if state_m and state_m.group(1) in fsm_states:
                return state_m.group(1)
    return None


def find_output_gating_signal(text):
    """Locate the 'assign <output> = ...' statement that gates the
    module's success output on both a state-equality test and a 1-bit
    register value, and return the derived identifiers:
        output_signal  - the assign target (e.g. 'boot_allowed')
        auth_signal    - the 1-bit reg read directly by that assign
                          (e.g. 'auth_ok')
        state_signal   - the state/control register compared against a
                          state literal in that assign (e.g. 'state')
        done_state     - the state literal compared to in that assign
                          (e.g. 'DONE')
        compare_state  - the state literal that gates the branch where
                          auth_signal is computed from a genuine data
                          comparison (e.g. 'COMPARE')
    Returns {} if any of these cannot be determined.
    """
    registers = extract_registers(text)
    reg_width_by_name = {r['name']: r['width'] for r in registers}
    reg_names = set(reg_width_by_name.keys())
    fsm_states = extract_fsm_states(text)

    state_var, _labels = _find_state_case(text, reg_names)
    if state_var is None:
        return {}

    for m in _ASSIGN_RE.finditer(text):
        out_name = m.group(1)
        rhs = m.group(2)

        comp_re = re.compile(r'\b' + re.escape(state_var) + r'\s*==\s*(\w+)')
        comp_m = comp_re.search(rhs)
        if not comp_m:
            continue

        auth_candidates = [
            name for name, w in reg_width_by_name.items()
            if w == 1 and name != state_var
            and re.search(r'\b' + re.escape(name) + r'\b', rhs)
        ]
        if not auth_candidates:
            continue

        done_state = comp_m.group(1)
        auth_signal = auth_candidates[0]
        compare_state = _find_compare_state(text, auth_signal, state_var, fsm_states)

        return {
            'output_signal': out_name,
            'auth_signal': auth_signal,
            'state_signal': state_var,
            'done_state': done_state,
            'compare_state': compare_state,
        }

    return {}