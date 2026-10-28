"""Check traceability of a patent-family shortlist and optionally export it."""

import argparse
import csv
import json
import sys
from pathlib import Path


COLUMNS = ("family_id", "publication_number", "title", "applicant", "inventors",
           "earliest_priority_date", "summary_cn", "source_urls", "claims_checked",
           "feature_evidence")


def check(data):
    errors, warnings = [], []
    searches, families = data.get("searches"), data.get("families")
    features = data.get("required_features")
    if not isinstance(searches, list) or not searches:
        errors.append("缺少检索日志 searches")
    else:
        recorded = {str(entry.get("database", "")).lower() for entry in searches if isinstance(entry, dict)}
        if not any("公布公告" in name or "epub" in name for name in recorded):
            warnings.append("未记录中国专利公布公告站尝试或未覆盖原因")
        batch_ids = set()
        for i, entry in enumerate(searches, 1):
            if not isinstance(entry, dict) or any(not entry.get(k) for k in ("database", "query", "searched_at", "status")):
                errors.append(f"检索日志 {i} 缺少数据库、检索式、日期或状态")
                continue
            if entry["status"] not in ("success", "partial", "unavailable"):
                errors.append(f"检索日志 {i} 状态不合法")
            total, viewed = entry.get("total_pages"), entry.get("pages_viewed", [])
            batch_id = entry.get("batch_id")
            if batch_id:
                if batch_id in batch_ids:
                    errors.append(f"检索日志 {i} 重复 batch_id: {batch_id}")
                batch_ids.add(batch_id)
            if not isinstance(viewed, list) or any(type(page) is not int or page < 1 for page in viewed):
                errors.append(f"检索日志 {i} 页码须为正整数列表")
                viewed = []
            elif len(viewed) != len(set(viewed)):
                errors.append(f"检索日志 {i} 页码重复，需核实是否重复抓取")
            if total is not None and (type(total) is not int or total < 0):
                errors.append(f"检索日志 {i} 总页数不合法")
            elif type(total) is int and len(set(viewed)) < total:
                warnings.append(f"检索日志 {i} 已查看 {len(set(viewed))}/{total} 页，报告需披露未覆盖页")
            if type(total) is int and any(page > total for page in viewed):
                errors.append(f"检索日志 {i} 页码超过总页数")
            complete = entry.get("coverage_complete")
            if complete is not None and type(complete) is not bool:
                errors.append(f"检索日志 {i} coverage_complete 须为布尔值")
            if complete is True:
                export_evidence = (entry.get("export_complete") is True and
                                   entry.get("export_verified") is True and
                                   type(entry.get("records_collected")) is int and
                                   entry["records_collected"] >= 0)
                if entry.get("terminal_evidence") is not True and not export_evidence:
                    errors.append(f"检索日志 {i} 缺少明确末页证据或经核对的完整导出，却声称完整覆盖")
                if entry.get("coverage_reason") in ("missing_terminal_evidence", "unknown_or_mismatched_hit_count",
                                                    "duplicate_publications", "non_contiguous_pages", "page_limit",
                                                    "zero_query_unconfirmed", "interrupted", "search_interrupted",
                                                    "total_pages_unconfirmed", "page_count_mismatch"):
                    errors.append(f"检索日志 {i} 覆盖原因与完整声明矛盾")
                if entry["status"] != "success":
                    errors.append(f"检索日志 {i} 未成功却声称完整覆盖")
                if total is None or set(viewed) != set(range(1, total + 1)):
                    if not export_evidence:
                        errors.append(f"检索日志 {i} 缺少连续全页或经核对的完整导出证据")
            elif complete is False:
                warnings.append(f"检索日志 {i} 未完成结果列表覆盖")
            elif complete is None:
                warnings.append(f"检索日志 {i} 未声明 coverage_complete，不能证明完整遍历")
    if not isinstance(features, list) or not features or any(not isinstance(x, str) or not x.strip() for x in features):
        errors.append("缺少必要技术特征 required_features")
        features = []
    if not isinstance(families, list):
        errors.append("families 必须是列表")
        families = []
    if len(families) > 50:
        errors.append("入选专利族超过 50 项")
    seen_families, seen_pubs = set(), set()
    for i, family in enumerate(families, 1):
        if not isinstance(family, dict):
            errors.append(f"第 {i} 项不是对象")
            continue
        for key in ("family_id", "publication_number", "title", "applicant", "summary_cn"):
            if not family.get(key):
                errors.append(f"第 {i} 项缺少 {key}")
        if not isinstance(family.get("inventors"), list) or not family["inventors"]:
            errors.append(f"第 {i} 项缺少发明人列表")
        if not isinstance(family.get("source_urls"), list) or not family["source_urls"]:
            errors.append(f"第 {i} 项缺少原文来源链接")
        elif any(not isinstance(url, str) or not url.startswith(("https://", "http://"))
                 for url in family["source_urls"]):
            errors.append(f"第 {i} 项原文来源链接不合法")
        if family.get("claims_checked") is not True:
            errors.append(f"第 {i} 项未核验权利要求")
        for key, seen in (("family_id", seen_families), ("publication_number", seen_pubs)):
            value = str(family.get(key, "")).strip().upper()
            if value and value in seen:
                errors.append(f"第 {i} 项重复 {key}: {value}")
            seen.add(value)
        if i <= 10:
            evidence = family.get("feature_evidence", [])
            if not isinstance(evidence, list):
                evidence = []
            for feature in features:
                rows = [row for row in evidence if isinstance(row, dict) and row.get("feature") == feature]
                if len(rows) != 1:
                    errors.append(f"第 {i} 项的技术特征“{feature}”需要唯一证据记录")
                    continue
                row = rows[0]
                if row.get("match") not in ("yes", "no", "uncertain") or not row.get("evidence"):
                    errors.append(f"第 {i} 项的技术特征“{feature}”缺少判断或说明")
                if row.get("match") == "yes" and (not row.get("claim_number") or not row.get("source_url")):
                    errors.append(f"第 {i} 项的技术特征“{feature}”匹配但缺少权利要求号或来源")
                elif row.get("match") == "yes" and not str(row["source_url"]).startswith(("https://", "http://")):
                    errors.append(f"第 {i} 项的技术特征“{feature}”证据来源链接不合法")
    return errors, warnings


