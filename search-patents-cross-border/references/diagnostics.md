# 浏览器故障诊断与安全日志

## 故障判断

| 证据 | category | 后续 |
| --- | --- | --- |
| Disclaimer、登录或验证码 | interaction_required | 保持会话，请用户本人完成必要交互 |
| HTTP 403/429/503等 | http_error | 记录状态和安全页面提示；不推断根因 |
| ERR_CONNECTION_TIMED_OUT | connection_timeout | 记录连接超时，不能确定网络或服务端责任 |
| DNS/TLS等连接错误 | connection_error | 记录错误码，不宣称网站宕机 |
| 页面打开但业务元素缺失 | page_not_ready_or_locator_mismatch | 有限等待，检查快照和渲染状态 |
| 结果已显示但字段定位失败 | extraction_error | 检查容器、表头、号码列 |
| 翻页失败、达到上限或末页证据不足 | coverage_unconfirmed | 保留记录并披露未读部分 |

主文档状态与资源错误分开记录：图片或分析脚本失败不等于整个检索失败。导航超时不等于连接超时：页面已有业务元素时以实际业务状态判断；等待结果行超时归为页面就绪或定位问题。

## 有限重试

连接超时或503最多重试一次正常页面导航，两次均记录。429或站点明确要求停止时遵守Retry-After/页面指示；等待过长则结束通道，不阻塞其他数据库。403、登录、验证码不自动循环重试。禁止更换身份、代理、复制Cookie或调用内部接口绕过防护。

## 日志结构

将 observations 存为 UTF-8 JSON；可复用 scripts/browser_diagnostics.py 的URL脱敏、分类和覆盖判断。浏览器工具执行时按同样结构手动记录，不必重新启动Python浏览器。

```json
{
  "database": "Google Patents",
  "observed_at": "2026-10-15T03:00:00+00:00",
  "stage": "detail",
  "attempt": 1,
  "final_url": "https://patents.google.com/patent/US20250108974A1/en",
  "http_status": 503,
  "error_code": null,
  "page_title": "Sorry...",
  "target_present": false,
  "interaction": null,
  "category": "http_error",
  "next_action": "retry_once"
}
```

stage使用 browser_setup、navigation、interaction、search_form、search、result_page、extraction、pagination、detail、claims 或 zero_results。脱敏URL去除账号信息、查询参数及fragment；检索词另存 query，不存会话ID。仅记录公开页面标题，认证页面标题用固定“认证页面”替代。

不要整包保存网络响应、Cookie、请求头、localStorage、认证页HTML或异常全文。网络工具仅按需要查看状态与错误，敏感值不输出。原始快照若包含账号或验证码不进入公开报告。公布公告站辅助脚本仅输出安全错误类型与阶段；其候选列表及原生报告不包含账号信息。

## 验收

验证：无下一页按钮不算完整；末页禁用按钮且数量吻合才完整；重复公开号、跳页、未知总数、计数不符都不能完整。另覆盖验证/登录、403/400/503、连接超时、定位失败和重复页。离线测试证明逻辑；真实数据库复测证明当次访问状态，两者不得混称。
