# Cross-border patent search skill / 跨库专利检索技能

An [Agent Skills](https://agentskills.io/specification) folder for searching published patents in Chinese and international sources, screening claims, and reporting patent families with source links. The instructions are in Chinese; an agent that can follow Chinese Markdown can use them. This repository includes only the reusable skill and its tests.

这是按 Agent Skills 格式编写的中文技能，用于检索已公开的国内外专利、复核权利要求并按专利族整理有来源的报告。下载后无需安装其他专利检索技能；部分操作依赖浏览器、网站访问权限和可选 Python 依赖。

## Install / 安装

1. Download or clone this repository.
2. Copy the **whole** `search-patents-cross-border/` folder into the skills directory documented by your agent. Keep `SKILL.md`, `references/` and `scripts/` together. Restart/reload the agent if it does not discover newly installed skills automatically.
3. Ask the agent in Chinese: `使用 search-patents-cross-border 技能检索某项技术的相关专利，列明申请人、独立权利要求证据与来源。`

Different agents choose different discovery directories and tools. If an agent does not support Agent Skills discovery, give it the local path to `search-patents-cross-border/SKILL.md` and ask it to read and follow that file and its relative references. This **manual mode** requires file-reading and web/browser access; the format cannot make every agent automatically install or execute a skill.

安装：将整个 `search-patents-cross-border` 目录放到当前 agent **文档指定的技能目录**，保持相对目录结构。如果 agent 不识别技能目录，直接让其读取该目录下的 `SKILL.md`，并按其中相对路径读取参考文件；能否执行网页检索取决于 agent 的联网与浏览器能力。

## Optional browser helper / 可选浏览器辅助脚本

The skill can guide an agent's existing browser tools. Its CNIPA helper additionally requires Python 3 and Playwright with a locally available Chrome/Edge/Chromium browser. Run from the repository root:

```bash
python -m pip install -r requirements-browser.txt
python search-patents-cross-border/scripts/epub_search.py --publication-number CN122897143A --max-pages 1 --output epub-results.json
```

On systems without an installed Chrome/Edge channel, install the Playwright Chromium browser with `python -m playwright install chromium` and pass `--channel chromium`. On Windows, `python -X utf8` helps with console encoding. XLSX export through `scripts/check_and_export.py` additionally requires `openpyxl` (`python -m pip install openpyxl`); CSV output and metadata screening use Python's standard library.

新建浏览器访问公布公告站时可能先返回 HTTP 202，最终变成 HTTP 400；脚本会写明失败阶段，**不能保证下载即可自动取得该网站的检索结果**。如果已有用户可见、可控的浏览器会话，可以按 [官方检索流程](search-patents-cross-border/references/epub.md)操作；已有本机 CDP 调试端口时可选 `--cdp-url`。验证码和登录仅由用户本人在可见会话完成。Google Patents 与 PATENTSCOPE 目前依赖 agent 的浏览器操作流程，没有内置批量抓取脚本。浏览器无法访问时，应披露缺口，不能把没有读到结果写成零命中。

辅助脚本输出的是**著录候选**，不是已核验的专利族或权利要求。请按技能说明查看公开文本并逐条复筛。

## Test / 测试

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python -m unittest discover -s tests -p 'test*.py' -v
```

These are offline logic tests; they do not prove live access to patent sites. Validate the Agent Skills metadata with `python -m pip install skills-ref` followed by `agentskills validate ./search-patents-cross-border`. The bundled GitHub Actions workflow checks the format and offline tests on Windows and Linux.

## Publication scope / 发布范围

This repository intentionally omits local research reports, patent PDFs, browser logs, account data, cookies, and exported search results. The source and documentation are distributed under the MIT license; see `LICENSE` in the repository root or the skill folder. Offline tests do not establish that live patent databases will accept every browser session.
