#!/usr/bin/env python3
"""
evaluate.py -- Gate-level trojan detection report grader.

Grades submission/trojan_report.json against structural ground truth
derived from inputs/netlist.v. See evaluation/README.md for the
participant-facing schema description.
"""

import json
import os
import re
import sys

INPUTS_DIR = "inputs"
SUBMISSION_DIR = "submission"

NETLIST_PATH = os.path.join(INPUTS_DIR, "netlist.v")
DESIGN_BRIEF_PATH = os.path.join(INPUTS_DIR, "design_brief.md")
CELL_LIB_PATH = os.path.join(INPUTS_DIR, "cell_library.v")
SUBMISSION_PATH = os.path.join(SUBMISSION_DIR, "trojan_report.json")

RESULTS = []  # list of (req_id, passed_bool, message)


def record(req_id, passed, message):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, message))
    RESULTS.append((req_id, passed, message))


def fail_all_setup(req_ids, reason):
    for rid in req_ids:
        record(rid, False, reason)


ALL_REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]


def main():
    # ---------------------------------------------------------------
    # Load and structurally parse inputs/netlist.v
    # ---------------------------------------------------------------
    if not os.path.isfile(NETLIST_PATH):
        fail_all_setup(ALL_REQ_IDS, "SETUP: {} not found".format(NETLIST_PATH))
        sys.exit(1)

    with open(NETLIST_PATH, "r") as f:
        netlist_text = f.read()

    # Strip line comments and block comments to simplify parsing.
    text_no_comments = re.sub(r'//.*', '', netlist_text)
    text_no_comments = re.sub(r'/\*.*?\*/', '', text_no_comments, flags=re.DOTALL)

    # ------------------------------------------------------------
    # Extract module instantiations of the form:
    #   <celltype> <instname> ( .port(expr), .port2(expr2), ... );
    # We look for identifier identifier ( ... ) ; patterns, excluding
    # keywords like module/endmodule/input/output/wire/reg/assign etc.
    # ------------------------------------------------------------
    KEYWORDS = {
        "module", "endmodule", "input", "output", "inout", "wire", "reg",
        "logic", "assign", "always", "begin", "end", "posedge", "negedge",
        "if", "else", "parameter", "localparam", "function", "endfunction",
        "generate", "endgenerate", "case", "endcase", "initial"
    }

    # Find all instantiation blocks: celltype instname ( .a(b), .c(d) );
    inst_pattern = re.compile(
        r'(?P<celltype>\w+)\s+(?P<instname>u_\w+)\s*\((?P<ports>.*?)\)\s*;',
        re.DOTALL
    )

    instances = {}  # instname -> {"celltype":..., "ports": {portname: expr}}
    for m in inst_pattern.finditer(text_no_comments):
        celltype = m.group("celltype")
        instname = m.group("instname")
        if celltype in KEYWORDS:
            continue
        ports_str = m.group("ports")
        # Extract .portname(expr) pairs
        port_pairs = re.findall(r'\.(\w+)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)', ports_str)
        port_map = {}
        for pname, pexpr in port_pairs:
            port_map[pname] = pexpr.strip()
        instances[instname] = {"celltype": celltype, "ports": port_map}

    all_instance_names = set(instances.keys())

    if not all_instance_names:
        fail_all_setup(ALL_REQ_IDS, "SETUP: no instances parsed from {}".format(NETLIST_PATH))
        sys.exit(1)

    # ------------------------------------------------------------
    # Discover output port names per celltype by structurally parsing
    # inputs/cell_library.v (not hardcoded from memory).
    # ------------------------------------------------------------
    output_port_by_celltype = {}
    if os.path.isfile(CELL_LIB_PATH):
        with open(CELL_LIB_PATH, "r") as f:
            cell_lib_text = f.read()
        cell_lib_nc = re.sub(r'//.*', '', cell_lib_text)
        cell_lib_nc = re.sub(r'/\*.*?\*/', '', cell_lib_nc, flags=re.DOTALL)
        mod_pattern = re.compile(
            r'module\s+(\w+)\s*\((.*?)\);(.*?)endmodule',
            re.DOTALL
        )
        for mm in mod_pattern.finditer(cell_lib_nc):
            modname = mm.group(1)
            header = mm.group(2)
            body = mm.group(3)
            full_decl_area = header + "\n" + body
            out_ports = re.findall(
                r'output\s+(?:wire\s+|reg\s+|logic\s+)?(?:\[\d+:\d+\]\s+)?(\w+)',
                full_decl_area
            )
            if out_ports:
                output_port_by_celltype[modname] = out_ports[0]

    def output_port_of(celltype):
        return output_port_by_celltype.get(celltype, None)

    # For each instance, compute its input-port expressions (all ports
    # except the discovered output port for its celltype).
    instance_input_exprs = {}
    for instname, info in instances.items():
        celltype = info["celltype"]
        ports = info["ports"]
        out_port = output_port_of(celltype)
        input_exprs = []
        for pname, pexpr in ports.items():
            if out_port is not None and pname == out_port:
                continue
            input_exprs.append(pexpr)
        instance_input_exprs[instname] = input_exprs

    def refs_bit(expr, bit):
        pattern = r'key_reg\s*\[\s*{}\s*\]'.format(bit)
        return re.search(pattern, expr) is not None

    # Build direct consumers of key_reg[i] for each bit: any instance
    # whose input expression directly references key_reg[i].
    direct_consumers = {i: set() for i in range(8)}
    for instname, input_exprs in instance_input_exprs.items():
        for i in range(8):
            for expr in input_exprs:
                if refs_bit(expr, i):
                    direct_consumers[i].add(instname)
                    break

    # ------------------------------------------------------------
    # Build a net-driven-by map (which instance's output port drives
    # a given net expression), so we can trace one additional hop:
    # if instance X directly consumes key_reg[i] and X's own output
    # feeds a net (e.g. shadow_reg[i]) that is consumed elsewhere
    # (directly, or via a bus-wide `assign` aggregation), those
    # downstream consumers are also part of key_reg[i]'s fanout tree.
    # ------------------------------------------------------------
    assign_pattern = re.compile(r'assign\s+(\w+)\s*=\s*([^;]+);')
    assigns = {}
    for am in assign_pattern.finditer(text_no_comments):
        lhs = am.group(1).strip()
        rhs = am.group(2).strip()
        assigns[lhs] = rhs

    def expr_depends_on_bus(expr, busname):
        return re.search(r'\b{}\b'.format(re.escape(busname)), expr) is not None

    # fanout[i] starts as the direct consumers, then we extend it by
    # tracing forward through each direct consumer's own output net,
    # following both direct net-name matches and bus-wide `assign`
    # aggregations (e.g. exfil_bit = |shadow_reg;) into any further
    # instance that consumes the resulting net -- recursively, until
    # no new instances are discovered (bounded fixed-point, handles
    # arbitrary chain depth without needing full symbolic simulation).
    fanout = {i: set(direct_consumers[i]) for i in range(8)}

    for i in range(8):
        frontier = set(direct_consumers[i])
        visited_insts = set(direct_consumers[i])
        while frontier:
            new_frontier = set()
            for src_inst in frontier:
                celltype = instances[src_inst]["celltype"]
                out_port = output_port_of(celltype)
                if out_port is None:
                    continue
                driven_net_expr = instances[src_inst]["ports"].get(out_port, "").strip()
                if not driven_net_expr:
                    continue
                bit_match = re.match(r'(\w+)\s*\[\s*\d+\s*\]', driven_net_expr)
                busname = bit_match.group(1) if bit_match else driven_net_expr

                # 1) Any instance directly consuming this exact net expression.
                for other_inst, input_exprs in instance_input_exprs.items():
                    if other_inst == src_inst:
                        continue
                    already = other_inst in fanout[i]
                    for expr in input_exprs:
                        if re.search(r'\b{}\b'.format(re.escape(driven_net_expr)), expr):
                            if other_inst not in fanout[i]:
                                fanout[i].add(other_inst)
                            if other_inst not in visited_insts:
                                new_frontier.add(other_inst)
                            break

                # 2) Any assign statement whose RHS depends on the bus
                #    this net belongs to, then any instance consuming
                #    the assign's LHS net.
                for lhs, rhs in assigns.items():
                    if expr_depends_on_bus(rhs, busname):
                        for other_inst, input_exprs in instance_input_exprs.items():
                            for expr in input_exprs:
                                if re.search(r'\b{}\b'.format(re.escape(lhs)), expr):
                                    if other_inst not in fanout[i]:
                                        fanout[i].add(other_inst)
                                    if other_inst not in visited_insts:
                                        new_frontier.add(other_inst)
                                    break
            new_frontier -= visited_insts
            visited_insts |= new_frontier
            frontier = new_frontier

    # ------------------------------------------------------------
    # Ground-truth suspect / legitimate sets, derived structurally.
    # Legitimate documented path per design_brief.md: key_reg[i] -> u_round_xor<i>
    # Everything else touching key_reg[i] (transitively) is undocumented/suspect.
    # ------------------------------------------------------------
    documented_consumer_by_bit = {}
    for i in range(8):
        candidate = "u_round_xor{}".format(i)
        if candidate in all_instance_names:
            documented_consumer_by_bit[i] = candidate

    suspect_ground_truth = set()
    for i in range(8):
        for inst in fanout[i]:
            if inst != documented_consumer_by_bit.get(i):
                suspect_ground_truth.add(inst)

    legitimate_instances = set()
    for i in range(8):
        key_ff_candidate = "u_key_ff{}".format(i)
        if key_ff_candidate in all_instance_names:
            legitimate_instances.add(key_ff_candidate)
        if i in documented_consumer_by_bit:
            legitimate_instances.add(documented_consumer_by_bit[i])

    # Ensure suspect set and legitimate set are disjoint (defensive).
    suspect_ground_truth -= legitimate_instances

    # ------------------------------------------------------------
    # Load submission
    # ------------------------------------------------------------
    if not os.path.isfile(SUBMISSION_PATH):
        fail_all_setup(ALL_REQ_IDS, "SETUP: {} not found".format(SUBMISSION_PATH))
        sys.exit(1)

    try:
        with open(SUBMISSION_PATH, "r") as f:
            raw_text = f.read()
        report = json.loads(raw_text)
    except Exception as e:
        fail_all_setup(ALL_REQ_IDS, "invalid JSON: {}".format(e))
        sys.exit(1)

    # ------------------------------------------------------------
    # FR1: top-level schema presence & types
    # ------------------------------------------------------------
    required_fields = {
        "verdict": str,
        "key_bus_signal": str,
        "fanout_map": list,
        "suspect_instances": list,
        "summary": str,
    }
    fr1_ok = True
    fr1_reason = ""
    if not isinstance(report, dict):
        fr1_ok = False
        fr1_reason = "top-level JSON is not an object"
    else:
        for field, ftype in required_fields.items():
            if field not in report:
                fr1_ok = False
                fr1_reason = "missing required field '{}'".format(field)
                break
            if not isinstance(report[field], ftype):
                fr1_ok = False
                fr1_reason = "field '{}' has wrong type (expected {})".format(
                    field, ftype.__name__
                )
                break
    record("FR1", fr1_ok, fr1_reason)

    # If FR1 failed badly enough that later checks can't proceed safely,
    # we still attempt them defensively with .get() fallbacks.
    fanout_map = report.get("fanout_map", []) if isinstance(report, dict) else []
    suspect_instances_raw = report.get("suspect_instances", []) if isinstance(report, dict) else []
    verdict = report.get("verdict", None) if isinstance(report, dict) else None

    # ------------------------------------------------------------
    # FR2: fanout_map structure - exactly 8 entries, key_bit 0..7 each once,
    # consumer_instances list of str, num_consumers == len(consumer_instances)
    # ------------------------------------------------------------
    fr2_ok = True
    fr2_reason = ""
    entry_by_bit = {}
    if not isinstance(fanout_map, list):
        fr2_ok = False
        fr2_reason = "fanout_map is not a list"
    else:
        if len(fanout_map) != 8:
            fr2_ok = False
            fr2_reason = "fanout_map has {} entries, expected 8".format(len(fanout_map))
        else:
            seen_bits = set()
            for idx, entry in enumerate(fanout_map):
                if not isinstance(entry, dict):
                    fr2_ok = False
                    fr2_reason = "fanout_map[{}] is not an object".format(idx)
                    break
                if "key_bit" not in entry or "consumer_instances" not in entry or "num_consumers" not in entry:
                    fr2_ok = False
                    fr2_reason = "fanout_map[{}] missing required keys".format(idx)
                    break
                kb = entry["key_bit"]
                ci = entry["consumer_instances"]
                nc = entry["num_consumers"]
                if not isinstance(kb, int) or not (0 <= kb <= 7):
                    fr2_ok = False
                    fr2_reason = "fanout_map[{}] key_bit invalid: {}".format(idx, kb)
                    break
                if kb in seen_bits:
                    fr2_ok = False
                    fr2_reason = "duplicate key_bit {} in fanout_map".format(kb)
                    break
                seen_bits.add(kb)
                if not isinstance(ci, list) or not all(isinstance(x, str) for x in ci):
                    fr2_ok = False
                    fr2_reason = "fanout_map[{}] consumer_instances is not a list of strings".format(idx)
                    break
                if not isinstance(nc, int) or nc != len(ci):
                    fr2_ok = False
                    fr2_reason = "fanout_map[{}] num_consumers ({}) != len(consumer_instances) ({})".format(
                        idx, nc, len(ci)
                    )
                    break
                entry_by_bit[kb] = entry
            if fr2_ok and len(seen_bits) != 8:
                fr2_ok = False
                fr2_reason = "fanout_map does not cover all key_bit values 0-7"
    record("FR2", fr2_ok, fr2_reason)

    # ------------------------------------------------------------
    # FR3: every named instance in fanout_map/suspect_instances exists
    # literally in inputs/netlist.v
    # ------------------------------------------------------------
    fr3_ok = True
    fr3_reason = ""
    offending = None
    if isinstance(fanout_map, list):
        for entry in fanout_map:
            if isinstance(entry, dict) and isinstance(entry.get("consumer_instances"), list):
                for name in entry["consumer_instances"]:
                    if isinstance(name, str) and name not in all_instance_names:
                        offending = name
                        break
            if offending:
                break
    if offending is None and isinstance(suspect_instances_raw, list):
        for name in suspect_instances_raw:
            if isinstance(name, str) and name not in all_instance_names:
                offending = name
                break
    if offending is not None:
        fr3_ok = False
        fr3_reason = "instance name '{}' does not exist in inputs/netlist.v".format(offending)
    record("FR3", fr3_ok, fr3_reason)

    # ------------------------------------------------------------
    # FR4: verdict field is exactly 'trojan_present' or 'trojan_absent'
    # ------------------------------------------------------------
    fr4_ok = verdict in ("trojan_present", "trojan_absent")
    fr4_reason = "" if fr4_ok else "verdict field is '{}', expected 'trojan_present' or 'trojan_absent'".format(verdict)
    record("FR4", fr4_ok, fr4_reason)

    # ------------------------------------------------------------
    # SR1: each key_bit's fanout must include both the documented XOR
    # consumer and the undocumented shadow FF consumer (num_consumers==2,
    # matching ground truth derived from netlist.v). We only require the
    # DIRECT consumers here (u_round_xor<i> and u_shadow_ff<i>); the
    # transitive convergence instance (u_exfil_mux) is graded separately
    # under SR2 since it is not a direct consumer of any single key bit.
    # ------------------------------------------------------------
    sr1_ok = True
    sr1_reason = ""
    for i in range(8):
        gt_direct_consumers = direct_consumers[i]  # direct ground-truth consumers of bit i
        entry = entry_by_bit.get(i)
        if entry is None:
            sr1_ok = False
            sr1_reason = "no fanout_map entry for key_bit {}".format(i)
            break
        submitted_consumers = set(entry.get("consumer_instances", []))
        num_consumers = entry.get("num_consumers", None)
        if not gt_direct_consumers.issubset(submitted_consumers):
            missing = gt_direct_consumers - submitted_consumers
            sr1_ok = False
            sr1_reason = "key_bit {} missing ground-truth consumer(s) {}".format(i, sorted(missing))
            break
        if num_consumers is None or num_consumers < len(gt_direct_consumers):
            sr1_ok = False
            sr1_reason = "key_bit {} reports num_consumers={} (expected at least {}, single-consumer topology detected)".format(
                i, num_consumers, len(gt_direct_consumers)
            )
            break
    record("SR1", sr1_ok, sr1_reason)

    # ------------------------------------------------------------
    # SR2: suspect_instances must be a superset of the ground-truth
    # suspect set (recall == 1.0).
    # ------------------------------------------------------------
    submitted_suspects = set(x for x in suspect_instances_raw if isinstance(x, str))
    missing_suspects = suspect_ground_truth - submitted_suspects
    sr2_ok = len(missing_suspects) == 0 and len(suspect_ground_truth) > 0
    if len(suspect_ground_truth) == 0:
        sr2_reason = "internal error: could not derive ground-truth suspect set from netlist.v"
    elif missing_suspects:
        sr2_reason = "suspect_instances missing required entries: {}".format(sorted(missing_suspects))
    else:
        sr2_reason = ""
    record("SR2", sr2_ok, sr2_reason)

    # ------------------------------------------------------------
    # SR3: verdict must be exactly 'trojan_present'
    # ------------------------------------------------------------
    sr3_ok = verdict == "trojan_present"
    sr3_reason = "" if sr3_ok else "verdict is '{}', expected 'trojan_present'".format(verdict)
    record("SR3", sr3_ok, sr3_reason)

    # ------------------------------------------------------------
    # SR4: false-positive rate over suspect_instances must not exceed
    # threshold. Only count entries that are real netlist instances.
    # ------------------------------------------------------------
    valid_submitted_suspects = submitted_suspects & all_instance_names
    if len(valid_submitted_suspects) == 0:
        sr4_ok = False
        sr4_reason = "suspect_instances is empty or contains no valid netlist instances"
    else:
        fp_count = len(valid_submitted_suspects & legitimate_instances)
        fp_rate = fp_count / len(valid_submitted_suspects)
        threshold = 0.15
        sr4_ok = fp_rate <= threshold
        sr4_reason = "" if sr4_ok else (
            "false-positive rate {:.3f} exceeds threshold {:.2f} "
            "({} of {} flagged instances are legitimate documented instances)".format(
                fp_rate, threshold, fp_count, len(valid_submitted_suspects)
            )
        )
    record("SR4", sr4_ok, sr4_reason)

    # ------------------------------------------------------------
    # Final verdict
    # ------------------------------------------------------------
    all_passed = all(passed for _, passed, _ in RESULTS)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()