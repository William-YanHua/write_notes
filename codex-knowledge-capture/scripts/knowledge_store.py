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
    (target / "topics").mkdir(parents=True, exist_ok=True)
    pending = target / "pending-review.md"
    if not pending.exists():
        write_text(
            pending,
            "# 待确认的项目知识\n\n"
            "> 存放冲突、适用范围不清或证据不足的候选信息。确认后再写入正式主题文档。\n",
        )
    rebuild_index(target)
    return target


def count_markers(path: Path, prefix: str) -> int:
    if not path.is_file():
        return 0
    return path.read_text(encoding="utf-8").count(f"<!-- {prefix}")


def rebuild_index(target: Path) -> None:
    topic_lines: list[str] = []
    for topic_file in sorted((target / "topics").glob("*.md")):
        count = count_markers(topic_file, "codex-knowledge:")
        if count:
            topic_lines.append(
                f"- [{topic_file.stem}](topics/{topic_file.name}) — {count} 条"
            )
    if not topic_lines:
        topic_lines.append("- 暂无正式知识")

    pending_count = count_markers(target / "pending-review.md", "codex-pending:")
    content = (
        "# Codex 项目知识\n\n"
        "> 本目录只沉淀当前项目中经过确认或验证、可供未来任务复用的信息。\n\n"
        "## 主题\n\n"
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
    for topic_file in sorted((target / "topics").glob("*.md")):
        match = pattern.search(topic_file.read_text(encoding="utf-8"))
        if match:
            return topic_file, match
    return None


def topic_header(topic: str) -> str:
    return f"# {topic} 项目知识\n\n"


def add_or_update(target: Path, entry: dict[str, Any]) -> str:
    existing = find_existing(target, entry["id"])
    target_file = target / "topics" / f"{entry['topic']}.md"

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize project-local knowledge")
    init_parser.add_argument("--project-root")
    init_parser.add_argument("--knowledge-dir")

    resolve_parser = subparsers.add_parser("resolve", help="print configured knowledge path")
    resolve_parser.add_argument("--project-root")

    write_parser = subparsers.add_parser("write", help="write one structured entry")
    write_parser.add_argument("--project-root")
    write_parser.add_argument("--input", required=True, type=Path)
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
        else:
            config = load_config(project_root)
            target = knowledge_path(project_root, config)
            entry = load_entry(args.input)
            status = write_conflict(target, entry) if entry["action"] == "conflict" else add_or_update(target, entry)
            result = {"status": status, "id": entry["id"], "knowledge_dir": str(target)}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (KnowledgeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
