# 检索入口与核验规则

站点界面和规则可能调整，每次检索先验证入口可用性。下面是入口和用途，不表示无需登录或保证自动化访问。

| 来源 | 入口 | 用法 |
| --- | --- | --- |
| 中国专利公布公告站 | http://epub.cnipa.gov.cn/Advanced | 中国官方已公开/公告文献的高级著录检索；按名称、摘要、申请人和分类号等字段查询，并核对公开详情页 |
| Google Patents | https://patents.google.com/ | 中英文跨国扩展、同族、引证和单篇公开文本 |
| WIPO PATENTSCOPE | https://patentscope.wipo.int/ | PCT 国际申请及跨国检索，核对 WO 原始文献 |
| Espacenet | https://worldwide.espacenet.com/ | 欧洲及全球文献、同族和分类号复核 |
| USPTO Patent Public Search | https://ppubs.uspto.gov/pubwebapp/ | 需要美国官方全文时使用；验证该入口是否仍有效 |
| USPTO Open Data Portal | https://data.uspto.gov/ | 核对美国申请案卷与公开著录，先验证实时入口和数据更新说明 |
| KIPRIS Plus | https://plus.kipris.or.kr/ | 韩国成为重点地域时使用其官方开放接口；需要 API 授权 |

优先用主管机关的公开文献核验著录事实；跨库来源可用于互证和发现同族，但出现冲突须逐项注明。WIPO 公开文本标识 PCT 申请，不等于该申请在所有指定国获得授权；Google Patents 的法律状态及同族信息可能有延迟。记录网页不可访问、检索失败、需要登录和结果不完整等实际情况，不推断遗漏范围为零。

对每条来源记录：数据库名称、具体文献链接、号码、访问日期、读取到的著录字段以及是否阅读权利要求；若无法得到稳定链接，提供站点入口与能复现的号码/检索式，并标记来源核验等级。

可选的 BigQuery/语义接口用于候选召回或批量去重；需用户现有认证并核对费用、配额及该接口对非美国权利要求的覆盖范围。不要通过不稳定的站点内部 XHR 接口绕过正常页面，也不要将第三方相关性分数当作权利要求复筛结论。

## 官方补充核验

- 美国：先按公开/申请号码在 USPTO Patent Public Search 和 Open Data Portal 核对申请、公开、案卷及时间；权属重要时另查官方 Assignment 记录。转让登记本身不等于已确认的当前最终权利人。接口需要授权时按官网当前说明申请密钥，不在命令、报告或日志中记录密钥。
- 韩国：用户要求韩国重点覆盖且具备 KIPRIS Plus 授权时，先以 `getWordSearch` 关键词查询，再用申请号执行 `getBibliographyDetailInfoSearch` 核对申请人、发明人和公开号；记录响应页码及异常，不将接口未返回的独立权利要求当作已读全文。
- 大规模候选：已有合规 BigQuery/语义搜索环境时，先检查配额、费用和数据更新日期；结果只用于扩召回和专利族线索。对入选文献仍在原始公开文本核实发明人、申请人和独立权利要求。
