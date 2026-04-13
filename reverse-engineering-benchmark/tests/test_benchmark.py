import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gatelift_bench.evaluator import BenchmarkEvaluator
from gatelift_bench.metrics import score_sia, score_sma, score_wrr
from gatelift_bench.models import EvalConfig
from gatelift_bench.parser import extract_llm_artifacts


class ParserTests(unittest.TestCase):
    def test_extracts_first_verilog_block(self):
        text = """summary text\n```verilog\nmodule a; endmodule\n```\nother\n```verilog\nmodule b; endmodule\n```"""
        result = extract_llm_artifacts(text)
        self.assertIn("module a", result.verilog)
        self.assertIn("Multiple Verilog blocks", " ".join(result.parse_notes))


class MetricTests(unittest.TestCase):
    def test_wrr_perfect_for_matching_buses(self):
        gt = "module m(input [7:0] a, output [7:0] y); assign y=a; endmodule"
        cand = "module m(input [7:0] a, output [7:0] y); assign y=a; endmodule"
        self.assertEqual(score_wrr(gt, cand).score, 1.0)

    def test_sma_drop_for_wrong_operator(self):
        gt = "module m(input [7:0] a,b, output [7:0] y); assign y = a + b; endmodule"
        cand = "module m(input [7:0] a,b, output [7:0] y); assign y = a ^ b; endmodule"
        self.assertLess(score_sma(gt, cand).score, 1.0)

    def test_sia_keyword_coverage(self):
        result = score_sia(
            "This is an 8-bit combinational adder.",
            "An 8-bit combinational adder.",
            ["8-bit", "adder", "combinational"],
        )
        self.assertGreaterEqual(result.score, 0.85)


class EndToEndTests(unittest.TestCase):
    def test_evaluate_all_generates_report(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            results = Path(td) / "report.json"
            cfg = EvalConfig(
                examples_dir=str(repo_root / "examples"),
                submissions_dir=str(repo_root / "submissions"),
                results_path=str(results),
                use_formal=False,
            )
            payload = BenchmarkEvaluator(cfg).evaluate_all()
            self.assertEqual(payload["num_cases"], 3)
            self.assertTrue(results.exists())
            loaded = json.loads(results.read_text())
            self.assertIn("aggregate_score", loaded)
            self.assertIn("results", loaded)

    def test_generator_script_help(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "tools" / "generate_case_from_rtl.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Generate GateLift-Bench case", proc.stdout)


if __name__ == "__main__":
    unittest.main()
