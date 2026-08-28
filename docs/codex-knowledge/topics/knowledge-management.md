# knowledge-management 沟通与迭代日志

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

<!-- codex-knowledge:separate-logs-and-documents -->
## 项目知识采用日志与文档双轨沉淀

**结论**

保留结构化卡片作为沟通与迭代日志；另建正式文档链路，将已确认事实组织成可独立阅读的完整文章。

**关键点**

- 日志与文档在索引中分区展示。
- 正式文档可以引用日志，但不得机械拼接卡片。
- 更新正式文档时需重审全文结构和上下游影响。

**依据**

日志需要保留结论演进和证据，正式文档需要围绕主题形成连续主线；让同一种结构兼任两种目标会造成正文流水账化。

**适用范围**

codex-knowledge-capture 管理的项目知识产物

**记录信息**

- 类型：`decision`
- 证据：`user-confirmed`
- 首次记录：2026-08-24
- 最近更新：2026-08-24

**来源**

- 用户确认，2026-08-24
<!-- /codex-knowledge:separate-logs-and-documents -->

<!-- codex-knowledge:maintain-one-project-document -->
## 项目默认持续维护同一份主文档

**结论**

每个项目默认持续维护同一份主文档；新功能、新任务、新阶段或新主题优先更新原文档，只有形成明确且长期独立的维护边界时才拆分。

**关键点**

- 写作前先扫描 INDEX.md 和 documents/，已有主文档时默认使用 update。
- 拆分前先尝试删重、重组章节、增加目录和压缩低价值细节。
- 确需拆分时记录来源主文档与具体理由，并在主文档保留概览和入口。

**依据**

频繁创建新文档会让项目知识分散、重复并增加检索和一致性维护成本；稳定入口更利于持续演进和整体理解。

**适用范围**

codex-knowledge-capture 管理的项目正式文档

**记录信息**

- 类型：`decision`
- 证据：`user-confirmed`
- 首次记录：2026-08-24
- 最近更新：2026-08-24

**来源**

- 用户确认，2026-08-24
<!-- /codex-knowledge:maintain-one-project-document -->

<!-- codex-knowledge:write-reader-oriented-formal-documents -->
## 正式文档按读者与内容类别组织

**结论**

正式文档只呈现读者需要理解的主题知识，不展示协作过程；写作时采用本次指定的风格，未指定时根据文档用途和目标读者选择合适风格。

**关键点**

- 支持技术类、科普类、研究类、业务类、操作类和自定义风格。
- 章节按实际对象和方法命名，例如数据清洗应展开字段标准化、缺失值处理和异常值识别。
- 审阅标记、修改过程和写作提醒需要先转化为事实、方法或约束，无法转化时不进入正文。

**依据**

正式文档的目标是帮助读者清楚理解内容。协作痕迹和机械套用的检查词汇会打断阅读，也无法准确表达具体方法。

**适用范围**

codex-knowledge-capture 生成和更新的正式文档

**记录信息**

- 类型：`project-preference`
- 证据：`user-confirmed`
- 首次记录：2026-08-28
- 最近更新：2026-08-28

**来源**

- 用户确认，2026-08-28
<!-- /codex-knowledge:write-reader-oriented-formal-documents -->
