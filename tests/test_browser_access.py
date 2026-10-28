import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


SCRIPTS = Path(__file__).resolve().parents[1] / "search-patents-cross-border" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import browser_diagnostics as diagnostics
import check_and_export as exporter
import epub_search as epub


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
            {"database": "中国专利公布公告站", "query": "四向车", "searched_at": "2026-10-16", "status": "success",
             "pages_viewed": [1], "total_pages": 1, "coverage_complete": True, "terminal_evidence": False}]}
        errors, warnings = exporter.check(data)
        self.assertTrue(any("末页证据" in error for error in errors))
        self.assertFalse(any("未记录中国专利公布公告站" in warning for warning in warnings))

    def test_export_rejects_omitted_terminal_and_unverified_export(self):
        search = {"database": "中国专利公布公告站", "query": "四向车", "searched_at": "2026-10-28",
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


class EpubSearchTests(unittest.TestCase):
    def test_initial_202_can_recover_to_business_form(self):
        page = MagicMock()
        page.url = "http://epub.cnipa.gov.cn/Dxb/AdvancedQuery"
        callbacks = {}
        page.on.side_effect = lambda name, callback: callbacks.__setitem__(name, callback)
        response = lambda status: SimpleNamespace(
            status=status, url=epub.SOURCE, request=SimpleNamespace(resource_type="document"))
        page.goto.side_effect = lambda *a, **k: callbacks["response"](response(202))
        def ready(*a, **k):
            callbacks["response"](response(200))
        page.locator.return_value.wait_for.side_effect = ready
        args = SimpleNamespace(timeout=2, headed=False, type="all", max_pages=1)
        with patch.object(epub, "collect_pages", return_value={"status": "success"}):
            data = epub.collect(page, args, {"title": "四向车", "type": "all"})
        self.assertEqual(data["status"], "success")
        page.locator("#ti").wait_for.assert_called()

    def test_first_page_survives_next_page_timeout(self):
        page = MagicMock()
        current, next_page = MagicMock(), MagicMock()
        current.count.return_value = 0
        next_page.count.return_value = 1
        next_page.get_attribute.return_value = "next_page"
        page.locator.side_effect = lambda selector: current if "current_page" in selector else next_page
        page.wait_for_function.side_effect = TimeoutError("page did not advance")
        row = {"publication_number": "CN122897143A", "claims_checked": False}
        with patch.object(epub, "inspect_result", return_value=([row], 3, False)):
            data = epub.collect_pages(page, SimpleNamespace(max_pages=3, timeout=2), {"title": "四向车"})
        self.assertEqual(data["records"], [row])
        self.assertEqual(data["pages_viewed"], [1])
        self.assertEqual(data["total_pages"], 3)
        self.assertEqual(data["status"], "partial")
        self.assertEqual(data["coverage_reason"], "search_interrupted")
        self.assertEqual(data["error_code"], "page_did_not_advance")
        self.assertFalse(data["terminal_evidence"])

    def test_first_page_survives_unexpected_browser_error(self):
        page = MagicMock()
        current = MagicMock()
        current.count.return_value = 0
        def locate(selector):
            if "current_page" in selector:
                return current
            raise RuntimeError("disconnected while locating next page")
        page.locator.side_effect = locate
        row = {"publication_number": "CN122897143A", "claims_checked": False}
        with patch.object(epub, "inspect_result", return_value=([row], 3, False)):
            data = epub.collect_pages(page, SimpleNamespace(max_pages=3, timeout=2), {"title": "四向车"})
        self.assertEqual(data["records"], [row])
        self.assertEqual(data["pages_viewed"], [1])
        self.assertEqual(data["status"], "partial")
        self.assertEqual(data["failure_stage"], "pagination")
        self.assertEqual(data["error_code"], "browser_RuntimeError")

    def test_last_page_needs_terminal_control_evidence(self):
        page = MagicMock()
        current, next_page = MagicMock(), MagicMock()
        current.count.return_value = 1
        current.inner_text.return_value = "1"
        next_page.count.return_value = 1
        next_page.get_attribute.return_value = "next_page"
        page.locator.side_effect = lambda selector: current if "current_page" in selector else next_page
        row = {"publication_number": "CN122897143A", "claims_checked": False}
        with patch.object(epub, "inspect_result", return_value=([row], 1, False)):
            data = epub.collect_pages(page, SimpleNamespace(max_pages=3, timeout=2), {"title": "四向车"})
            self.assertEqual(data["coverage_reason"], "missing_terminal_evidence")
            self.assertFalse(data["coverage_complete"])
            next_page.get_attribute.return_value = "next_page btn_dis"
            data = epub.collect_pages(page, SimpleNamespace(max_pages=3, timeout=2), {"title": "四向车"})
        self.assertTrue(data["terminal_evidence"])
        self.assertTrue(data["coverage_complete"])

    def test_cdp_reuses_context_and_cleanup_cannot_erase_partial_records(self):
        from playwright import sync_api
        playwright_manager = MagicMock()
        playwright = playwright_manager.__enter__.return_value
        browser = playwright.chromium.connect_over_cdp.return_value
        page = browser.contexts[0].new_page.return_value
        page.close.side_effect = RuntimeError("browser disconnected")
        partial = {"status": "partial", "records": [{"publication_number": "CN122897143A"}]}
        args = SimpleNamespace(cdp_url="http://127.0.0.1:9222", timeout=2)
        with patch.object(sync_api, "sync_playwright", return_value=playwright_manager):
            with patch.object(epub, "query_values", return_value={"title": "四向车"}):
                with patch.object(epub, "collect", return_value=partial):
                    self.assertEqual(epub.run(args), partial)
        playwright.chromium.connect_over_cdp.assert_called_once()
        browser.close.assert_not_called()

    def test_zero_results_do_not_invent_page_one(self):
        data = epub.summarize({"applicant": ["Movu"]}, [], [], 0, zero=True)
        self.assertEqual(data["pages_viewed"], [])
        self.assertEqual(data["coverage_reason"], "zero_results")
        self.assertTrue(data["coverage_complete"])

    def test_partial_page_keeps_publication_and_unread_page_count(self):
        data = epub.summarize({"title": "四向车"}, [
            {"publication_number": "CN122897143A", "claims_checked": False}], [1], 48)
        self.assertEqual(data["pages_viewed"], [1])
        self.assertEqual(data["total_pages"], 48)
        self.assertEqual(data["coverage_reason"], "page_limit")
        self.assertFalse(data["records"][0]["claims_checked"])

    def test_unknown_total_never_claims_complete(self):
        data = epub.summarize({"publication-number": "CN122897143A"}, [
            {"publication_number": "CN122897143A"}], [1], None)
        self.assertEqual(data["status"], "partial")
        self.assertEqual(data["coverage_reason"], "total_pages_unconfirmed")

    def test_official_cards_and_confirmed_zero_are_distinct_from_empty_shell(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            channel = os.environ.get("PATENT_TEST_BROWSER", "chrome")
            browser = (playwright.chromium.launch() if channel == "chromium"
                       else playwright.chromium.launch(channel=channel))
            try:
                page = browser.new_page()
                page.set_content('''<div class="overview-default"><div class="item">
                <h1 class="title">[发明公布] 一种低压轨道重载型四向车及其轨道</h1>
                <div class="info"><dl><dt>申请公布号：</dt><dd>CN122897143A</dd></dl>
                <dl><dt>申请人：</dt><dd>江苏易飞迅物流科技有限公司</dd></dl>
                <dl><dt>发明人：</dt><dd>吴洋;蔡程民;张琼</dd></dl></div>
                <div class="intro"><dl><dt>摘要：</dt><dd>升降机构和四个丝杆升降器</dd></dl></div>
                </div></div><span class="page_total">共 48 页, 到第</span>''')
                rows, total, zero = epub.inspect_result(page)
                self.assertEqual((total, zero), (48, False))
                self.assertEqual(rows[0]["publication_number"], "CN122897143A")
                self.assertEqual(rows[0]["applicant"], "江苏易飞迅物流科技有限公司")
                self.assertIn("/patent/CN122897143A", rows[0]["source_url"])
                page.set_content("<div>抱歉，没有您要查询的结果！</div>")
                self.assertEqual(epub.inspect_result(page), ([], 0, True))
                page.set_content("<body></body>")
                with self.assertRaises(epub.SearchFailure):
                    epub.inspect_result(page)
            finally:
                browser.close()

    def test_browser_entry_failure_reports_unavailable_without_fake_hits(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "search.json"
            with patch.object(epub, "run", side_effect=epub.SearchFailure("entry", "form_missing_or_interaction_required", 202)):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    status = epub.main(["--title", "四向车", "--output", str(output)])
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(status, 1)
            self.assertEqual(data["status"], "unavailable")
            self.assertEqual(data["records"], [])
            self.assertEqual(data["http_status"], 202)


if __name__ == "__main__":
    unittest.main()
