#!/usr/bin/env python3
"""Build explain topics from a directory tree of markdown resource files.

resources/ is a literal hierarchy: every directory at any depth (except the
resources/ root itself) must contain exactly one index.md, the primer for
that directory. Leaf topic files declare topic:+description: frontmatter;
their group is derived from their parent directory, never hand-written.

Generates:
  cognigy-vibe-mcp/cognigy_mcp/tools/_explain_topics_generated.py
  plugin/skills/explain/SKILL.md

Run with: uv run scripts/build_explain_topics.py
"""
from __future__ import annotations
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RESOURCES = REPO_ROOT / "plugin" / "skills" / "explain" / "resources"
TEMPLATE = REPO_ROOT / "plugin" / "skills" / "explain" / "SKILL.md.template"
GENERATED_PY = REPO_ROOT / "cognigy-vibe-mcp" / "cognigy_mcp" / "tools" / "_explain_topics_generated.py"
GENERATED_SKILL = REPO_ROOT / "plugin" / "skills" / "explain" / "SKILL.md"


@dataclass(frozen=True)
class LeafTopic:
    key: str
    description: str
    body: str
    path: str  # source file path, relative to resources/ — SKILL.md-only, never in MCP output


@dataclass(frozen=True)
class GroupIndex:
    key: str  # "" for the virtual resources/ root, else e.g. "aiagent" or "aiagent/tools"
    description: str | None
    body: str | None
    path: str | None  # this group's index.md path, relative to resources/ ("" root has none)
    leaf_topics: list[LeafTopic] = field(default_factory=list)
    subgroups: list["GroupIndex"] = field(default_factory=list)


def parse_frontmatter(content: str, path: Path) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from markdown content. Returns (metadata, body).

    Raises ValueError on malformed frontmatter (no closing '---') or a key declared
    twice in the same block — callers must catch this via _try_parse_frontmatter to
    collect it as a normal build error rather than letting it crash the scan.
    """
    match = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', content, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter found in {path}")
    fm_text = match.group(1)
    body = content[match.end():]
    metadata: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            if key in metadata:
                raise ValueError(f"Duplicate frontmatter key '{key}' in {path}")
            metadata[key] = value.strip()
    return metadata, body


def _try_parse_frontmatter(content: str, path: Path, errors: list[str]) -> tuple[dict[str, str], str] | None:
    """parse_frontmatter, but malformed input is collected into errors instead of raised."""
    try:
        return parse_frontmatter(content, path)
    except ValueError as e:
        errors.append(str(e))
        return None


def _try_read_text(path: Path, errors: list[str]) -> str | None:
    """Read a file as UTF-8, collecting I/O or decode failures into errors instead of raising —
    a broken symlink, permission error, or non-UTF-8 file must not crash the whole scan."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        errors.append(f"{path}: cannot read file ({e})")
        return None


