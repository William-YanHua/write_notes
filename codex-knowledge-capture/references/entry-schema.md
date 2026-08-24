# 日志卡片输入格式

`knowledge_store.py write-log` 接收一个 UTF-8 JSON 对象。`write` 是兼容旧调用的别名。

## 正式条目

```json
{
  "action": "add",
  "semantic_rewrite": true,
  "id": "store-time-in-utc",
  "topic": "architecture",
  "title": "服务端时间统一存储 UTC",
  "type": "decision",
  "evidence": "user-confirmed",
  "scope": "服务端持久化的业务时间字段",
  "conclusion": "服务端统一存储 UTC；展示时转换为用户时区。",
  "reason": "避免跨时区和夏令时带来的时间歧义。",
  "details": [
    "接口传输使用带时区的 ISO 8601 时间。"
  ],
  "sources": [
    "用户确认，2026-08-20"
  ],
  "recorded_at": "2026-08-20"
}
```

`semantic_rewrite: true` 表示已经理解实际含义、核对项目术语并重新组织表达，不是原话直译。每次写入都必须显式提供。

`action` 可取：

- `add`：ID 不得已存在。
- `update`：ID 必须已存在，且 `topic` 必须与原条目相同。
- `conflict`：写入待确认文档，不修改正式条目。

必填字段：`action`、`semantic_rewrite`、`id`、`topic`、`title`、`type`、`evidence`、`scope`、`conclusion`、`reason`、`sources`。`details`、`diagram`、`diagram_omission_reason` 和 `recorded_at` 可省略。

允许的 `type`：

- `decision`
- `constraint`
- `validated-solution`
- `pitfall`
- `project-fact`
- `project-preference`
- `framework`
- `workflow`

允许的正式证据：`user-confirmed`、`verified`、`observed`。

`id` 和 `topic` 必须是小写 kebab-case。ID 描述语义，不使用日期或序号。

## 精简限制

- `title`：不超过 60 个字符。
- `scope`：不超过 160 个字符。
- `conclusion`：不超过 320 个字符，优先使用 1–2 句。
- `reason`：不超过 320 个字符。
- `details`：最多 5 条，每条不超过 200 个字符。
- `sources`：最多 8 条，每条不超过 240 个字符。

这些是上限，不是目标长度。能够继续压缩且不损失含义时，应使用更短表达。

## LaTeX 公式

公式直接写入 `conclusion`、`reason` 或 `details`：

```json
{
  "conclusion": "策略更新比率为 $r_t=\\frac{\\pi_\\theta}{\\pi_{\\mathrm{old}}}$。",
  "details": [
    "目标函数为：\n\n$$\nL=-\\mathbb{E}_t[r_tA_t]\n$$"
  ]
}
```

JSON 中使用 `\\` 表示一个 LaTeX 反斜杠。写入后的 Markdown 为：

```markdown
策略更新比率为 $r_t=\frac{\pi_\theta}{\pi_{\mathrm{old}}}$。

$$
L=-\mathbb{E}_t[r_tA_t]
$$
```

只允许 `$...$` 和独立成行的 `$$`。写入器会拒绝 `\(...\)`、`\[...\]`、代码围栏公式以及未配对的公式定界符。

## Mermaid 图示

框架、架构、流程、状态流转或多组件关系可提供不带 Markdown 围栏的 `diagram`：

```json
{
  "action": "add",
  "semantic_rewrite": true,
  "id": "request-failover-flow",
  "topic": "reliability",
  "title": "请求故障转移流程",
  "type": "workflow",
  "evidence": "observed",
  "scope": "在线查询请求",
  "conclusion": "主服务重试一次仍失败时切换备用服务；备用服务失败则返回明确错误。",
  "reason": "限制重试次数可避免故障期间放大流量。",
  "diagram": "flowchart LR\n    A[调用主服务] --> B{\"成功?\"}\n    B -->|是| C[返回结果]\n    B -->|否| D[重试一次]\n    D --> E{\"成功?\"}\n    E -->|否| F[调用备用服务]",
  "details": [
    "只有超时和可重试错误触发故障转移。"
  ],
  "sources": [
    "查询模块代码，2026-08-20"
  ]
}
```

脚本会自动添加 `mermaid` 代码围栏。`diagram` 内不要重复添加围栏。

`framework` 和 `workflow` 默认必须提供 `diagram`。图示不能提升理解时，改填 `diagram_omission_reason`，说明文字为何更清楚。两者不可同时填写。

## 冲突或待确认条目

```json
{
  "action": "conflict",
  "semantic_rewrite": true,
  "id": "store-time-in-utc",
  "topic": "architecture",
  "title": "批处理时间存储规则待确认",
  "type": "decision",
  "evidence": "inferred",
  "scope": "离线批处理模块",
  "conclusion": "批处理模块可能要求保存 Asia/Shanghai 本地时间。",
  "reason": "该行为与 UTC 存储决策冲突，且尚未验证。",
  "sources": [
    "批处理模块代码观察，2026-08-20"
  ],
  "conflicts_with": "store-time-in-utc",
  "question": "离线批处理是否属于 UTC 存储规则的例外？"
}
```

冲突条目额外要求 `question`；与已有条目冲突时填写 `conflicts_with`。

## 更新原则

更新时提供完整条目，不传局部补丁。脚本保留“首次记录”日期与历史来源，并更新“最近更新”日期。

`sources` 只提供新增的独立证据。已有来源已表达同一证据时，不要换一种说法再次加入。
