# 正式文档输入格式

`knowledge_store.py write-document` 接收一个 UTF-8 JSON 对象。脚本校验文档元数据和基本完整性，并将正文写入 `documents/<id>.md`。

## 完整示例

```json
{
  "action": "add",
  "semantic_rewrite": true,
  "id": "project-knowledge-capture",
  "title": "项目知识沉淀机制",
  "type": "architecture",
  "status": "stable",
  "writing_style": "technical",
  "style_notes": "面向项目开发者，重点解释双轨机制和写入规则。",
  "summary": "说明项目如何分别维护可追溯的迭代日志与可独立阅读的正式文档。",
  "audience": [
    "项目开发者",
    "维护项目知识的 Codex Agent"
  ],
  "scope": "项目内可复用知识的采集、成文、更新和导航",
  "source_log_ids": [
    "keep-knowledge-project-local",
    "write-semantic-concise-knowledge"
  ],
  "split_from": null,
  "split_reason": null,
  "sources": [
    "项目知识沉淀决策，2026-08-24",
    "codex-knowledge-capture/SKILL.md"
  ],
  "updated_at": "2026-08-24",
  "body": "## 背景与目标\n\n项目需要同时解决知识可追溯与系统可读两个问题……\n\n## 整体设计\n\n系统采用双轨模型……\n\n## 边界与验证\n\n日志不直接充当正文……"
}
```

示例正文为了展示 JSON 结构而缩短；实际输入必须满足完整性约束。

## 字段

- `action`：`add` 或 `update`。更新必须提供完整文档，不接受局部补丁。
- `semantic_rewrite`：必须为 `true`，表示已经综合事实并从全文角度重新组织，不是拼接日志。
- `id`：稳定的 kebab-case 文档 ID，同时作为文件名。
- `title`：面向读者的正式标题，不超过 80 个字符。
- `type`：决定内容检查重点，允许值见下文。
- `status`：`draft` 或 `stable`。
- `writing_style`：写作风格，可选；支持 `technical`、`explanatory`、`research`、`business`、`operational` 和 `custom`。省略时按 `type` 推断。
- `style_notes`：用户对本次写作口吻、详略、术语或示例的补充要求，可选；`writing_style` 为 `custom` 时必填。
- `summary`：一句话说明文章解决的问题或价值，不超过 240 个字符。
- `audience`：目标读者，1–6 项。
- `scope`：文章覆盖范围，不超过 240 个字符。
- `source_log_ids`：本文采用的日志稳定 ID；没有关联日志时可以是空数组。
- `split_from`：仅拆分文档使用，填写来源主文档的稳定 ID；项目主文档省略或设为 `null`。
- `split_reason`：仅拆分文档使用，说明为什么重组主文档仍不足以解决维护问题；必须与 `split_from` 同时提供。
- `sources`：项目文件、正式资料、测试结果或用户确认等依据，1–20 项。
- `updated_at`：`YYYY-MM-DD`，省略时使用当前日期。
- `body`：不含一级标题和“参考依据”章节的 Markdown 正文。

## 文档类型

`type` 允许：

- `proposal`
- `analysis`
- `requirements`
- `architecture`
- `technical-design`
- `project-guide`
- `operation-manual`
- `api-reference`
- `troubleshooting`
- `postmortem`
- `decision-record`
- `test-report`
- `comparative-research`
- `research-note`
- `paper-reading`
- `progress-report`
- `meeting-notes`
- `summary`

各类型如何筛选、压缩和重排交互内容，见 [document-type-styles.md](document-type-styles.md)。其中列出的成文主线不是固定目录，不得直接复制成章节标题。

`type` 和 `writing_style` 互相独立：前者说明文档要完成什么任务，后者说明内容如何讲给目标读者。例如，同一份 `technical-design` 可以采用面向开发者的 `technical` 风格，也可以采用面向跨职能评审者的 `explanatory` 风格。

## 正文约束

- 至少 400 个字符，并以二级标题开始。
- 至少包含三个二级章节。
- 不包含一级标题；脚本根据 `title` 统一生成。
- 不创建“参考依据”章节；脚本根据 `sources` 统一生成。
- 可包含自然段、列表、表格、Mermaid 和 LaTeX。
- 正文中不得包含 `codex-document` 保留标记。
- 正文应直接陈述主题知识，不保留用户建议、评审 comment、修改过程或写作提醒。
- 必须引入用户未提及的术语时，应在首次出现处说明它在当前场景中的具体含义；缩写首次出现时应写出全称。
- 二级标题应按实际主题命名，不照抄类型检查清单中的通用词汇。
- `stable` 状态不得包含 `TODO`、“待补充”“待撰写”或占位内容。

这些限制只拦截明显不完整的产物。章节是否充分、主线是否连贯、取舍和边界是否讲清，仍须按写作规范人工判断。

## 添加与更新

```bash
python3 <skill-dir>/scripts/knowledge_store.py write-document \
  --project-root <project-root> \
  --input <document.json>
```

项目没有正式文档时，`add` 创建项目主文档。已有任意正式文档后，默认使用 `update` 维护原文档；再次 `add` 必须同时提供指向项目主文档的 `split_from` 和具体的 `split_reason`，否则脚本拒绝写入。拆分文档不能继续作为其他文档的拆分来源。新主题、新功能、新任务、新阶段或新日期不能单独作为拆分理由，判定标准见 [document-writing.md](document-writing.md)。

`update` 要求文档已由该脚本管理。更新时脚本保留首次创建日期和既有拆分来源，正文整体替换，索引摘要和更新时间同步重建。拆分来源一经建立不可改为其他文档。

所有 `source_log_ids` 必须能在当前项目日志中找到。该字段允许为空，因为文档也可以直接依据代码、配置、测试或正式资料建立。
