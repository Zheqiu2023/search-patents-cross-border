import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "search-patents-cross-border" / "scripts" / "shortlist_metadata.py"
spec = importlib.util.spec_from_file_location("shortlist_metadata", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ShortlistTests(unittest.TestCase):
    def test_dedup_keeps_ambiguous_and_missing_number_count(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "input.csv"
            with source.open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=["公开号", "标题", "摘要", "申请人"])
                writer.writeheader()
                writer.writerows([
                    {"公开号": "CN 123 A", "标题": "四向穿梭车", "摘要": "顶升换向", "申请人": "甲"},
                    {"公开号": "CN123A", "标题": "", "摘要": "", "申请人": "甲"},
                    {"公开号": "US999B2", "标题": "Unknown", "摘要": "", "申请人": "乙"},
                    {"公开号": "", "标题": "Missing", "摘要": "", "申请人": "甲"},
                ])
            rows, audit = module.shortlist([source], ["四向穿梭车"], ["顶升"], [])
            self.assertEqual([row["triage"] for row in rows], ["candidate", "manual_review"])
            self.assertEqual(audit["input_rows"], 4)
            self.assertEqual(audit["duplicate_publications"], 1)
            self.assertEqual(audit["missing_publication_by_file"][str(source)], 1)
            self.assertTrue(all(row["claims_checked"] is False for row in rows))

    def test_cli_rejects_overwriting_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "input.csv"
            source.write_text("publication_number,title\nCN123A,shuttle\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source),
                                     "--output", str(source), "--audit", str(Path(folder) / "audit.json"),
                                     "--product", "shuttle", "--structure", "wheel"],
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CN123A", source.read_text(encoding="utf-8"))

    def test_truncated_abstract_only_in_compact_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "input.csv"
            with source.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["publication_number", "title", "abstract"])
                writer.writeheader()
                writer.writerow({"publication_number": "US2A", "title": "shuttle", "abstract": "wheel " * 130})
            rows, _ = module.shortlist([source], ["shuttle"], ["wheel"], [])
            self.assertEqual(len(rows[0]["abstract"]), 500)
            self.assertTrue(rows[0]["abstract_truncated"])
            self.assertIn("wheel " * 130, source.read_text(encoding="utf-8"))

    def test_cli_writes_audit_and_jsonl(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source, output, audit = base / "input.csv", base / "triage.jsonl", base / "audit.json"
            source.write_text("publication_number,title,abstract\nUS2A,shuttle,wheel lifting\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source),
                                     "--output", str(output), "--audit", str(audit),
                                     "--product", "shuttle", "--structure", "wheel"],
                                    capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(audit.read_text(encoding="utf-8"))["candidate"], 1)
            self.assertFalse(json.loads(output.read_text(encoding="utf-8"))["claims_checked"])


if __name__ == "__main__":
    unittest.main()
