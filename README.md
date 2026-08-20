# Codex Knowledge Capture

`codex-knowledge-capture` 是一个 Codex 技能，用于从项目交互中提炼经过确认或验证的可复用知识，并将结果写入当前项目自己的知识目录。

核心约束：

- 每个项目独立保存知识，通过 `.codex-knowledge.json` 记录项目内相对路径。
- 写入前进行语义重写和信息压缩，不机械复述或直译对话。
- 框架、架构和流程优先使用 Mermaid，数学公式使用 LaTeX 定界符。
- 冲突或证据不足的内容进入待确认区，不覆盖正式结论。

## 安装

将技能目录复制到 Codex 技能目录：

```bash
cp -R codex-knowledge-capture ~/.codex/skills/
```

重新打开 Codex 任务后，即可显式调用 `$codex-knowledge-capture`；符合技能描述的项目知识沉淀任务也可以自动触发。

## 目录

```text
codex-knowledge-capture/
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/knowledge_store.py
```

详细工作流、准入规则和条目格式见技能目录中的 `SKILL.md` 与 `references/`。