def scan_dir(dir_path: Path, rel: str, errors: list[str]) -> GroupIndex:
    """Recursively scan a resources directory into a GroupIndex tree, collecting errors."""
    try:
        entries = sorted(dir_path.iterdir(), key=lambda p: p.name)
    except OSError as e:
        errors.append(f"{dir_path}: cannot list directory ({e})")
        return GroupIndex(key=rel, description=None, body=None, path=(f"{rel}/index.md" if rel else None))
    md_files = [p for p in entries if p.is_file() and p.suffix == ".md"]
    subdirs = [p for p in entries if p.is_dir()]

    index_candidates = [p for p in md_files if p.name == "index.md"]
    leaf_files = [p for p in md_files if p.name != "index.md"]

    description: str | None
    body: str | None

    if rel == "":
        if index_candidates:
            errors.append("resources/ root must not contain an index.md — the root index is generated, not authored")
        if leaf_files:
            names = ", ".join(p.name for p in leaf_files)
            errors.append(f"resources/ root must not contain topic files directly ({names}) — move them into a group directory")
        description, body = None, None
    else:
        if len(index_candidates) == 0:
            errors.append(f"{rel}/ is missing index.md — every group directory needs exactly one")
            description, body = None, None
        elif len(index_candidates) > 1:
            errors.append(f"{rel}/ has more than one index.md")
            description, body = None, None
        else:
            index_path = index_candidates[0]
            content = _try_read_text(index_path, errors)
            if content is None:
                description, body = None, None
            else:
                parsed = _try_parse_frontmatter(content, index_path, errors)
                if parsed is None:
                    description, body = None, None
                else:
                    metadata, raw_body = parsed
                    if "topic" in metadata:
                        errors.append(f"{index_path}: index.md must not declare 'topic' — its key is derived from its directory path")
                    description = metadata.get("description", "").strip()
                    if not description:
                        errors.append(f"{index_path}: missing 'description' in frontmatter")
                    body = raw_body.strip()

    leaf_topics: list[LeafTopic] = []
    for md_file in leaf_files:
        content = _try_read_text(md_file, errors)
        if content is None:
            continue
        parsed = _try_parse_frontmatter(content, md_file, errors)
        if parsed is None:
            continue
        metadata, raw_body = parsed
        if "group" in metadata:
            errors.append(f"{md_file}: leaf topic files must not declare 'group' — it is derived from directory nesting")
        topic = metadata.get("topic", "").strip()
        topic_description = metadata.get("description", "").strip()
        if not topic:
            errors.append(f"{md_file}: missing 'topic' in frontmatter")
            continue
        if not topic_description:
            errors.append(f"{md_file}: missing 'description' in frontmatter")
            continue
        leaf_path = f"{rel}/{md_file.name}" if rel else md_file.name
        leaf_topics.append(LeafTopic(key=topic, description=topic_description, body=raw_body.strip(), path=leaf_path))

    subgroups: list[GroupIndex] = []
    for subdir in subdirs:
        child_rel = f"{rel}/{subdir.name}" if rel else subdir.name
        subgroups.append(scan_dir(subdir, child_rel, errors))

    return GroupIndex(
        key=rel,
        description=description,
        body=body,
        path=(f"{rel}/index.md" if rel else None),
        leaf_topics=sorted(leaf_topics, key=lambda t: t.key),
        subgroups=sorted(subgroups, key=lambda g: g.key),
    )


def _render_table(rows: list[tuple[str, str]]) -> str:
    """Render (key, description) rows as a two-column markdown table."""
    lines = ["| Topic | Description |", "| --- | --- |"]
    for key, desc in rows:
        safe_desc = desc.replace("|", "\\|")
        lines.append(f"| `{key}` | {safe_desc} |")
    return "\n".join(lines)


def build_children_section(group: GroupIndex) -> str:
    """Auto-generated 'Topics in this group' listing. Leaf topics are keyed by their flat
    topic name; subgroups are keyed by their full callable path (e.g. 'aiagent/tools')."""
    children = [(t.key, t.description) for t in group.leaf_topics]
    children += [(g.key, g.description or "") for g in group.subgroups]
    if not children:
        return ""
    lines = ["### Topics in this group", ""]
    lines.append(_render_table(sorted(children)))
    return "\n".join(lines)


def flatten(group: GroupIndex) -> list[tuple[str, str, str]]:
    """Flatten the tree into (key, description, full_body) tuples. Excludes the virtual root."""
    out: list[tuple[str, str, str]] = []
    if group.key:
        children_section = build_children_section(group)
        full_body = group.body or ""
        if children_section:
            full_body = f"{full_body}\n\n{children_section}" if full_body else children_section
        out.append((group.key, group.description or "", full_body.strip()))
    for topic in group.leaf_topics:
        out.append((topic.key, topic.description, topic.body))
    for sub in group.subgroups:
        out.extend(flatten(sub))
    return out


def build_top_level_index(root: GroupIndex) -> str:
    """Groups-only top-level index for explain()'s no-arg MCP response. No file paths —
    the MCP tool already returns real content, so a filesystem path is dead weight there."""
    rows = [(g.key, g.description or "") for g in root.subgroups]
    lines = ["Topics and what they cover:", "", _render_table(rows)]
    return "\n".join(lines)


