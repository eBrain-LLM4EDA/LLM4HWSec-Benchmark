import json
import os
import re
import subprocess
import sys
import tempfile

# Import hidden ground truth
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'private'))
from ground_truth import CORRECT_KEY, CORRECT_FEEDBACK_GATES

def fail(requirement_id, reason):
    print(f"[TEST] FAIL: {requirement_id}: {reason}")
    return False

def pass_(requirement_id):
    print(f"[TEST] PASS: {requirement_id}")
    return True

def main():
    results = {}

    # ------------------------------------------------------------------
    # FR1: submission/recovered_key.json must exist and be valid JSON
    # ------------------------------------------------------------------
    submission_path = os.path.join('submission', 'recovered_key.json')
    if not os.path.isfile(submission_path):
        fail('FR1', f'{submission_path} not found')
        results['FR1'] = False
    else:
        try:
            with open(submission_path, 'r') as f:
                data = json.load(f)
            results['FR1'] = pass_('FR1')
        except json.JSONDecodeError as e:
            fail('FR1', f'JSON parse error: {e}')
            results['FR1'] = False
            data = None

    # If FR1 failed, we cannot proceed with other checks that need data
    if not results.get('FR1', False):
        # Still emit failures for remaining requirements
        for rid in ['FR2', 'FR3', 'SR1', 'SR2']:
            if rid not in results:
                fail(rid, 'cannot check because FR1 failed')
                results[rid] = False
        sys.exit(1)

    # ------------------------------------------------------------------
    # FR2: key field present, correct length, only '0'/'1'
    # ------------------------------------------------------------------
    key_width = None
    hints_path = os.path.join('inputs', 'hints.txt')
    if not os.path.isfile(hints_path):
        fail('FR2', f'{hints_path} not found')
        results['FR2'] = False
    else:
        with open(hints_path, 'r') as f:
            hints_content = f.read()
        match = re.search(r'Key width:\s*(\d+)', hints_content)
        if not match:
            fail('FR2', 'could not determine key width from hints.txt')
            results['FR2'] = False
        else:
            key_width = int(match.group(1))
            if 'key' not in data:
                fail('FR2', 'missing "key" field')
                results['FR2'] = False
            else:
                key_val = data['key']
                if not isinstance(key_val, str):
                    fail('FR2', '"key" field is not a string')
                    results['FR2'] = False
                elif len(key_val) != key_width:
                    fail('FR2', f'key length {len(key_val)} != expected {key_width}')
                    results['FR2'] = False
                elif not all(c in '01' for c in key_val):
                    fail('FR2', 'key contains characters other than 0/1')
                    results['FR2'] = False
                else:
                    results['FR2'] = pass_('FR2')

    # ------------------------------------------------------------------
    # FR3: simulate locked_netlist with submitted key against oracle
    # ------------------------------------------------------------------
    if not results.get('FR2', False):
        fail('FR3', 'cannot check because FR2 failed')
        results['FR3'] = False
    else:
        # Generate a testbench that instantiates locked_netlist and oracle
        # and compares outputs for all 8 input combinations.
        tb_template = """// Auto-generated testbench for FR3
`timescale 1ns/1ps

module tb_check;
    reg a, b, c;
    wire [1:0] key;
    wire locked_out, oracle_out;

    assign key = 2'b{key_val};

    locked_netlist dut (
        .a(a), .b(b), .c(c),
        .key(key),
        .out(locked_out)
    );

    oracle ref (
        .a(a), .b(b), .c(c),
        .out(oracle_out)
    );

    integer i;
    reg [2:0] pattern;
    reg mismatch;

    initial begin
        mismatch = 0;
        for (i = 0; i < 8; i = i + 1) begin
            pattern = i;
            a = pattern[2];
            b = pattern[1];
            c = pattern[0];
            #1;
            if (locked_out !== oracle_out) begin
                $display("[TEST] FAIL: FR3: mismatch at a=%b b=%b c=%b: locked=%b oracle=%b",
                         a, b, c, locked_out, oracle_out);
                mismatch = 1;
            end
        end
        if (!mismatch) begin
            $display("[TEST] PASS: FR3");
        end
        $finish;
    end
endmodule
"""
        tb_content = tb_template.replace('{key_val}', key_val)

        with tempfile.TemporaryDirectory() as tmpdir:
            tb_path = os.path.join(tmpdir, 'tb_check.v')
            with open(tb_path, 'w') as f:
                f.write(tb_content)

            # Copy input files to tmpdir (iverilog works relative to current dir)
            # We'll compile from the project root, so inputs/ files are accessible.
            # Compile command:
            cmd = [
                'iverilog', '-g2012', '-o', os.path.join(tmpdir, 'sim.vvp'),
                os.path.join('inputs', 'locked_netlist.v'),
                os.path.join('inputs', 'oracle.v'),
                tb_path
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            except subprocess.CalledProcessError as e:
                fail('FR3', f'iverilog compile failed: {e.stderr.strip()}')
                results['FR3'] = False
            else:
                # Run simulation
                try:
                    proc = subprocess.run(
                        ['vvp', os.path.join(tmpdir, 'sim.vvp')],
                        capture_output=True, text=True, timeout=30
                    )
                    output = proc.stdout + proc.stderr
                    if '[TEST] PASS: FR3' in output:
                        results['FR3'] = pass_('FR3')
                    elif '[TEST] FAIL: FR3' in output:
                        # Extract the failure line
                        for line in output.splitlines():
                            if '[TEST] FAIL: FR3' in line:
                                fail('FR3', line.split('FR3: ', 1)[-1])
                                break
                        else:
                            fail('FR3', 'simulation output missing expected marker')
                        results['FR3'] = False
                    else:
                        fail('FR3', f'simulation output did not contain expected marker:\n{output}')
                        results['FR3'] = False
                except subprocess.TimeoutExpired:
                    fail('FR3', 'simulation timed out')
                    results['FR3'] = False
                except subprocess.CalledProcessError as e:
                    fail('FR3', f'vvp run failed: {e.stderr.strip()}')
                    results['FR3'] = False

    # ------------------------------------------------------------------
    # SR1: submitted key must exactly match hidden ground truth
    # ------------------------------------------------------------------
    if not results.get('FR2', False):
        fail('SR1', 'cannot check because FR2 failed')
        results['SR1'] = False
    else:
        if key_val == CORRECT_KEY:
            results['SR1'] = pass_('SR1')
        else:
            fail('SR1', f'submitted key "{key_val}" != ground truth')
            results['SR1'] = False

    # ------------------------------------------------------------------
    # SR2: optional feedback_gates field cross-check
    # ------------------------------------------------------------------
    if 'feedback_gates' in data:
        fb_gates = data['feedback_gates']
        if not isinstance(fb_gates, list):
            fail('SR2', '"feedback_gates" field is not an array')
            results['SR2'] = False
        else:
            if set(fb_gates) == set(CORRECT_FEEDBACK_GATES):
                results['SR2'] = pass_('SR2')
            else:
                fail('SR2', f'feedback_gates {fb_gates} != ground truth {CORRECT_FEEDBACK_GATES}')
                results['SR2'] = False
    else:
        # Field is optional; absence is acceptable
        results['SR2'] = pass_('SR2')

    # ------------------------------------------------------------------
    # Final exit code
    # ------------------------------------------------------------------
    if all(results.values()):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()