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


@dataclass
class LeafTopic:
    key: str
    description: str
    body: str


@dataclass
class GroupIndex:
    key: str  # "" for the virtual resources/ root, else e.g. "aiagent" or "aiagent/tools"
    description: str | None
    body: str | None
    leaf_topics: list[LeafTopic] = field(default_factory=list)
    subgroups: list["GroupIndex"] = field(default_factory=list)


def parse_frontmatter(content: str, path: Path) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from markdown content. Returns (metadata, body)."""
    match = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', content, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter found in {path}")
    fm_text = match.group(1)
    body = content[match.end():]
    metadata: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ':' in line:
            key, _, value = line.partition(':')
            metadata[key.strip()] = value.strip()
    return metadata, body


def scan_dir(dir_path: Path, rel: str, errors: list[str]) -> GroupIndex:
    """Recursively scan a resources directory into a GroupIndex tree, collecting errors."""
    entries = sorted(dir_path.iterdir(), key=lambda p: p.name)
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
            content = index_path.read_text(encoding="utf-8")
            metadata, raw_body = parse_frontmatter(content, index_path)
            if "topic" in metadata:
                errors.append(f"{index_path}: index.md must not declare 'topic' — its key is derived from its directory path")
            description = metadata.get("description", "").strip()
            if not description:
                errors.append(f"{index_path}: missing 'description' in frontmatter")
            body = raw_body.strip()

    leaf_topics: list[LeafTopic] = []
    for md_file in leaf_files:
        content = md_file.read_text(encoding="utf-8")
        metadata, raw_body = parse_frontmatter(content, md_file)
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
        leaf_topics.append(LeafTopic(key=topic, description=topic_description, body=raw_body.strip()))

    subgroups: list[GroupIndex] = []
    for subdir in subdirs:
        child_rel = f"{rel}/{subdir.name}" if rel else subdir.name
        subgroups.append(scan_dir(subdir, child_rel, errors))

    return GroupIndex(
        key=rel,
        description=description,
        body=body,
        leaf_topics=sorted(leaf_topics, key=lambda t: t.key),
        subgroups=sorted(subgroups, key=lambda g: g.key),
    )


def build_children_section(group: GroupIndex) -> str:
    """Auto-generated 'Topics in this group' listing, keyed by full callable path."""
    children = [(t.key, t.description) for t in group.leaf_topics]
    children += [(g.key, g.description or "") for g in group.subgroups]
    if not children:
        return ""
    lines = ["### Topics in this group", "", "```"]
    for key, desc in sorted(children):
        lines.append(f"  {key:<26} {desc}")
    lines.append("```")
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
    """Groups-only top-level index for SKILL.md and explain()'s no-arg response."""
    lines = ["Topics and what they cover:", "", "```"]
    for g in root.subgroups:
        lines.append(f"  {g.key:<26} {g.description or ''}")
    lines.append("```")
    return "\n".join(lines)


def generate_python(entries: list[tuple[str, str, str]], root: GroupIndex, output_path: Path) -> None:
    """Write _explain_topics_generated.py."""
    keys = [e[0] for e in entries]
    topics_repr = repr(keys)
    index = build_top_level_index(root)
    content_items = "\n".join(f"    {k!r}: {b!r}," for k, _, b in entries)
    code = f'''# AUTO-GENERATED by scripts/build_explain_topics.py — do not edit directly
# Source: plugin/skills/explain/resources/
from __future__ import annotations

TOPICS: list[str] = {topics_repr}

_TOPIC_INDEX = """
{index}
"""

_CONTENT: dict[str, str] = {{
{content_items}
}}
'''
    output_path.write_text(code, encoding="utf-8")
    print(f"Generated: {output_path}")


def generate_skill_md(root: GroupIndex, template_path: Path, output_path: Path) -> None:
    """Render SKILL.md.template → SKILL.md."""
    template = template_path.read_text(encoding="utf-8")
    index = build_top_level_index(root)
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
    for key, _, _ in entries:
        if key in seen:
            errors.append(f"Duplicate topic/group key: '{key}'")
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
