#!/usr/bin/env python3
"""Manage a project-local knowledge directory for Codex conversations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(".codex-knowledge.json")
DEFAULT_KNOWLEDGE_DIR = Path("docs/codex-knowledge")
LOGS_DIR = Path("topics")
DOCUMENTS_DIR = Path("documents")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_TYPES = {
    "decision",
    "constraint",
    "validated-solution",
    "pitfall",
    "project-fact",
    "project-preference",
    "framework",
    "workflow",
}
DIAGRAM_TYPES = {"framework", "workflow"}
MERMAID_PREFIXES = (
    "flowchart ",
    "graph ",
    "sequenceDiagram",
    "stateDiagram",
    "erDiagram",
    "classDiagram",
    "journey",
    "gantt",
    "mindmap",
    "timeline",
    "gitGraph",
    "pie",
)
ACCEPTED_EVIDENCE = {"user-confirmed", "verified", "observed"}
ALL_EVIDENCE = ACCEPTED_EVIDENCE | {"inferred"}
ALLOWED_DOCUMENT_TYPES = {
    "architecture",
    "technical-design",
    "project-guide",
    "troubleshooting",
    "postmortem",
    "decision-record",
    "research-note",
}
ALLOWED_DOCUMENT_STATUS = {"draft", "stable"}
PROJECT_MARKERS = (
    "AGENTS.md",
    "Cargo.toml",
    "go.mod",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
)


class KnowledgeError(Exception):
    """Raised when project knowledge data is invalid."""


def discover_project_root(start: Path) -> Path:
    start = start.expanduser().resolve()
    if start.is_file():
        start = start.parent

    # Prefer the closest existing project-local dependency record. This keeps an
    # explicitly initialized monorepo subproject independent from its Git root.
    for directory in (start, *start.parents):
        if (directory / CONFIG_PATH).is_file():
            return directory

    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip()).resolve()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    for directory in (start, *start.parents):
        if any((directory / marker).exists() for marker in PROJECT_MARKERS):
            return directory
    return start


def resolve_root(value: str | None) -> Path:
    if value:
        root = Path(value).expanduser().resolve()
        if root.is_file():
            raise KnowledgeError("project_root must be a directory")
        return root
    return discover_project_root(Path.cwd())


def validate_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise KnowledgeError("knowledge_dir must be a project-relative path without '..'")
    if path == Path(".") or path.parts[0] == ".git":
        raise KnowledgeError("knowledge_dir must be a dedicated directory outside .git")
    return path


def config_file(project_root: Path) -> Path:
    return project_root / CONFIG_PATH


def load_config(project_root: Path) -> dict[str, Any]:
    path = config_file(project_root)
    if not path.is_file():
        raise KnowledgeError(
            f"missing {CONFIG_PATH}; initialize this project with the init command"
        )
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise KnowledgeError(f"cannot read {path}: {exc}") from exc

    if config.get("version") != 1 or config.get("project_root") != ".":
        raise KnowledgeError(f"unsupported or invalid config: {path}")
    knowledge_dir = config.get("knowledge_dir")
    if not isinstance(knowledge_dir, str):
        raise KnowledgeError(f"knowledge_dir is missing from {path}")
    validate_relative_path(knowledge_dir)
    return config


def knowledge_path(project_root: Path, config: dict[str, Any]) -> Path:
    path = (project_root / validate_relative_path(config["knowledge_dir"])).resolve()
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise KnowledgeError("knowledge directory resolves outside the project") from exc
    return path


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_name = temporary.name
        Path(temporary_name).replace(path)
    finally:
        if temporary_name:
            temporary_path = Path(temporary_name)
            if temporary_path.exists():
                temporary_path.unlink()


def initialize(project_root: Path, relative_dir: str | None) -> Path:
    if not project_root.is_dir():
        raise KnowledgeError(f"project root does not exist or is not a directory: {project_root}")
    path = config_file(project_root)

    if path.exists():
        config = load_config(project_root)
        configured = validate_relative_path(config["knowledge_dir"])
        requested = validate_relative_path(relative_dir) if relative_dir else configured
        if configured != requested:
            raise KnowledgeError(
                f"project already uses {configured}; refusing to replace it with {requested}"
            )
    else:
        requested = validate_relative_path(
            relative_dir or DEFAULT_KNOWLEDGE_DIR.as_posix()
        )
        config = {
            "version": 1,
            "project_root": ".",
            "knowledge_dir": requested.as_posix(),
            "path_resolution": "project-relative",
            "created_at": date.today().isoformat(),
        }
        write_text(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")

    target = knowledge_path(project_root, config)
    (target / LOGS_DIR).mkdir(parents=True, exist_ok=True)
    (target / DOCUMENTS_DIR).mkdir(parents=True, exist_ok=True)
    pending = target / "pending-review.md"
    if not pending.exists():
        write_text(
            pending,
            "# 待确认的项目知识\n\n"
            "> 存放冲突、适用范围不清或证据不足的候选信息。确认后可写入日志，并按需同步到正式文档。\n",
        )
    rebuild_index(target)
    return target


def count_markers(path: Path, prefix: str) -> int:
    if not path.is_file():
        return 0
    return path.read_text(encoding="utf-8").count(f"<!-- {prefix}")


def extract_document_metadata(content: str) -> dict[str, Any] | None:
    match = re.search(r"<!-- codex-document-meta:(\{.*\}) -->", content)
    if not match:
        return None
    try:
        metadata = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    required = {"title", "summary", "status", "updated_at"}
    if not isinstance(metadata, dict) or not required.issubset(metadata):
        return None
    return metadata


def rebuild_index(target: Path) -> None:
    document_lines: list[str] = []
    for document_file in sorted((target / DOCUMENTS_DIR).glob("*.md")):
        metadata = extract_document_metadata(
            document_file.read_text(encoding="utf-8")
        )
        if not metadata:
            continue
        status = "稳定" if metadata["status"] == "stable" else "草稿"
        document_lines.append(
            f"- [{metadata['title']}](documents/{document_file.name})"
            f" — {metadata['summary']}（{status}，{metadata['updated_at']}）"
        )
    if not document_lines:
        document_lines.append("- 暂无正式文档")

    topic_lines: list[str] = []
    for topic_file in sorted((target / LOGS_DIR).glob("*.md")):
        count = count_markers(topic_file, "codex-knowledge:")
        if count:
            topic_lines.append(
                f"- [{topic_file.stem}](topics/{topic_file.name}) — {count} 条"
            )
    if not topic_lines:
        topic_lines.append("- 暂无沟通与迭代日志")

    pending_count = count_markers(target / "pending-review.md", "codex-pending:")
    content = (
        "# Codex 项目知识\n\n"
        "> 正式文档用于系统理解主题；沟通与迭代日志用于保留可追溯的结论变化。\n\n"
        "## 正式文档\n\n"
        + "\n".join(document_lines)
        + "\n\n## 沟通与迭代日志\n\n"
        + "\n".join(topic_lines)
        + "\n\n## 待确认\n\n"
        f"- [冲突和低置信信息](pending-review.md) — {pending_count} 条\n"
    )
    write_text(target / "INDEX.md", content)


def require_text(
    entry: dict[str, Any],
    key: str,
    *,
    max_length: int | None = None,
    allow_mermaid_syntax: bool = False,
) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeError(f"{key} must be a non-empty string")
    value = value.strip()
    if (
        "<!--" in value
        or "```" in value
        or "\x00" in value
        or ("-->" in value and not allow_mermaid_syntax)
    ):
        raise KnowledgeError(f"{key} contains a reserved marker or null byte")
    if max_length is not None and len(value) > max_length:
        raise KnowledgeError(f"{key} must be at most {max_length} characters")
    return value


def require_string_list(
    entry: dict[str, Any],
    key: str,
    optional: bool = False,
    *,
    max_items: int | None = None,
    max_item_length: int | None = None,
) -> list[str]:
    value = entry.get(key, [] if optional else None)
    if not isinstance(value, list) or (not optional and not value):
        raise KnowledgeError(f"{key} must be a non-empty string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise KnowledgeError(f"{key} must contain only non-empty strings")
    normalized = [item.strip() for item in value]
    if any(
        "<!--" in item or "-->" in item or "```" in item or "\x00" in item
        for item in normalized
    ):
        raise KnowledgeError(f"{key} contains a reserved marker or null byte")
    if max_items is not None and len(normalized) > max_items:
        raise KnowledgeError(f"{key} must contain at most {max_items} items")
    if max_item_length is not None and any(
        len(item) > max_item_length for item in normalized
    ):
        raise KnowledgeError(
            f"each {key} item must be at most {max_item_length} characters"
        )
    return normalized


def optional_text(
    entry: dict[str, Any],
    key: str,
    *,
    max_length: int,
    allow_mermaid_syntax: bool = False,
) -> str | None:
    if entry.get(key) is None:
        return None
    return require_text(
        entry,
        key,
        max_length=max_length,
        allow_mermaid_syntax=allow_mermaid_syntax,
    )


def validate_diagram(diagram: str | None) -> str | None:
    if diagram is None:
        return None
    if "```" in diagram:
        raise KnowledgeError("diagram must not include Markdown code fences")
    first_line = diagram.splitlines()[0].strip()
    if not any(first_line.startswith(prefix) for prefix in MERMAID_PREFIXES):
        raise KnowledgeError("diagram must start with a supported Mermaid diagram type")
    return diagram


def validate_math_markdown(value: str, key: str) -> None:
    forbidden = (r"\(", r"\)", r"\[", r"\]")
    if any(delimiter in value for delimiter in forbidden):
        raise KnowledgeError(
            f"{key} must use $...$ or standalone $$ delimiters for LaTeX"
        )
    if re.search(r"`[^`\n]*\$[^`\n]*`", value):
        raise KnowledgeError(f"{key} must not put LaTeX formulas in inline code")

    in_block = False
    for line in value.splitlines():
        if "$$" in line:
            if line.strip() != "$$":
                raise KnowledgeError(
                    f"{key} block-math delimiters must each occupy their own line"
                )
            in_block = not in_block
            continue
        if in_block:
            continue
        inline_delimiters = re.findall(r"(?<!\\)\$(?!\$)", line)
        if len(inline_delimiters) % 2 != 0:
            raise KnowledgeError(f"{key} contains an unpaired inline $ delimiter")
    if in_block:
        raise KnowledgeError(f"{key} contains an unpaired $$ delimiter")


def validate_entry_math(entry: dict[str, Any]) -> None:
    for key in ("title", "scope", "conclusion", "reason"):
        validate_math_markdown(entry[key], key)
    for key in ("details", "sources"):
        for index, value in enumerate(entry[key]):
            validate_math_markdown(value, f"{key}[{index}]")
    if entry.get("diagram_omission_reason"):
        validate_math_markdown(
            entry["diagram_omission_reason"], "diagram_omission_reason"
        )
    if entry.get("question"):
        validate_math_markdown(entry["question"], "question")


def validate_entry(entry: dict[str, Any]) -> dict[str, Any]:
    if entry.get("semantic_rewrite") is not True:
        raise KnowledgeError(
            "semantic_rewrite must be true after meaning and terminology are reviewed"
        )
    action = require_text(entry, "action")
    if action not in {"add", "update", "conflict"}:
        raise KnowledgeError("action must be add, update, or conflict")

    knowledge_id = require_text(entry, "id")
    topic = require_text(entry, "topic")
    if not SLUG_RE.fullmatch(knowledge_id) or len(knowledge_id) > 80:
        raise KnowledgeError("id must be kebab-case and at most 80 characters")
    if not SLUG_RE.fullmatch(topic) or len(topic) > 64:
        raise KnowledgeError("topic must be kebab-case and at most 64 characters")

    entry_type = require_text(entry, "type")
    if entry_type not in ALLOWED_TYPES:
        raise KnowledgeError(f"unsupported type: {entry_type}")
    evidence = require_text(entry, "evidence")
    if evidence not in ALL_EVIDENCE:
        raise KnowledgeError(f"unsupported evidence: {evidence}")
    if action != "conflict" and evidence not in ACCEPTED_EVIDENCE:
        raise KnowledgeError("inferred knowledge can only be written as conflict")

    diagram = validate_diagram(
        optional_text(
            entry,
            "diagram",
            max_length=4000,
            allow_mermaid_syntax=True,
        )
    )
    omission_reason = optional_text(
        entry, "diagram_omission_reason", max_length=200
    )
    if diagram and omission_reason:
        raise KnowledgeError(
            "provide diagram or diagram_omission_reason, not both"
        )
    if entry_type in DIAGRAM_TYPES and not (diagram or omission_reason):
        raise KnowledgeError(
            f"{entry_type} entries require diagram or diagram_omission_reason"
        )

    normalized = {
        "action": action,
        "semantic_rewrite": True,
        "id": knowledge_id,
        "topic": topic,
        "title": require_text(entry, "title", max_length=60),
        "type": entry_type,
        "evidence": evidence,
        "scope": require_text(entry, "scope", max_length=160),
        "conclusion": require_text(entry, "conclusion", max_length=320),
        "reason": require_text(entry, "reason", max_length=320),
        "diagram": diagram,
        "diagram_omission_reason": omission_reason,
        "details": require_string_list(
            entry,
            "details",
            optional=True,
            max_items=5,
            max_item_length=200,
        ),
        "sources": require_string_list(
            entry,
            "sources",
            max_items=8,
            max_item_length=240,
        ),
        "recorded_at": entry.get("recorded_at") or date.today().isoformat(),
    }
    if not isinstance(normalized["recorded_at"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", normalized["recorded_at"]
    ):
        raise KnowledgeError("recorded_at must use YYYY-MM-DD")

    if action == "conflict":
        normalized["question"] = require_text(
            entry, "question", max_length=240
        )
        conflicts_with = entry.get("conflicts_with")
        if conflicts_with is not None:
            if not isinstance(conflicts_with, str) or not SLUG_RE.fullmatch(conflicts_with):
                raise KnowledgeError("conflicts_with must be a kebab-case ID")
            normalized["conflicts_with"] = conflicts_with
    validate_entry_math(normalized)
    return normalized


def validate_document_body(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeError("body must be a non-empty Markdown string")
    body = value.strip()
    if len(body) < 400:
        raise KnowledgeError("body must contain at least 400 characters of developed prose")
    if len(body) > 60000:
        raise KnowledgeError("body must contain at most 60000 characters")
    if "\x00" in body or "<!-- codex-document" in body:
        raise KnowledgeError("body contains a reserved marker or null byte")

    prose = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    if re.search(r"^#\s+", prose, re.MULTILINE):
        raise KnowledgeError("body must not contain an H1; title is rendered separately")
    if len(re.findall(r"^##\s+\S", prose, re.MULTILINE)) < 3:
        raise KnowledgeError("body must contain at least three H2 sections")
    if not body.startswith("## "):
        raise KnowledgeError("body must start with an H2 section")
    if re.search(r"^##\s+参考依据\s*$", prose, re.MULTILINE):
        raise KnowledgeError("body must not define 参考依据; sources are rendered separately")
    validate_math_markdown(prose, "body")
    return body


def validate_document(entry: dict[str, Any]) -> dict[str, Any]:
    if entry.get("semantic_rewrite") is not True:
        raise KnowledgeError(
            "semantic_rewrite must be true after the document is synthesized as a whole"
        )
    action = require_text(entry, "action")
    if action not in {"add", "update"}:
        raise KnowledgeError("document action must be add or update")

    document_id = require_text(entry, "id")
    if not SLUG_RE.fullmatch(document_id) or len(document_id) > 80:
        raise KnowledgeError("document id must be kebab-case and at most 80 characters")

    document_type = require_text(entry, "type")
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise KnowledgeError(f"unsupported document type: {document_type}")
    status = require_text(entry, "status")
    if status not in ALLOWED_DOCUMENT_STATUS:
        raise KnowledgeError("document status must be draft or stable")

    split_from = optional_text(entry, "split_from", max_length=80)
    split_reason = optional_text(entry, "split_reason", max_length=320)
    if bool(split_from) != bool(split_reason):
        raise KnowledgeError("split_from and split_reason must be provided together")
    if split_from and not SLUG_RE.fullmatch(split_from):
        raise KnowledgeError("split_from must be a kebab-case document ID")
    if split_from == document_id:
        raise KnowledgeError("a document cannot be split from itself")

    normalized = {
        "action": action,
        "semantic_rewrite": True,
        "id": document_id,
        "title": require_text(entry, "title", max_length=80),
        "type": document_type,
        "status": status,
        "summary": require_text(entry, "summary", max_length=240),
        "audience": require_string_list(
            entry, "audience", max_items=6, max_item_length=80
        ),
        "scope": require_text(entry, "scope", max_length=240),
        "split_from": split_from,
        "split_reason": split_reason,
        "source_log_ids": require_string_list(
            entry,
            "source_log_ids",
            optional=True,
            max_items=50,
            max_item_length=80,
        ),
        "sources": require_string_list(
            entry, "sources", max_items=20, max_item_length=240
        ),
        "body": validate_document_body(entry.get("body")),
        "updated_at": entry.get("updated_at") or date.today().isoformat(),
    }
    if any(not SLUG_RE.fullmatch(item) for item in normalized["source_log_ids"]):
        raise KnowledgeError("source_log_ids must contain only kebab-case IDs")
    if not isinstance(normalized["updated_at"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", normalized["updated_at"]
    ):
        raise KnowledgeError("updated_at must use YYYY-MM-DD")
    placeholder_patterns = (
        r"\b(?:TODO|TBD|FIXME)\b",
        r"(?:\[|【|<|（|\()\s*(?:待补充|待撰写|占位)\s*(?:\]|】|>|）|\))",
        r"^#{2,6}\s+(?:待补充|待撰写|占位)\s*$",
    )
    if status == "stable" and any(
        re.search(pattern, normalized["body"], re.IGNORECASE | re.MULTILINE)
        for pattern in placeholder_patterns
    ):
        raise KnowledgeError("stable documents must not contain unresolved placeholders")
    for key in ("title", "summary", "scope"):
        validate_math_markdown(normalized[key], key)
    for key in ("split_reason",):
        if normalized[key]:
            validate_math_markdown(normalized[key], key)
    for key in ("audience", "sources"):
        for index, value in enumerate(normalized[key]):
            validate_math_markdown(value, f"{key}[{index}]")
    return normalized


def render_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_entry(entry: dict[str, Any], first_recorded: str | None = None) -> str:
    first_recorded = first_recorded or entry["recorded_at"]
    diagram = ""
    if entry["diagram"]:
        diagram = f"\n\n```mermaid\n{entry['diagram']}\n```"
    details = ""
    if entry["details"]:
        details = f"\n\n**关键点**\n\n{render_list(entry['details'])}"
    omission = ""
    if entry["diagram_omission_reason"]:
        omission = (
            "\n\n**图示说明**\n\n"
            f"{entry['diagram_omission_reason']}"
        )
    return (
        f"<!-- codex-knowledge:{entry['id']} -->\n"
        f"## {entry['title']}\n\n"
        f"**结论**\n\n{entry['conclusion']}"
        f"{diagram}"
        f"{details}"
        f"{omission}\n\n"
        f"**依据**\n\n{entry['reason']}\n\n"
        f"**适用范围**\n\n{entry['scope']}\n\n"
        f"**记录信息**\n\n"
        f"- 类型：`{entry['type']}`\n"
        f"- 证据：`{entry['evidence']}`\n"
        f"- 首次记录：{first_recorded}\n"
        f"- 最近更新：{entry['recorded_at']}\n\n"
        f"**来源**\n\n{render_list(entry['sources'])}\n"
        f"<!-- /codex-knowledge:{entry['id']} -->"
    )


def render_document(entry: dict[str, Any], created_at: str | None = None) -> str:
    metadata = {
        "id": entry["id"],
        "title": entry["title"],
        "type": entry["type"],
        "status": entry["status"],
        "summary": entry["summary"],
        "audience": entry["audience"],
        "scope": entry["scope"],
        "source_log_ids": entry["source_log_ids"],
        "created_at": created_at or entry["updated_at"],
        "updated_at": entry["updated_at"],
    }
    if entry["split_from"]:
        metadata["split_from"] = entry["split_from"]
        metadata["split_reason"] = entry["split_reason"]
    metadata_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
    return (
        f"<!-- codex-document:{entry['id']} -->\n"
        f"<!-- codex-document-meta:{metadata_json} -->\n"
        f"# {entry['title']}\n\n"
        f"> {entry['summary']}\n\n"
        f"{entry['body'].rstrip()}\n\n"
        f"## 参考依据\n\n"
        f"{render_list(entry['sources'])}\n"
        f"<!-- /codex-document:{entry['id']} -->\n"
    )


def extract_sources(block: str) -> list[str]:
    match = re.search(
        r"\n\*\*来源\*\*\n\n(?P<sources>.*?)(?:\n<!-- /codex-knowledge:)",
        block,
        re.DOTALL,
    )
    if not match:
        return []
    return [
        line[2:].strip()
        for line in match.group("sources").splitlines()
        if line.startswith("- ") and line[2:].strip()
    ]


def block_pattern(knowledge_id: str) -> re.Pattern[str]:
    escaped = re.escape(knowledge_id)
    return re.compile(
        rf"<!-- codex-knowledge:{escaped} -->.*?"
        rf"<!-- /codex-knowledge:{escaped} -->",
        re.DOTALL,
    )


def find_existing(target: Path, knowledge_id: str) -> tuple[Path, re.Match[str]] | None:
    pattern = block_pattern(knowledge_id)
    for topic_file in sorted((target / LOGS_DIR).glob("*.md")):
        match = pattern.search(topic_file.read_text(encoding="utf-8"))
        if match:
            return topic_file, match
    return None


def topic_header(topic: str) -> str:
    return f"# {topic} 沟通与迭代日志\n\n"


def add_or_update(target: Path, entry: dict[str, Any]) -> str:
    existing = find_existing(target, entry["id"])
    target_file = target / LOGS_DIR / f"{entry['topic']}.md"

    if entry["action"] == "add" and existing:
        raise KnowledgeError(f"knowledge ID already exists: {entry['id']}")
    if entry["action"] == "update" and not existing:
        raise KnowledgeError(f"cannot update missing knowledge ID: {entry['id']}")

    if existing:
        existing_file, match = existing
        if existing_file != target_file:
            raise KnowledgeError(
                f"knowledge ID belongs to topic {existing_file.stem}, not {entry['topic']}"
            )
        old_block = match.group(0)
        first_match = re.search(r"^- 首次记录：(\d{4}-\d{2}-\d{2})$", old_block, re.MULTILINE)
        first_recorded = first_match.group(1) if first_match else entry["recorded_at"]
        if entry["recorded_at"] < first_recorded:
            raise KnowledgeError("recorded_at cannot be earlier than the first recorded date")
        old_sources = extract_sources(old_block)
        merged_sources = list(dict.fromkeys([*old_sources, *entry["sources"]]))
        if len(merged_sources) > 8:
            merged_sources = [merged_sources[0], *merged_sources[-7:]]
        entry["sources"] = merged_sources
        new_block = render_entry(entry, first_recorded)
        content = existing_file.read_text(encoding="utf-8")
        write_text(existing_file, content[: match.start()] + new_block + content[match.end() :])
        result = "updated"
    else:
        block = render_entry(entry)
        content = target_file.read_text(encoding="utf-8") if target_file.exists() else topic_header(entry["topic"])
        write_text(target_file, content.rstrip() + "\n\n" + block + "\n")
        result = "added"

    rebuild_index(target)
    return result


def add_or_update_document(target: Path, entry: dict[str, Any]) -> str:
    for source_log_id in entry["source_log_ids"]:
        if not find_existing(target, source_log_id):
            raise KnowledgeError(f"source log ID does not exist: {source_log_id}")

    target_file = target / DOCUMENTS_DIR / f"{entry['id']}.md"
    exists = target_file.is_file()
    if entry["action"] == "add" and exists:
        raise KnowledgeError(f"document already exists: {entry['id']}")
    if entry["action"] == "update" and not exists:
        raise KnowledgeError(f"cannot update missing document: {entry['id']}")

    document_files = sorted((target / DOCUMENTS_DIR).glob("*.md"))
    if entry["action"] == "add" and not document_files and entry["split_from"]:
        raise KnowledgeError("the first project document cannot be a split document")
    if entry["action"] == "add" and document_files:
        if not entry["split_from"]:
            existing_ids = []
            for document_file in document_files:
                metadata = extract_document_metadata(
                    document_file.read_text(encoding="utf-8")
                )
                existing_ids.append(
                    metadata.get("id", document_file.stem) if metadata else document_file.stem
                )
            raise KnowledgeError(
                "this project already has a document; update one of "
                f"{', '.join(existing_ids)} or provide split_from and split_reason "
                "when an independent maintenance boundary requires a split"
            )

        split_source_file = target / DOCUMENTS_DIR / f"{entry['split_from']}.md"
        if not split_source_file.is_file():
            raise KnowledgeError(
                f"split source document does not exist: {entry['split_from']}"
            )
        split_source_metadata = extract_document_metadata(
            split_source_file.read_text(encoding="utf-8")
        )
        if (
            not split_source_metadata
            or split_source_metadata.get("id") != entry["split_from"]
        ):
            raise KnowledgeError(
                f"cannot split from unmanaged document: {split_source_file}"
            )
        if split_source_metadata.get("split_from"):
            raise KnowledgeError("a split document must be split directly from the primary document")

    created_at = None
    if exists:
        old_content = target_file.read_text(encoding="utf-8")
        old_metadata = extract_document_metadata(old_content)
        if not old_metadata or old_metadata.get("id") != entry["id"]:
            raise KnowledgeError(f"cannot safely update unmanaged document: {target_file}")
        old_split_from = old_metadata.get("split_from")
        old_split_reason = old_metadata.get("split_reason")
        if old_split_from:
            if entry["split_from"] and entry["split_from"] != old_split_from:
                raise KnowledgeError("split_from cannot change after document creation")
            entry["split_from"] = old_split_from
            entry["split_reason"] = entry["split_reason"] or old_split_reason
        elif entry["split_from"]:
            raise KnowledgeError("an existing primary document cannot become a split document")
        created_at = old_metadata.get("created_at") or old_metadata.get("updated_at")
        if created_at and entry["updated_at"] < created_at:
            raise KnowledgeError("updated_at cannot be earlier than created_at")
        previous_updated_at = old_metadata.get("updated_at")
        if previous_updated_at and entry["updated_at"] < previous_updated_at:
            raise KnowledgeError("updated_at cannot be earlier than the previous update")

    write_text(target_file, render_document(entry, created_at))
    rebuild_index(target)
    return "updated" if exists else "added"


def write_conflict(target: Path, entry: dict[str, Any]) -> str:
    fingerprint_source = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:12]
    marker = f"codex-pending:{entry['id']}:{fingerprint}"
    pending = target / "pending-review.md"
    content = pending.read_text(encoding="utf-8")
    if f"<!-- {marker} -->" in content:
        return "unchanged"

    conflicts_with = ""
    if entry.get("conflicts_with"):
        conflicts_with = f"\n- 冲突条目：`{entry['conflicts_with']}`"
    details = ""
    if entry["details"]:
        details = f"\n\n**关键点**\n\n{render_list(entry['details'])}"
    diagram = ""
    if entry["diagram"]:
        diagram = f"\n\n```mermaid\n{entry['diagram']}\n```"
    omission = ""
    if entry["diagram_omission_reason"]:
        omission = f"\n\n**图示说明**\n\n{entry['diagram_omission_reason']}"
    block = (
        f"<!-- {marker} -->\n"
        f"## {entry['title']}\n\n"
        f"**候选结论**\n\n{entry['conclusion']}"
        f"{diagram}"
        f"{details}"
        f"{omission}\n\n"
        f"**暂不采纳的依据**\n\n{entry['reason']}\n\n"
        f"**需要确认**\n\n{entry['question']}\n\n"
        f"**适用范围**\n\n{entry['scope']}\n\n"
        f"**记录信息**\n\n"
        f"- 候选 ID：`{entry['id']}`\n"
        f"- 主题：`{entry['topic']}`\n"
        f"- 类型：`{entry['type']}`\n"
        f"- 证据：`{entry['evidence']}`\n"
        f"- 记录日期：{entry['recorded_at']}"
        f"{conflicts_with}\n\n"
        f"**来源**\n\n{render_list(entry['sources'])}\n"
        f"<!-- /{marker} -->"
    )
    write_text(pending, content.rstrip() + "\n\n" + block + "\n")
    rebuild_index(target)
    return "pending"


def load_entry(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise KnowledgeError(f"cannot read entry JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise KnowledgeError("entry JSON must contain one object")
    return validate_entry(value)


def load_document(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise KnowledgeError(f"cannot read document JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise KnowledgeError("document JSON must contain one object")
    return validate_document(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize project-local knowledge")
    init_parser.add_argument("--project-root")
    init_parser.add_argument("--knowledge-dir")

    resolve_parser = subparsers.add_parser("resolve", help="print configured knowledge path")
    resolve_parser.add_argument("--project-root")

    for command, help_text in (
        ("write", "write one structured log entry (backward-compatible)"),
        ("write-log", "write one structured communication and iteration log entry"),
    ):
        write_parser = subparsers.add_parser(command, help=help_text)
        write_parser.add_argument("--project-root")
        write_parser.add_argument("--input", required=True, type=Path)

    document_parser = subparsers.add_parser(
        "write-document", help="write one synthesized project document"
    )
    document_parser.add_argument("--project-root")
    document_parser.add_argument("--input", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        project_root = resolve_root(args.project_root)
        if args.command == "init":
            target = initialize(project_root, args.knowledge_dir)
            result = {"status": "initialized", "project_root": str(project_root), "knowledge_dir": str(target)}
        elif args.command == "resolve":
            config = load_config(project_root)
            target = knowledge_path(project_root, config)
            result = {"project_root": str(project_root), "knowledge_dir": str(target)}
        elif args.command in {"write", "write-log"}:
            config = load_config(project_root)
            target = knowledge_path(project_root, config)
            entry = load_entry(args.input)
            status = write_conflict(target, entry) if entry["action"] == "conflict" else add_or_update(target, entry)
            result = {"status": status, "id": entry["id"], "knowledge_dir": str(target)}
        else:
            config = load_config(project_root)
            target = knowledge_path(project_root, config)
            document = load_document(args.input)
            status = add_or_update_document(target, document)
            result = {
                "status": status,
                "id": document["id"],
                "document": str(target / DOCUMENTS_DIR / f"{document['id']}.md"),
                "knowledge_dir": str(target),
            }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (KnowledgeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
