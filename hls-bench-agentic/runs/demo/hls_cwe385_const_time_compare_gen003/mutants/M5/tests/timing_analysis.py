#!/usr/bin/env python3
import sys
import re
def parse_cycles(log_file):
    try:
        with open(log_file, 'r') as f:
            content = f.read()
        cycle_match = re.search(r'Total cycles:\s*(\d+)', content)
        if cycle_match:
            return int(cycle_match.group(1))
        cycle_match = re.search(r'Simulation cycles:\s*(\d+)', content)
        if cycle_match:
            return int(cycle_match.group(1))
        cycle_match = re.search(r'(\d+)\s*cycles', content)
        if cycle_match:
            return int(cycle_match.group(1))
        return None
    except Exception as e:
        print(f'[ERROR] Failed to parse {log_file}: {e}')
        return None
def main():
    if len(sys.argv) < 2:
        print('[FAIL] SR1: No log files provided')
        sys.exit(1)
    log_files = sys.argv[1:]
    cycles = []
    for log_file in log_files:
        cycle_count = parse_cycles(log_file)
        if cycle_count is None:
            print(f'[WARN] Could not extract cycle count from {log_file}')
            continue
        cycles.append((log_file, cycle_count))
        print(f'[INFO] {log_file}: {cycle_count} cycles')
    if len(cycles) < 2:
        print('[FAIL] SR1: Insufficient timing data for comparison')
        sys.exit(1)
    reference_cycles = cycles[0][1]
    all_equal = True
    for log_file, cycle_count in cycles[1:]:
        if cycle_count != reference_cycles:
            print(f'[FAIL] SR1: Timing variation detected: {cycles[0][0]} has {reference_cycles} cycles, {log_file} has {cycle_count} cycles')
            all_equal = False
    if all_equal:
        print(f'[PASS] SR1: All test cases completed in {reference_cycles} cycles')
        sys.exit(0)
    else:
        sys.exit(1)
if __name__ == '__main__':
    main()
