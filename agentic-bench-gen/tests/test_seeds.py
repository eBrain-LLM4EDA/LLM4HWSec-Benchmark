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
        "multi_domain_seeds_expanded.yaml": (18, 3),
        "multi_domain_seeds_set3.yaml": (30, 5),
    }
    for filename, (total, per_domain) in expected.items():
        path = root / "examples" / filename
        rows = _validate_seed_rows(yaml.safe_load(path.read_text(encoding="utf-8")))
        assert len(rows) == total
        assert set(Counter(row["domain_id"] for row in rows).values()) == {per_domain}
