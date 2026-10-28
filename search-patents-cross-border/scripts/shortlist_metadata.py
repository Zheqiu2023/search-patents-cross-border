"""Deduplicate exported publication rows and emit compact metadata candidates.

This is a high-recall triage aid, not a relevance, family or claims decision.
"""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


FIELDS = {
    "publication_number": ("publication_number", "publication number", "publication", "公开号", "公开公告号"),
    "title": ("title", "标题", "名称", "专利名称"),
    "abstract": ("abstract", "摘要"),
    "classification": ("classification", "ipc", "cpc", "分类号"),
    "applicant": ("applicant", "assignee", "申请人"),
    "priority_date": ("priority_date", "priority date", "优先权日"),
    "source_url": ("source_url", "url", "link", "链接"),
}


def normalize_number(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def compact(row):
    mapped = {key.lower().strip(): (value or "").strip() for key, value in row.items() if key}
    return {name: next((mapped[alias] for alias in aliases if alias in mapped and mapped[alias]), "")
            for name, aliases in FIELDS.items()}


def shortlist(paths, product_terms, structure_terms, applicant_terms):
    records, counts, rejected = {}, Counter(), Counter()
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not any(x.strip().lower() in FIELDS["publication_number"]
                                                 for x in reader.fieldnames):
                raise ValueError(f"{path}: 缺少公开号列，请先规范化导出字段")
            for line, raw in enumerate(reader, 2):
                counts["input_rows"] += 1
                item = compact(raw)
                number = normalize_number(item["publication_number"])
                if not number:
                    rejected[str(path)] += 1
                    continue
                if number in records:
                    counts["duplicate_publications"] += 1
                    for field in FIELDS:
                        if not records[number][field] and item[field]:
                            records[number][field] = item[field]
                    continue
                item["publication_number"] = number
                records[number] = item
    candidates = []
    for item in records.values():
        content = " ".join(item[key] for key in ("title", "abstract", "classification")).casefold()
        product = any(term.casefold() in content for term in product_terms)
        structure = any(term.casefold() in content for term in structure_terms)
        applicant = any(term.casefold() in item["applicant"].casefold() for term in applicant_terms)
        # Do not silently discard sparse or ambiguous records: send them to manual review.
        if (product and structure) or (applicant and (product or structure)):
            item["triage"] = "candidate"
        else:
            item["triage"] = "manual_review"
        item["abstract_truncated"] = len(item["abstract"]) > 500
        item["abstract"] = item["abstract"][:500]
        item["claims_checked"] = False
        candidates.append(item)
        counts[item["triage"]] += 1
    counts["unique_publications"] = len(records)
    return candidates, {**counts, "missing_publication_by_file": dict(rejected),
                        "note": "仅按公开号去重；未验证家族、摘要/著录及独立权利要求；不得据此声明完整覆盖"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True, help="可重复指定已导出的 CSV")
    parser.add_argument("--output", type=Path, required=True, help="精简元数据 JSONL")
    parser.add_argument("--audit", type=Path, required=True, help="仅含计数的 JSON")
    parser.add_argument("--product", action="append", required=True, help="产品词，可重复")
    parser.add_argument("--structure", action="append", required=True, help="机构词，可重复")
    parser.add_argument("--applicant", action="append", default=[], help="目标申请人别名，可重复")
    args = parser.parse_args()
    if args.output.resolve() == args.audit.resolve() or any(
            args.output.resolve() == source.resolve() or args.audit.resolve() == source.resolve()
            for source in args.input):
        parser.error("输出路径不得覆盖原始导出或彼此相同")
    try:
        candidates, audit = shortlist(args.input, args.product, args.structure, args.applicant)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    with args.output.open("w", encoding="utf-8") as handle:
        for item in candidates:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    # Keep terminal output ASCII-safe on Windows runners with legacy console encodings.
    # The saved audit and JSONL above still contain readable UTF-8 text.
    print(json.dumps(audit, ensure_ascii=True))


if __name__ == "__main__":
    main()
