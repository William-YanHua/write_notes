# knowledge-management 项目知识

<!-- codex-knowledge:keep-knowledge-project-local -->
## 项目知识采用仓库级隔离

**结论**

每个项目独立保存知识，并通过项目内相对路径配置定位知识目录。

**关键点**

- 路径配置保存在项目根目录的 .codex-knowledge.json。
- 默认知识目录为 docs/codex-knowledge/。

**依据**

知识随项目移动和版本管理，可避免不同项目的结论互相污染。

**适用范围**

该技能管理的项目知识

**记录信息**

- 类型：`decision`
- 证据：`user-confirmed`
- 首次记录：2026-08-20
- 最近更新：2026-08-20

**来源**

- 用户确认，2026-08-20
<!-- /codex-knowledge:keep-knowledge-project-local -->

<!-- codex-knowledge:write-semantic-concise-knowledge -->
## 项目知识采用语义化精简表达

**结论**

知识必须按实际含义重写并优先呈现关键结论，不得机械直译或复述原话；框架和流程优先使用 Mermaid 配合短说明。

**关键点**

- 术语优先沿用项目代码、正式文档和行业稳定名称。
- 每条知识只保留一个中心结论和必要依据。
- 简单事实或单条约束不强制使用图示。

**依据**

准确术语可避免语义失真，精简结构和关系图可降低后续理解成本。

**适用范围**

该技能写入的所有项目知识

**记录信息**

- 类型：`constraint`
- 证据：`user-confirmed`
- 首次记录：2026-08-20
- 最近更新：2026-08-20

**来源**

- 用户确认，2026-08-20
<!-- /codex-knowledge:write-semantic-concise-knowledge -->

<!-- codex-knowledge:render-math-with-latex-delimiters -->
## Markdown 公式使用可渲染的 LaTeX 定界符

**结论**

行内公式使用单美元符号定界，独立公式使用单独成行的双美元符号定界；不得使用括号式、方括号式定界符或代码块保存公式。

**关键点**

- 多行推导在独立公式块内使用 aligned、cases 等 LaTeX 环境。
- JSON 输入中的 LaTeX 反斜杠需要写成双反斜杠。
- Mermaid 只表达结构关系，数学公式保留在正文中。

**依据**

目标 Markdown 渲染器对美元符号定界的 LaTeX 支持更稳定，其他写法可能按普通文本显示。

**适用范围**

该技能生成的 Markdown 项目知识

**记录信息**

- 类型：`constraint`
- 证据：`user-confirmed`
- 首次记录：2026-08-20
- 最近更新：2026-08-20

**来源**

- 用户确认，2026-08-20
<!-- /codex-knowledge:render-math-with-latex-delimiters -->
