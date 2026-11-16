# Cross-border patent search skill / 跨库专利检索技能

An [Agent Skills](https://agentskills.io/specification) folder for searching published patents in Chinese and international sources, screening claims, and reporting patent families with source links. The instructions are in Chinese; an agent that can follow Chinese Markdown can use them. This repository includes only the reusable skill and its tests.

这是按 Agent Skills 格式编写的中文技能，用于检索已公开的国内外专利、复核权利要求并按专利族整理有来源的报告。下载后无需安装其他专利检索技能；部分操作依赖浏览器、网站访问权限和可选 Python 依赖。

## Install / 安装

1. Download or clone this repository.
2. Copy the **whole** `search-patents-cross-border/` folder into the skills directory documented by your agent. Keep `SKILL.md`, `references/` and `scripts/` together. Restart/reload the agent if it does not discover newly installed skills automatically.
3. Ask the agent in Chinese: `使用 search-patents-cross-border 技能检索某项技术的相关专利，列明申请人、独立权利要求证据与来源。`

Different agents choose different discovery directories and tools. If an agent does not support Agent Skills discovery, give it the local path to `search-patents-cross-border/SKILL.md` and ask it to read and follow that file and its relative references. This **manual mode** requires file-reading and web/browser access; the format cannot make every agent automatically install or execute a skill.

安装：将整个 `search-patents-cross-border` 目录放到当前 agent **文档指定的技能目录**，保持相对目录结构。如果 agent 不识别技能目录，直接让其读取该目录下的 `SKILL.md`，并按其中相对路径读取参考文件；能否执行网页检索取决于 agent 的联网与浏览器能力。

## Sources and browser access / 检索来源与浏览器要求

The default Chinese official source is the **CNIPA Patent Search and Analysis System**. Google Patents and WIPO PATENTSCOPE provide international search and document checks. The skill guides the agent's browser tools; it does not include a batch search adapter for these sites.

中国官方来源已更换为**国家知识产权局专利检索及分析系统**。请使用可见、可由用户操作且可由 agent 接管的浏览器，按 [国家知识产权局检索流程](search-patents-cross-border/references/cnipa-pss.md)执行：

1. 打开 `https://pss-system.cponline.cnipa.gov.cn/conventionalSearch`，检查当前登录状态。
2. 未登录时，由用户本人完成登录、短信和验证码；登录成功后，agent 在同一浏览器会话中继续检索。
3. 选择“自动识别”或“发明名称”等字段，输入检索词，点击输入框右侧带搜索图标的 `div.btn`，避免误点顶部的“检索”导航。
4. 提交后检查新建或复用的 `/retrieveList` 结果页，等待“检索结果”和 `N 条数据`出现，再记录查询、命中数和首条公开号。
5. 记录实际读取的页码，分别核验摘要、主权利要求、著录项目和同族。只读部分页面时标记“部分覆盖”。

Users complete authentication themselves in the visible browser. The skill contains reusable instructions, not account credentials or browser session data. An existing valid session may be reused. If the entry, result page, or a document is unavailable, record that specific failure and continue with accessible sources; an unread result page is not evidence of zero hits.

登录状态由浏览器与网站管理，**不保存在 skill 中，也不会随技能一起分发**。遇到空白页、HTTP 400 或安全防护提示，应按流程有限重试并记录失败阶段。浏览器或登录不可用时，应说明国家知识产权局检索系统未覆盖，并继续可访问的其他来源。Google Patents 和 PATENTSCOPE 同样通过正常网页操作。

如 agent 需要本地 Playwright，可选安装 `requirements-browser.txt` 中的依赖，并使用本机 Chrome/Edge 或执行 `python -m playwright install chromium` 准备 Chromium。这只是浏览器环境准备，不能替代 agent 的浏览器接入与用户登录。

## Data tools / 数据整理与导出

Python 3 is needed only when running the bundled data tools. Metadata screening and CSV export use the standard library; XLSX export additionally requires `openpyxl` (`python -m pip install openpyxl`). Run from the repository root:

```bash
python search-patents-cross-border/scripts/shortlist_metadata.py --help
python search-patents-cross-border/scripts/check_and_export.py --help
```

`shortlist_metadata.py` 对已有 CSV 导出按公开号去重，保留候选和待人工复核项；`check_and_export.py` 检查报告字段、来源日志、覆盖证据及专利族信息，并支持 CSV/XLSX 导出。JSON 格式见 [数据格式](search-patents-cross-border/references/data-format.md)。On Windows, use `python -X utf8` if the console cannot display Chinese.

元数据初筛结果需要继续核验公开文本、同族和独立权利要求；导出检查通过也不代表已完成全部检索或全文复筛。

## Test / 测试

```bash
python -m unittest discover -s tests -p 'test*.py' -v
```

These are offline logic tests for the retained diagnostics, coverage checks, exports, and metadata screening; they do not require a browser or prove live access to patent sites. Validate the Agent Skills metadata with `python -m pip install skills-ref` followed by `agentskills validate ./search-patents-cross-border`. The bundled GitHub Actions workflow checks the format and offline tests on Windows and Linux.

2026-11-16 的实际浏览器验证已确认：用户登录后可提交检索、读取结果数量与首条公开号，并切换名称检索字段。该验证不代表全量分页、批量下载或全部权利要求复筛已经完成，也不保证其他浏览器会话或其他 agent 的访问结果；命中数量以每次检索页面为准。详细步骤见 [已验证的最小流程](search-patents-cross-border/references/cnipa-pss.md#7-已验证的最小流程)。

## Publication scope / 发布范围

This repository intentionally omits local research reports, patent PDFs, browser logs, account data, cookies, and exported search results. The source and documentation are distributed under the MIT license; see `LICENSE` in the repository root or the skill folder. Offline tests do not establish that live patent databases will accept every browser session.