def _build_skill_md_section(group: GroupIndex, heading_level: int) -> list[str]:
    """Recursively render one group's children (leaf topics + subgroups) as a path-annotated table,
    then recurse into each subgroup with its own heading."""
    lines: list[str] = []
    rows = [(t.key, t.description, t.path) for t in group.leaf_topics]
    rows += [(g.key, g.description or "", g.path or "") for g in group.subgroups]
    if rows:
        lines.append("| Topic | Description | File |")
        lines.append("| --- | --- | --- |")
        for key, desc, path in sorted(rows):
            safe_desc = desc.replace("|", "\\|")
            lines.append(f"| `{key}` | {safe_desc} | `{path}` |")
        lines.append("")
    for sub in group.subgroups:
        hashes = "#" * min(heading_level, 6)
        lines.append(f"{hashes} {sub.key}")
        lines.append("")
        if sub.description:
            lines.append(sub.description)
            lines.append("")
        lines.extend(_build_skill_md_section(sub, heading_level + 1))
    return lines


def build_full_topic_tree(root: GroupIndex) -> str:
    """Full tree — every group and every leaf topic, each with its source file path — for
    SKILL.md only. Lets a session without the MCP tool available read a topic's content
    directly off disk. Never used for the MCP tool's own generated content (build_top_level_index
    and build_children_section stay path-free for that)."""
    lines = [
        "Topics and what they cover. File paths are relative to "
        "`plugin/skills/explain/resources/` — read a topic's file directly if the "
        "`explain` MCP tool isn't available in this session.",
        "",
    ]
    lines.extend(_build_skill_md_section(root, heading_level=3))
    return "\n".join(lines).rstrip()


def generate_python(entries: list[tuple[str, str, str]], root: GroupIndex, output_path: Path) -> None:
    """Write _explain_topics_generated.py.

    _TOPIC_INDEX is embedded via repr(), not a hand-rolled triple-quoted string — a
    description containing a literal '\"\"\"' would otherwise produce a syntactically
    invalid generated file while the script still reports success (issue found in
    PR #260 review). repr() escapes arbitrary content safely, same as _CONTENT below.
    """
    keys = [e[0] for e in entries]
    topics_repr = repr(keys)
    index_literal = repr(f"\n{build_top_level_index(root)}\n")
    content_items = "\n".join(f"    {k!r}: {b!r}," for k, _, b in entries)
    code = f'''# AUTO-GENERATED by scripts/build_explain_topics.py — do not edit directly
# Source: plugin/skills/explain/resources/
from __future__ import annotations

TOPICS: list[str] = {topics_repr}

_TOPIC_INDEX: str = {index_literal}

_CONTENT: dict[str, str] = {{
{content_items}
}}
'''
    output_path.write_text(code, encoding="utf-8")
    print(f"Generated: {output_path}")


def generate_skill_md(root: GroupIndex, template_path: Path, output_path: Path) -> None:
    """Render SKILL.md.template → SKILL.md. Uses the full path-annotated tree, not the
    groups-only MCP index — SKILL.md is loaded once regardless of tool availability, so it
    carries a filesystem fallback that the MCP tool's own response doesn't need."""
    template = template_path.read_text(encoding="utf-8")
    index = build_full_topic_tree(root)
    output_path.write_text(template.replace("{{TOPIC_REGISTRY}}", index), encoding="utf-8")
    print(f"Generated: {output_path}")


def main() -> None:
    if not RESOURCES.exists():
        print(f"ERROR: resources directory not found: {RESOURCES}", file=sys.stderr)
        sys.exit(1)
    errors: list[str] = []
    root = scan_dir(RESOURCES, "", errors)
    entries = flatten(root)

    # Groups/subgroups get path-derived keys (e.g. "aiagent/tools"), but leaf
    # topic keys (their `topic:` frontmatter value) share one flat global
    # namespace by design — two leaf topics in different groups cannot use
    # the same `topic:` value, and will fail the build here if they do.
    seen: set[str] = set()
    reported: set[str] = set()
    for key, _, _ in entries:
        if key in seen and key not in reported:
            errors.append(f"Duplicate topic/group key: '{key}'")
            reported.add(key)
        seen.add(key)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    if not entries:
        print("ERROR: no topics found", file=sys.stderr)
        sys.exit(1)

    generate_python(entries, root, GENERATED_PY)
    generate_skill_md(root, TEMPLATE, GENERATED_SKILL)
    print(f"Done. {len(entries)} topic(s)/group(s) processed.")


if __name__ == "__main__":
    main()
