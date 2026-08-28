# Codex Knowledge Capture

`codex-knowledge-capture` 是一个项目级知识沉淀 Skill，同时维护两类互补产物：

- **沟通与迭代日志**：用结构化卡片保留已确认结论、证据和变化历史。
- **正式文档**：默认持续维护同一份项目主文档，并按目标读者选择技术类、科普类、研究类、业务类、操作类或自定义写作风格；正文只呈现主题知识，不保留建议、comment 等协作过程。只有形成独立的长期维护边界时才拆分。

两类产物都写入当前项目，通过 `.codex-knowledge.json` 记录项目内相对路径。日志可以成为文档的事实依据，但不会被机械拼接成正文；文档更新也不会覆盖历史日志。

## 安装

将技能目录复制到 Codex 技能目录：

```bash
cp -R codex-knowledge-capture ~/.codex/skills/
```

重新打开 Codex 任务后，可显式调用 `$codex-knowledge-capture`；记录项目结论、总结经验或撰写项目文档时也可以自动触发。

## 目录

```text
codex-knowledge-capture/
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/knowledge_store.py

docs/codex-knowledge/
├── INDEX.md
├── topics/       # 沟通与迭代日志，保留旧目录名以兼容现有项目
├── documents/    # 默认一份项目主文档，必要时包含拆分文档
└── pending-review.md
```

详细选择规则、写作流程和输入格式见技能目录中的 `SKILL.md` 与 `references/`。
