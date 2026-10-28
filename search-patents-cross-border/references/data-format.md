# 复筛数据及自动检查格式

每条检索日志可新增 diagnostics（按 diagnostics.md）、failure_stage、coverage_reason、terminal_evidence。diagnostics仅证明访问观察，不充当结果列表或权利要求证据。公布公告站辅助脚本输出的 coverage_complete 已单独表示列表覆盖；记录仍属著录候选，不能把其摘要当成已核验权利要求。转成 searches 记录时保留页码、计数、覆盖原因及安全诊断。
把检索笔记保存为 UTF-8 JSON，满足下例结构。`scripts/check_and_export.py` 检查关键字段、重复家族、检索日志和前 10 项特征证据；可导出 CSV 或 XLSX 供人工复核。脚本只检查结构和内部一致性，**不能代替逐篇阅读文献或证实来源真实**。

```json
{
  "required_features": ["横向运行", "纵向运行"],
  "searches": [
    {
      "database": "中国专利公布公告站",
      "query": "四向穿梭车",
      "searched_at": "2026-09-30",
      "status": "success",
      "batch_id": "epub-2026-09-30-01",
      "coverage_complete": false,
      "records_collected": 20,
      "hits": 120,
      "pages_viewed": [1, 2],
      "total_pages": 12
    }
  ],
  "families": [
    {
      "family_id": "family-1",
      "publication_number": "CN123456789A",
      "title": "示例专利名称",
      "applicant": "示例申请人",
      "inventors": ["张三"],
      "earliest_priority_date": "2022-01-01",
      "summary_cn": "对原文技术内容的简明中文概述。",
      "source_urls": ["https://patents.google.com/patent/CN123456789A/zh"],
      "claims_checked": true,
      "feature_evidence": [
        {
          "feature": "横向运行",
          "match": "yes",
          "claim_number": "1",
          "evidence": "独立权利要求1记载横向行走轮组",
          "source_url": "https://patents.google.com/patent/CN123456789A/zh"
        },
        {"feature": "纵向运行", "match": "no", "evidence": "权利要求1未记载纵向运行"}
      ]
    }
  ]
}
```

`status` 使用 `success`、`partial`、`unavailable`；`match` 使用 `yes`、`no`、`uncertain`。`family_id` 应使用已核实的专利族标识；无法确定同族时给该申请单独的临时 ID 并在报告注明，避免误合并。`pages_viewed` 为实际读过的页码，`total_pages` 不确定时填 `null`。前 10 项的每个必要特征都要有一条证据；匹配为 `yes` 时必须填写具体权利要求号、证据及公开文本链接。序号与 `families` 顺序相同，不要把未经权利要求复核的文献混入前 50 项。

Google Patents 与 PATENTSCOPE 按 [coverage.md](coverage.md) 拆成批次；每个批次独立写一条 `searches` 记录，`batch_id` 不重复，并记录检索集合、日期边界、字段、排序、结果链接、页码、实际提取数与失败阶段。`coverage_complete: true` 仅在页码覆盖 1 至 `total_pages` 且无跳页，或完整导出经人工核对时填写；后者另写 `export_complete: true`、`export_verified: true`、`records_collected` 及报告内可复核的导出证据。`check_and_export.py` 只能审查记录自洽，**不能证明网站确实返回了完整结果或日期拆批没有空白**。旧记录未填 `coverage_complete` 会收到警告，不可据此声称覆盖完成。

完整覆盖还必须有明确的 `terminal_evidence: true`，或同时提供 `export_complete: true`、`export_verified: true` 和非负 `records_collected`；未填写末页证据视为缺失，而不是默认通过。`coverage_reason=search_interrupted`、`missing_terminal_evidence` 等失败原因与完整覆盖声明矛盾，也会被拒绝。零结果时也要记录本次查询的正式零结果页作为末页证据。该检查仍无法独立证明网站真实性，应保留实际页面或导出核验记录。

运行：

```powershell
python -X utf8 scripts/check_and_export.py --input .\research.json --csv .\results.csv
python -X utf8 scripts/check_and_export.py --input .\research.json --xlsx .\results.xlsx
```

导出 CSV 使用 Python 标准库；XLSX 需要 `openpyxl`。先修复错误再生成文件；警告（例如未读完全部分页）应原样写进报告。不要在公开交付物中放账号、Cookie 或 API 密钥。
