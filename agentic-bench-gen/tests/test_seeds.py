from collections import Counter
from pathlib import Path

import yaml

from agentic_bench_gen.orchestrator import _validate_seed_rows


def test_all_example_seed_files_are_valid():
    root = Path(__file__).resolve().parents[1]
    for path in sorted((root / "examples").glob("*seeds*.yaml")):
        rows = yaml.safe_load(path.read_text(encoding="utf-8"))
        _validate_seed_rows(rows)


def test_multi_domain_seed_sets_have_expected_domain_balance():
    root = Path(__file__).resolve().parents[1]
    expected = {
        "multi_domain_seeds_expanded.yaml": 3,
    }
    for filename, per_domain in expected.items():
        path = root / "examples" / filename
        rows = _validate_seed_rows(yaml.safe_load(path.read_text(encoding="utf-8")))
        counts = Counter(row["domain_id"] for row in rows)
        assert len(counts) == 6
        if per_domain is not None:
            assert set(counts.values()) == {per_domain}


def test_set4_has_five_non_hls_domains_and_new_ids():
    root = Path(__file__).resolve().parents[1]
    examples = root / "examples"
    set4_path = examples / "multi_domain_seeds_set4.yaml"
    set4 = _validate_seed_rows(yaml.safe_load(set4_path.read_text(encoding="utf-8")))
    counts = Counter(row["domain_id"] for row in set4)
    assert counts == {
        "rtl_trojan_detection": 5,
        "gate_trojan_detection": 5,
        "hardware_reverse_engineering": 5,
        "side_channel_fault_analysis": 5,
        "logic_deobfuscation_sat": 5,
    }

    prior_ids = set()
    for path in examples.glob("*.yaml"):
        if path == set4_path:
            continue
        rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        prior_ids.update(str(row.get("seed_id", "")) for row in rows if isinstance(row, dict))
    assert not ({row["seed_id"] for row in set4} & prior_ids)