def rows_for_export(families):
    for family in families:
        values = dict(family)
        for key in ("inventors", "source_urls"):
            values[key] = "; ".join(values.get(key, []))
        values["feature_evidence"] = " | ".join(
            f"{item.get('feature', '')}: {item.get('match', '')}; 权利要求{item.get('claim_number', '未确认')}; "
            f"{item.get('evidence', '')}; {item.get('source_url', '')}"
            for item in family.get("feature_evidence", []) if isinstance(item, dict))
        # Spreadsheet viewers may execute formulas in untrusted cell text.
        yield {key: "'" + str(value) if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
               else value for key in COLUMNS for value in [values.get(key, "")]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--xlsx", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON 根节点必须是对象")
        errors, warnings = check(data)
    except (OSError, ValueError, TypeError) as exc:
        print(f"读取或解析失败: {exc}", file=sys.stderr)
        return 2
    for message in warnings:
        print(f"警告: {message}", file=sys.stderr)
    for message in errors:
        print(f"错误: {message}", file=sys.stderr)
    if errors:
        return 1
    if args.xlsx:
        try:
            from openpyxl import Workbook
        except ImportError:
            print("导出 XLSX 需要 openpyxl", file=sys.stderr)
            return 2
    items = list(rows_for_export(data["families"]))
    if args.csv:
        with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(items)
    if args.xlsx:
        book = Workbook()
        sheet = book.active
        sheet.title = "专利族"
        sheet.append(COLUMNS)
        for item in items:
            sheet.append([item[key] for key in COLUMNS])
        book.save(args.xlsx)
    print(f"检查通过：{len(items)} 个专利族；{len(warnings)} 条覆盖提醒")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
