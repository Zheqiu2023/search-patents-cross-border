"""Safe, shared browser observations and conservative coverage verification."""

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


def safe_url(url):
    """Drop credentials, query strings and fragments from diagnostic URLs."""
    try:
        parts = urlsplit(str(url))
        if parts.scheme not in ("http", "https"):
            return ""
        host = parts.hostname or ""
        if parts.port:
            host += f":{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, "", ""))
    except ValueError:
        return ""


def classify(http_status=None, error_code=None, interaction=None, ready=False):
    if error_code:
        if "TIMED_OUT" in error_code:
            return "connection_timeout"
        if "ERR_" in error_code:
            return "connection_error"
        return "page_not_ready_or_locator_mismatch"
    if http_status is not None and http_status >= 400:
        return "http_error"
    if interaction in ("disclaimer", "login", "captcha"):
        return "interaction_required"
    return "ready" if ready else "page_not_ready_or_locator_mismatch"


def observe(page, database, stage, diagnostics, response=None, error=None,
            interaction=None, ready=False):
    # Do not retain exception text, headers, network bodies or page HTML.
    code = None
    if error:
        match = re.search(r"(?:net::)?ERR_[A-Z_]+", str(error))
        code = match.group(0) if match else type(error).__name__
    try:
        title = "认证页面" if interaction else page.title()[:160]
    except Exception:
        title = ""
    status = response.status if response is not None else None
    if status is None and page is not None:
        try:
            status = page.evaluate("() => performance.getEntriesByType('navigation')[0]?.responseStatus || null")
        except Exception:
            pass
    entry = {"database": database, "observed_at": datetime.now(timezone.utc).isoformat(),
             "stage": stage, "final_url": safe_url(page.url) if page is not None else "", "http_status": status,
             "error_code": code, "page_title": title, "interaction": interaction,
             "target_present": ready,
             "category": classify(status, code, interaction, ready),
             "attempt": 1 + sum(item["stage"] == stage for item in diagnostics)}
    if error and code and "ERR_" not in code and stage in ("extraction", "pagination"):
        entry["category"] = "extraction_error" if stage == "extraction" else "coverage_unconfirmed"
    entry["next_action"] = ("manual_interaction" if interaction else
                            "continue" if ready else "inspect_or_stop")
    diagnostics.append(entry)
    return entry


def verify_coverage(pages, hits, terminal_evidence):
    """A missing next button is never terminal evidence."""
    numbers = [item["page"] for item in pages]
    if not terminal_evidence:
        return False, "missing_terminal_evidence"
    if numbers != list(range(1, len(pages) + 1)):
        return False, "non_contiguous_pages"
    rows = [row for item in pages for row in item["rows"]]
    keys = [row.get("publication_number") for row in rows]
    if not all(keys):
        return False, "missing_publication_number"
    if len(set(keys)) != len(keys):
        return False, "duplicate_publications"
    if hits is None or hits != len(rows):
        return False, "unknown_or_mismatched_hit_count"
    return True, "zero_results" if hits == 0 else "terminal_and_count_verified"
