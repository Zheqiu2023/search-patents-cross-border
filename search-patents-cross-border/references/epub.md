# 中国专利公布公告站：高级著录检索

入口为 `http://epub.cnipa.gov.cn/Advanced`；以当次网站实际导航和业务元素为准。它覆盖中国**已公开/公告**文献，不代表未公开申请、现行权利人或全球专利族。

## 运行

在本技能目录运行：

```powershell
python -X utf8 scripts/epub_search.py --title "四向车" --max-pages 3 --output ".\epub-results.json"
python -X utf8 scripts/epub_search.py --applicant "某公司" --max-pages 2 --output ".\epub-company.json"
python -X utf8 scripts/epub_search.py --publication-number "CN122897143A" --cdp-url "http://127.0.0.1:9222" --output ".\epub-known.json"
```

脚本直接用本机 Python + Playwright 驱动 Chrome（或 `--channel msedge` 指定 Edge），不依赖其他技能；首次运行应预先安装 Playwright Python 包与浏览器。可加 `--headed` 使用可见浏览器；`--cdp-url` 则连接**用户已打开且启用本机调试端口**的 Chrome，复用同一可见会话与手动完成的网站交互，运行结束不会关闭这台浏览器。只接受无账号密码的本机 HTTP 地址；不从其他进程复制 Cookie，不自动处理验证码。需提前用单独的浏览器用户数据目录开启调试端口，不要对日常浏览器的默认目录直接启用远程调试。无需预先进入统一认证页。输出含 `database`、`query`、`status`、`pages_viewed`、`total_pages`、`coverage_complete`、`records`，方便汇入 `data-format.md` 的 `searches`；`records` 是**著录候选**，`claims_checked=false`。

名称与摘要分别填对应字段；摘要多词以空格隔开的 `and` / `or` / `not` 连接，分类号用 IPC 前缀，公开号可填完整 `CN...`。另支持 `--inventor`、`--application-number` 和 `--type all|invention|utility_model|design`。多条件由网站按 AND 处理；避免将其他数据库的查询语法直接复制过来。通用词命中多时先用名称、申请人或结构词收窄，再分批扩大召回。默认最多 3 页；需要逐页遍历时将 `--max-pages` 设到预计总页数以上，再以实际总页数核对。达到页数上限时脚本退出码为 3，`status=partial`；它仍保存已取得的候选和未覆盖页数，不能把退出码 3 当成没有检索结果。

## 浏览器或网站故障

脚本遇到入口返回空白 HTTP 202 时，继续等待业务表单，避免把中间响应误判为结论；若最终变成 HTTP 400，会记录 `initial_http_status=202`、`http_status=400` 和 `failure_stage=entry`，不会将其解释为零结果。本机新建浏览器遭拒而现有可见浏览器可用时，优先复用同一会话（已开放调试端口时用 `--cdp-url`；否则用可控制浏览器正常检索），分别记录两条访问路径及其结果；不能声称重试或连接调试端口必然解决站点拒绝。按 [browser-access.md](browser-access.md) 核对查询、第一页首条公开号、总页数及详情链接。若不能访问或缺少浏览器，标记 `unavailable`，继续 Google Patents、PATENTSCOPE。遇到验证码、登录或网站明确限制时停止该通道，由用户在**可见的同一会话**自行处理，不索取凭据或复制 Cookie。

分页期间若已取到完整的前几页，但下一页出现超时、卡片重复或其他浏览器异常，输出 `status=partial`、`coverage_reason=search_interrupted`、已验页码及对应候选，并记录 `failure_stage` 和 `error_code`；零页成功提取时仍为 `unavailable`。脚本在已知总页数时还需核对末页“下一页”不可用；仅页码等于总页数、但下一页仍可用时标记 `missing_terminal_evidence`。不能把部分结果当成完整结果或声称未取到任何记录。

可控制浏览器的独立检索步骤：导航到 `/Advanced` 并确认页面有 `#ti`；名称填 `#ti`，摘要填 `#abs`，申请人填 `#e71_73`，公布号填 `#pn`，分类号填 `#e51`；勾选专利类型后点击“查询”。确认落在 `/Dxb/AdvancedQuery`，从 `.overview-default > .item` 逐条读取标题、`dl > dt/dd` 著录、摘要和公开号，形成官方单篇入口 `/patent/{公开号}`。从 `.page_ctrl .page_total` 读取“共 N 页”，点击 `.next_page` 后核对首条公开号已变化，重复至第 N 页或页数上限。若页数没有确认、页码未变化或卡片重复，应标记部分覆盖。正式零结果页会显示“抱歉，没有您要查询的结果！”；只有提交后出现这一提示才记录零结果。浏览器获得结果而本地脚本因入口 HTTP 202 失败时，应分别记录两条访问路径及实际结果，不以脚本失败覆盖浏览器的发现。

区分入口、查询提交、结果列表、翻页和单篇详情的失败；HTTP 400 不自动归因为未登录。零命中必须由本次查询的正式结果页证实。只有实际遍历完整批次且采到可核对的总页数，或本次查询明确返回零结果，才写 `coverage_complete=true`；缺少总页数时将覆盖标为部分。报告中注明筛查的是公布公告：可用其官方著录和摘要做初筛；独立权利要求无法从当前页核验时，另找公开全文核对并标记证据来源，绝不能把摘要或检索脚本标志当成权利要求已读。
