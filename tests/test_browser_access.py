import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "search-patents-cross-border" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import browser_diagnostics as diagnostics
import check_and_export as exporter


class DiagnosticTests(unittest.TestCase):
    def test_url_strips_authentication_and_session(self):
        self.assertEqual(diagnostics.safe_url("https://user:secret@example.org/view?token=secret#cookie"),
                         "https://example.org/view")

    def test_classify_distinguishes_http_connection_and_dom(self):
        self.assertEqual(diagnostics.classify(503), "http_error")
        self.assertEqual(diagnostics.classify(error_code="net::ERR_CONNECTION_TIMED_OUT"), "connection_timeout")
        self.assertEqual(diagnostics.classify(error_code="TimeoutError"), "page_not_ready_or_locator_mismatch")
        for interaction in ("disclaimer", "login", "captcha"):
            self.assertEqual(diagnostics.classify(interaction=interaction), "interaction_required")

    def test_coverage_rejects_duplicate_skip_unknown_count_and_missing_terminal(self):
        row = {"publication_number": "CN123A"}
        one = [{"page": 1, "rows": [row]}]
        self.assertTrue(diagnostics.verify_coverage(one, 1, True)[0])
        self.assertFalse(diagnostics.verify_coverage(one, 1, False)[0])
        self.assertFalse(diagnostics.verify_coverage(one, None, True)[0])
        self.assertFalse(diagnostics.verify_coverage(one, 2, True)[0])
        self.assertFalse(diagnostics.verify_coverage(one + [{"page": 3, "rows": [row]}], 2, True)[0])
        self.assertFalse(diagnostics.verify_coverage(one + [{"page": 2, "rows": [row]}], 2, True)[0])
        self.assertTrue(diagnostics.verify_coverage([], 0, True)[0])

    def test_export_rejects_false_terminal_claim(self):
        data = {"required_features": ["顶升"], "families": [], "searches": [
            {"database": "国家知识产权局专利检索及分析系统", "query": "提升机", "searched_at": "2026-11-16", "status": "success",
             "pages_viewed": [1], "total_pages": 1, "coverage_complete": True, "terminal_evidence": False}]}
        errors, warnings = exporter.check(data)
        self.assertTrue(any("末页证据" in error for error in errors))
        self.assertFalse(any("未记录国家知识产权局" in warning for warning in warnings))

    def test_export_rejects_omitted_terminal_and_unverified_export(self):
        search = {"database": "国家知识产权局专利检索及分析系统", "query": "提升机", "searched_at": "2026-11-16",
                  "status": "success", "pages_viewed": [1], "total_pages": 1, "coverage_complete": True}
        data = {"required_features": ["顶升"], "families": [], "searches": [search]}
        self.assertTrue(any("末页证据" in e for e in exporter.check(data)[0]))
        search.update(export_complete=True, export_verified=False, records_collected=1)
        self.assertTrue(any("末页证据" in e for e in exporter.check(data)[0]))
        search["terminal_evidence"] = True
        self.assertEqual(exporter.check(data)[0], [])
        search.update(terminal_evidence=False, export_verified=True)
        self.assertEqual(exporter.check(data)[0], [])
        search.update(terminal_evidence=True, coverage_reason="search_interrupted")
        self.assertTrue(any("覆盖原因" in e for e in exporter.check(data)[0]))

    def test_official_source_is_required_and_distinct_from_google_patents(self):
        search = {"query": "lift", "searched_at": "2026-11-16", "status": "unavailable",
                  "pages_viewed": [], "coverage_complete": False}
        data = {"required_features": ["lifting"], "families": [], "searches": [search]}
        for name in ("国家知识产权局专利检索及分析系统", "CNIPA", "PSS"):
            with self.subTest(database=name):
                search["database"] = name
                self.assertFalse(any("未记录国家知识产权局" in w for w in exporter.check(data)[1]))
        search["database"] = "Google Patents"
        self.assertTrue(any("未记录国家知识产权局" in w for w in exporter.check(data)[1]))


if __name__ == "__main__":
    unittest.main()
