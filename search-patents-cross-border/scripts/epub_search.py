"""Search CNIPA's published/announced bibliographic records in a browser.

Only Playwright and Python's standard library are used. A result is a bibliographic
candidate; the site's result page does not establish patent families or claims.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


DATABASE = "中国专利公布公告站"
SOURCE = "http://epub.cnipa.gov.cn/Advanced"
FIELDS = {"title": "ti", "abstract": "abs", "class": "e51",
          "publication-number": "pn", "application-number": "an",
          "inventor": "e72", "applicant": "e71_73"}
TYPE_CHECKBOXES = {
    "all": ("isFmgb", "isFmsq", "isXx", "isWg"),
    "invention": ("isFmgb", "isFmsq"),
    "utility_model": ("isXx",), "design": ("isWg",),
}

# Read visible bibliographic values from each official result card. Hidden expanded
# fields are intentionally excluded; they are not evidence that claims were read.
EXTRACT_ROWS = """() => [...document.querySelectorAll('.overview-default > .item')].map(card => {
  const field = label => {
    const dl = [...card.querySelectorAll('dl')].find(d =>
      d.querySelector(':scope > dt')?.textContent.trim().replace(/[：:]/g, '') === label);
    const dd = dl?.querySelector(':scope > dd');
    if (!dd) return null;
    const copy = dd.cloneNode(true);
    copy.querySelectorAll('.allinfo, .open, .point').forEach(x => x.remove());
    copy.querySelectorAll('.alltxt').forEach(x => x.style.display = '');
    return copy.textContent.replace(/\\s+/g, ' ').trim() || null;
  };
  const number = field('申请公布号') || field('授权公告号') ||
                 field('公布公告号') || field('公告号');
  return {publication_number:number, application_number:field('申请号'),
    title:card.querySelector('h1.title')?.textContent.trim().replace(/^\\[[^\\]]+\\]\\s*/, '') || null,
    applicant:field('申请人') || field('专利权人'),
    inventors:field('发明人') || field('设计人'),
    application_date:field('申请日'),
    publication_date:field('申请公布日') || field('授权公告日') || field('公告日'),
    abstract:field('摘要') || field('简要说明'),
    source_url:number && /^CN[0-9A-Z]+$/i.test(number)
      ? 'http://epub.cnipa.gov.cn/patent/' + number : null,
    claims_checked:false};
})"""


class SearchFailure(Exception):
    def __init__(self, stage, code, http_status=None, initial_http_status=None):
        super().__init__(code)
        self.stage, self.code = stage, code
        self.http_status, self.initial_http_status = http_status, initial_http_status


def inspect_result(page):
    """Require either real result cards or an explicit zero-result notice."""
    rows = page.evaluate(EXTRACT_ROWS)
    summary = page.locator(".page_total").all_text_contents()
    match = re.search(r"共\s*(\d+)\s*页", " ".join(summary))
    total = int(match.group(1)) if match else None
    body = page.locator("body").inner_text(timeout=10000)
    zero = bool(re.search(r"(暂无(相关)?(数据|结果)|未查询到|没有(查询到|检索到|找到|您要查询的结果)|查询结果为\s*0\s*条)", body))
    if not rows and not zero:
        raise SearchFailure("results", "result_cards_or_zero_notice_missing")
    if rows and any(not row["publication_number"] or not row["source_url"] for row in rows):
        raise SearchFailure("results", "publication_number_missing")
    return rows, 0 if zero and not rows else total, zero and not rows


def query_values(args):
    fields = {"title": args.title or args.query, "abstract": args.abstract,
              "class": args.class_code, "publication-number": args.publication_number,
              "application-number": args.application_number,
              "inventor": args.inventor, "applicant": args.applicant}
    if not any(fields.values()):
        raise ValueError("至少填写一个著录检索字段")
    return {**{key: value for key, value in fields.items() if value}, "type": args.type}


def summarize(query, records, pages, total, zero=False, failure=None, terminal=False):
    complete = failure is None and total is not None and (
        total == 0 and zero or total > 0 and terminal and pages == list(range(1, total + 1)))
    reason = ("zero_results" if zero else "terminal_and_count_verified") if complete else (
        "search_interrupted" if failure else "total_pages_unconfirmed" if total is None
        else "page_limit" if len(pages) < total else "missing_terminal_evidence" if not terminal
        else "page_count_mismatch")
    result = {
        "database": DATABASE, "source": SOURCE, "query": query,
        "searched_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "success" if complete else "partial",
        "coverage_complete": complete, "coverage_reason": reason,
        "total_pages": total, "pages_viewed": pages, "pages_scanned": 1 if zero else len(pages),
        "records_collected": len(records), "terminal_evidence": complete,
        "first_publication": records[0]["publication_number"] if records else None,
        "last_publication": records[-1]["publication_number"] if records else None,
        "records": records, "claims_checked": False,
    }
    if failure:
        result.update(failure_stage=failure.stage, error_code=failure.code)
    return result


def collect(page, args, query):
    statuses = []
    def record_response(response):
        if urlsplit(response.url).path == "/Advanced" and response.request.resource_type == "document":
            statuses.append(response.status)

    page.on("response", record_response)
    try:
        page.goto(SOURCE, wait_until="domcontentloaded", timeout=args.timeout * 1000)
    except Exception as exc:
        raise SearchFailure("entry", "navigation_failed", statuses[-1] if statuses else None,
                            statuses[0] if statuses else None) from exc
    try:
        # A transient 202 can navigate to either the real form or an HTTP error.
        # Wait for the business element instead of deciding from the first response.
        page.locator("#ti").wait_for(state="visible", timeout=args.timeout * 1000)
    except Exception as exc:
        try:
            body = page.locator("body").inner_text(timeout=5000)
        except Exception:
            body = ""
        if (args.headed or args.cdp_url) and re.search(r"登录|验证码|人机验证|身份验证", body):
            print("请在当前可见浏览器完成网站要求的交互，脚本等待查询表单。", file=sys.stderr)
            try:
                page.locator("#ti").wait_for(state="visible", timeout=180000)
            except Exception as wait_exc:
                raise SearchFailure("entry", "interaction_required", statuses[-1] if statuses else None,
                                    statuses[0] if statuses else None) from wait_exc
        else:
            final = statuses[-1] if statuses else None
            raise SearchFailure("entry", "http_error" if final and final >= 400 else "form_missing_or_interaction_required",
                                final, statuses[0] if statuses else None) from exc
    for field, selector in FIELDS.items():
        value = query.get(field)
        if value:
            page.locator("#" + selector).fill(" ".join(value) if isinstance(value, list) else value)
    selected = TYPE_CHECKBOXES[args.type]
    for checkbox in TYPE_CHECKBOXES["all"]:
        page.locator("#" + checkbox).set_checked(checkbox in selected)
    try:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=args.timeout * 1000):
            page.get_by_role("button", name="查询", exact=True).click()
    except Exception as exc:
        raise SearchFailure("submit", "navigation_failed") from exc
    if not page.url.startswith("http://epub.cnipa.gov.cn/Dxb/"):
        raise SearchFailure("submit", "unexpected_results_url")
    try:
        page.locator(".overview-default > .item, .page_total, .no-data, .empty").first.wait_for(timeout=12000)
    except Exception:
        pass  # inspect_result distinguishes a confirmed zero from an empty shell.

    return collect_pages(page, args, query)


def collect_pages(page, args, query):
    seen, pages = set(), []
    records = []
    total = None
    terminal = False
    try:
        rows, total, zero = inspect_result(page)
        if zero:
            return summarize(query, [], [], 0, zero=True)
        while True:
            page_number = len(pages) + 1
            if not rows:
                raise SearchFailure("pagination", "empty_page_without_zero_notice")
            current = page.locator(".page_ctrl .current_page")
            if total is not None and current.count() and current.inner_text().strip() != str(page_number):
                raise SearchFailure("pagination", "page_number_mismatch")
            publications = [row["publication_number"] for row in rows]
            if len(publications) != len(set(publications)) or seen.intersection(publications):
                raise SearchFailure("pagination", "duplicate_publication_or_page")
            seen.update(publications)
            records.extend(rows)
            pages.append(page_number)
            if total is not None and len(pages) == total:
                next_page = page.locator(".page_ctrl .next_page")
                terminal = next_page.count() == 0 or "btn_dis" in (next_page.get_attribute("class") or "")
                break
            if len(pages) >= args.max_pages:
                break
            next_page = page.locator(".page_ctrl .next_page")
            if next_page.count() == 0 or "btn_dis" in (next_page.get_attribute("class") or ""):
                if total is not None and len(pages) < total:
                    raise SearchFailure("pagination", "next_page_unavailable")
                break
            first = publications[0]
            next_page.click()
            try:
                page.wait_for_function(
                    "n => document.querySelector('.overview-default > .item .info dd')?.textContent.trim() !== n",
                    arg=first, timeout=min(args.timeout * 1000, 20000))
            except Exception as exc:
                raise SearchFailure("pagination", "page_did_not_advance") from exc
            rows, new_total, new_zero = inspect_result(page)
            if new_zero or (new_total is not None and total is not None and new_total != total):
                raise SearchFailure("pagination", "result_count_changed")
            if total is None:
                total = new_total
    except Exception as exc:
        if not pages:
            raise
        failure = (exc if isinstance(exc, SearchFailure) else
                   SearchFailure("pagination", "browser_" + type(exc).__name__))
        return summarize(query, records, pages, total, failure=failure)
    return summarize(query, records, pages, total, zero, terminal=terminal)


def run(args):
    query = query_values(args)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SearchFailure("browser_setup", "playwright_not_installed") from exc
    try:
        with sync_playwright() as playwright:
            attached = bool(args.cdp_url)
            browser = (playwright.chromium.connect_over_cdp(args.cdp_url, timeout=args.timeout * 1000)
                       if attached else playwright.chromium.launch(channel=args.channel, headless=not args.headed))
            try:
                if attached:
                    if not browser.contexts:
                        raise SearchFailure("browser_setup", "existing_browser_context_missing")
                    page = browser.contexts[0].new_page()
                else:
                    page = browser.new_page()
                try:
                    return collect(page, args, query)
                finally:
                    # A lost browser connection must not erase already collected pages.
                    try:
                        page.close()
                    except Exception:
                        pass
            finally:
                if not attached:
                    try:
                        browser.close()
                    except Exception:
                        pass
    except SearchFailure:
        raise
    except Exception as exc:
        raise SearchFailure("browser_setup", type(exc).__name__) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", default="")
    parser.add_argument("--query", default="", help="名称字段别名")
    parser.add_argument("--abstract", default="")
    parser.add_argument("--class", dest="class_code", default="")
    parser.add_argument("--publication-number", default="")
    parser.add_argument("--application-number", default="")
    parser.add_argument("--inventor", default="")
    parser.add_argument("--applicant", action="append", default=[])
    parser.add_argument("--type", choices=tuple(TYPE_CHECKBOXES), default="all")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--headed", action="store_true", help="使用可见 Chrome；需用户手动处理站点交互")
    parser.add_argument("--channel", choices=("chrome", "msedge", "chromium"), default="chrome")
    parser.add_argument("--cdp-url", default="", help="连接已经由用户打开的本机 Chrome 调试端口，复用其可见会话")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=40)
    args = parser.parse_args(argv)
    if args.max_pages < 1 or args.timeout < 1:
        parser.error("--max-pages 和 --timeout 必须大于零")
    if args.cdp_url:
        endpoint = urlsplit(args.cdp_url)
        if endpoint.scheme != "http" or endpoint.hostname not in ("localhost", "127.0.0.1", "::1") or endpoint.username or endpoint.password:
            parser.error("--cdp-url 仅接受无凭据的本机 HTTP 调试地址")
        if args.headed:
            parser.error("--cdp-url 已复用可见浏览器，不必同时指定 --headed")
    try:
        data = run(args)
    except (SearchFailure, ValueError) as exc:
        stage = exc.stage if isinstance(exc, SearchFailure) else "query"
        code = exc.code if isinstance(exc, SearchFailure) else "empty_query"
        data = {"database": DATABASE, "source": SOURCE,
                "query": {"title": args.title or args.query, "abstract": args.abstract,
                          "class": args.class_code, "publication-number": args.publication_number,
                          "application-number": args.application_number, "inventor": args.inventor,
                          "applicant": args.applicant, "type": args.type},
                "searched_at": datetime.now(timezone.utc).astimezone().isoformat(),
                "status": "unavailable", "coverage_complete": False,
                "coverage_reason": "search_unavailable", "total_pages": None,
                "pages_viewed": [], "records_collected": 0, "records": [],
                "failure_stage": stage, "error_code": code, "claims_checked": False}
        if isinstance(exc, SearchFailure) and exc.http_status:
            data["http_status"] = exc.http_status
        if isinstance(exc, SearchFailure) and exc.initial_http_status:
            data["initial_http_status"] = exc.initial_http_status
        print(f"公布公告站检索未完成：{stage} / {code}", file=sys.stderr)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存 {len(data['records'])} 条公布公告候选到 {args.output}")
    return 0 if data["status"] == "success" else 3 if data["status"] == "partial" else 1


if __name__ == "__main__":
    raise SystemExit(main())
