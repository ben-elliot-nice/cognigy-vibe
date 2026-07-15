# tests/test_build_explain_topics.py
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_explain_topics as bet


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_dir_requires_index_md_in_group_directory(tmp_path):
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "leaf-one.md", "---\ntopic: leaf-one\ndescription: d\n---\nbody\n")
    errors: list[str] = []
    bet.scan_dir(resources, "", errors)
    assert any("aiagent" in e and "index.md" in e for e in errors)


def test_scan_dir_rejects_group_field_on_leaf_topic(tmp_path):
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: aiagent primer\n---\nprimer body\n")
    _write(
        resources / "aiagent" / "leaf-one.md",
        "---\ntopic: leaf-one\ndescription: d\ngroup: aiagent\n---\nbody\n",
    )
    errors: list[str] = []
    bet.scan_dir(resources, "", errors)
    assert any("leaf-one.md" in e and "group" in e for e in errors)


def test_scan_dir_rejects_topic_field_on_index_md(tmp_path):
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ntopic: aiagent\ndescription: d\n---\nbody\n")
    errors: list[str] = []
    bet.scan_dir(resources, "", errors)
    assert any("index.md" in e and "topic" in e for e in errors)


def test_scan_dir_rejects_stray_leaf_file_and_index_at_root(tmp_path):
    resources = tmp_path / "resources"
    _write(resources / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "stray.md", "---\ntopic: stray\ndescription: d\n---\nbody\n")
    errors: list[str] = []
    bet.scan_dir(resources, "", errors)
    assert any("must not contain an index.md" in e for e in errors)
    assert any("stray.md" in e for e in errors)


def test_scan_dir_collects_malformed_frontmatter_as_error_not_crash(tmp_path):
    """Regression (PR #260 review): malformed frontmatter must not crash the scan and
    discard every other error already collected — it must be reported like any other
    build error, and scanning must continue for the rest of the tree."""
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "aiagent" / "broken.md", "---\ntopic: broken\ndescription: d\nno closing marker\n")
    _write(resources / "code" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "code" / "dup.md", "---\ntopic: dup\ndescription: d2\n---\nbody2\n")
    errors: list[str] = []
    root = bet.scan_dir(resources, "", errors)
    assert any("No frontmatter found" in e and "broken.md" in e for e in errors)
    keys = {k for k, _, _ in bet.flatten(root)}
    assert "dup" in keys, "scanning other directories must continue past the malformed file"


def test_parse_frontmatter_rejects_duplicate_key_in_same_file(tmp_path):
    """Regression (PR #260 review): a key declared twice in one file's frontmatter was
    silently overwritten by the last value — now must raise instead of clobbering."""
    content = "---\ntopic: first-value\ntopic: second-value\ndescription: d\n---\nbody\n"
    with pytest.raises(ValueError, match="Duplicate frontmatter key 'topic'"):
        bet.parse_frontmatter(content, tmp_path / "fake.md")


def test_scan_dir_collects_duplicate_frontmatter_key_as_build_error(tmp_path):
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "aiagent" / "dup-key.md", "---\ntopic: dup-key\ntopic: other\ndescription: d\n---\nbody\n")
    errors: list[str] = []
    bet.scan_dir(resources, "", errors)
    assert any("Duplicate frontmatter key" in e and "dup-key.md" in e for e in errors)


def test_generate_python_escapes_triple_quote_in_description(tmp_path, monkeypatch):
    """Regression (PR #260 review): a description containing a literal '\"\"\"' must not
    produce a syntactically invalid generated file. Verified by actually parsing the
    generated source with ast.parse, not just checking for a substring."""
    import ast

    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", '---\ndescription: has a """ triple quote\n---\nbody\n')
    monkeypatch.setattr(bet, "RESOURCES", resources)
    errors: list[str] = []
    root = bet.scan_dir(resources, "", errors)
    assert errors == []
    entries = bet.flatten(root)

    output_path = tmp_path / "generated.py"
    bet.generate_python(entries, root, output_path)

    source = output_path.read_text(encoding="utf-8")
    ast.parse(source)  # raises SyntaxError if the embedding is unsafe
    namespace: dict = {}
    exec(compile(source, str(output_path), "exec"), namespace)
    assert 'has a """ triple quote' in namespace["_TOPIC_INDEX"]


def test_generate_python_escapes_triple_quote_in_leaf_topic_body(tmp_path, monkeypatch):
    """Symmetry check for the fix above: generate_python embeds leaf topic bodies via the
    same {k!r}: {b!r} pattern as _TOPIC_INDEX — confirm a leaf body containing a literal
    '\"\"\"' also survives ast.parse + exec, not just group descriptions."""
    import ast

    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(
        resources / "aiagent" / "leaf.md",
        '---\ntopic: leaf\ndescription: d\n---\nBody with a """ triple quote inside.\n',
    )
    monkeypatch.setattr(bet, "RESOURCES", resources)
    errors: list[str] = []
    root = bet.scan_dir(resources, "", errors)
    assert errors == []
    entries = bet.flatten(root)

    output_path = tmp_path / "generated.py"
    bet.generate_python(entries, root, output_path)

    source = output_path.read_text(encoding="utf-8")
    ast.parse(source)
    namespace: dict = {}
    exec(compile(source, str(output_path), "exec"), namespace)
    assert 'Body with a """ triple quote inside.' in namespace["_CONTENT"]["leaf"]


def test_flatten_produces_leaf_and_group_entries_with_full_keys(tmp_path):
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: AI Agent group primer\n---\nPrimer text.\n")
    _write(
        resources / "aiagent" / "agent-avatar-image.md",
        "---\ntopic: agent-avatar-image\ndescription: avatar image pattern\n---\nAvatar body.\n",
    )
    errors: list[str] = []
    root = bet.scan_dir(resources, "", errors)
    assert errors == []
    entries = bet.flatten(root)
    keys = {k for k, _, _ in entries}
    assert "aiagent" in keys
    assert "agent-avatar-image" in keys
    aiagent_body = next(b for k, _, b in entries if k == "aiagent")
    assert "Primer text." in aiagent_body
    assert "agent-avatar-image" in aiagent_body
    assert "avatar image pattern" in aiagent_body


def test_flatten_nested_subgroup_shows_full_path_key(tmp_path):
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: AI Agent group primer\n---\nPrimer.\n")
    _write(resources / "aiagent" / "tools" / "index.md", "---\ndescription: Tool authoring sub-group\n---\nTools primer.\n")
    _write(
        resources / "aiagent" / "tools" / "agent-tool-branch.md",
        "---\ntopic: agent-tool-branch\ndescription: tool branch pattern\n---\nBranch body.\n",
    )
    errors: list[str] = []
    root = bet.scan_dir(resources, "", errors)
    assert errors == []
    entries = bet.flatten(root)
    keys = {k for k, _, _ in entries}
    assert "aiagent/tools" in keys
    assert "agent-tool-branch" in keys
    aiagent_body = next(b for k, _, b in entries if k == "aiagent")
    assert "aiagent/tools" in aiagent_body, "parent primer must show the full callable key of its sub-group"


def test_flatten_and_skill_md_tree_support_three_tier_nesting(tmp_path):
    """Regression (PR #260 review): only one level of subgroup nesting had coverage.
    Exercises scan_dir's recursive path-building and _build_skill_md_section's
    heading-level recursion two levels deep (aiagent/tools/scaffolding)."""
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: AI Agent group primer\n---\nPrimer.\n")
    _write(resources / "aiagent" / "tools" / "index.md", "---\ndescription: Tool authoring sub-group\n---\nTools primer.\n")
    _write(
        resources / "aiagent" / "tools" / "scaffolding" / "index.md",
        "---\ndescription: Scaffolding sub-sub-group\n---\nScaffolding primer.\n",
    )
    _write(
        resources / "aiagent" / "tools" / "scaffolding" / "deep-topic.md",
        "---\ntopic: deep-topic\ndescription: three tiers deep\n---\nDeep body.\n",
    )
    errors: list[str] = []
    root = bet.scan_dir(resources, "", errors)
    assert errors == []

    entries = bet.flatten(root)
    keys = {k for k, _, _ in entries}
    assert "aiagent/tools/scaffolding" in keys
    assert "deep-topic" in keys
    tools_body = next(b for k, _, b in entries if k == "aiagent/tools")
    assert "aiagent/tools/scaffolding" in tools_body, \
        "the tools sub-group primer must list its own scaffolding sub-sub-group by full path"

    tree_text = bet.build_full_topic_tree(root)
    assert "### aiagent/tools/scaffolding" in tree_text or "aiagent/tools/scaffolding" in tree_text
    assert "`aiagent/tools/scaffolding/deep-topic.md`" in tree_text, \
        "SKILL.md tree must show the correct three-level-deep file path"


def test_scan_dir_collects_unreadable_directory_as_error_not_crash(tmp_path, monkeypatch):
    """Regression (PR #260 review): an unguarded dir_path.iterdir() could crash scan_dir
    on a permission error or broken symlink, discarding already-collected errors."""
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "code" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "code" / "leaf.md", "---\ntopic: leaf\ndescription: d\n---\nbody\n")

    real_iterdir = Path.iterdir

    def fake_iterdir(self):
        if self.name == "aiagent":
            raise OSError("simulated permission error")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)
    errors: list[str] = []
    root = bet.scan_dir(resources, "", errors)
    assert any("aiagent" in e and "simulated permission error" in e for e in errors)
    keys = {k for k, _, _ in bet.flatten(root)}
    assert "leaf" in keys, "scanning other directories must continue past the unreadable one"


def test_scan_dir_collects_unreadable_file_as_error_not_crash(tmp_path, monkeypatch):
    """Regression (PR #260 review): unguarded read_text() calls could crash scan_dir on
    a non-UTF-8 file or I/O error."""
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "aiagent" / "unreadable.md", "---\ntopic: unreadable\ndescription: d\n---\nbody\n")
    _write(resources / "code" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "code" / "leaf.md", "---\ntopic: leaf\ndescription: d\n---\nbody\n")

    real_read_text = Path.read_text

    def fake_read_text(self, *args, **kwargs):
        if self.name == "unreadable.md":
            raise OSError("simulated I/O error")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    errors: list[str] = []
    root = bet.scan_dir(resources, "", errors)
    assert any("unreadable.md" in e and "simulated I/O error" in e for e in errors)
    keys = {k for k, _, _ in bet.flatten(root)}
    assert "leaf" in keys, "scanning other files must continue past the unreadable one"


def test_main_reports_duplicate_key_only_once_regardless_of_occurrence_count(tmp_path, monkeypatch, capsys):
    """Regression (PR #260 review): a key duplicated 3+ times was reported N-1 times."""
    resources = tmp_path / "resources"
    _write(resources / "a" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "a" / "dup.md", "---\ntopic: dup\ndescription: d\n---\nbody\n")
    _write(resources / "b" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "b" / "dup.md", "---\ntopic: dup\ndescription: d\n---\nbody\n")
    _write(resources / "c" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "c" / "dup.md", "---\ntopic: dup\ndescription: d\n---\nbody\n")
    monkeypatch.setattr(bet, "RESOURCES", resources)
    monkeypatch.setattr(bet, "TEMPLATE", tmp_path / "SKILL.md.template")
    monkeypatch.setattr(bet, "GENERATED_PY", tmp_path / "generated.py")
    monkeypatch.setattr(bet, "GENERATED_SKILL", tmp_path / "SKILL.md")
    _write(tmp_path / "SKILL.md.template", "{{TOPIC_REGISTRY}}")
    with pytest.raises(SystemExit):
        bet.main()
    captured = capsys.readouterr()
    assert captured.err.count("Duplicate topic/group key: 'dup'") == 1, \
        "a key duplicated 3 times must be reported exactly once, not twice"


def test_build_top_level_index_lists_groups_only(tmp_path):
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: AI Agent stuff\n---\nPrimer.\n")
    _write(resources / "aiagent" / "leaf.md", "---\ntopic: leaf\ndescription: d\n---\nbody\n")
    _write(resources / "code" / "index.md", "---\ndescription: Code node stuff\n---\nPrimer.\n")
    errors: list[str] = []
    root = bet.scan_dir(resources, "", errors)
    assert errors == []
    index_text = bet.build_top_level_index(root)
    assert "aiagent" in index_text
    assert "code" in index_text
    assert "leaf" not in index_text, "top-level index must list groups only, not leaf topics"


def test_main_fails_on_duplicate_keys(tmp_path, monkeypatch, capsys):
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "aiagent" / "dup.md", "---\ntopic: dup\ndescription: d\n---\nbody\n")
    _write(resources / "code" / "index.md", "---\ndescription: d\n---\nbody\n")
    _write(resources / "code" / "dup.md", "---\ntopic: dup\ndescription: d2\n---\nbody2\n")
    monkeypatch.setattr(bet, "RESOURCES", resources)
    monkeypatch.setattr(bet, "TEMPLATE", tmp_path / "SKILL.md.template")
    monkeypatch.setattr(bet, "GENERATED_PY", tmp_path / "generated.py")
    monkeypatch.setattr(bet, "GENERATED_SKILL", tmp_path / "SKILL.md")
    _write(tmp_path / "SKILL.md.template", "{{TOPIC_REGISTRY}}")
    with pytest.raises(SystemExit):
        bet.main()
    captured = capsys.readouterr()
    assert "Duplicate" in captured.err


def test_main_generates_python_and_skill_md_on_success(tmp_path, monkeypatch):
    resources = tmp_path / "resources"
    _write(resources / "aiagent" / "index.md", "---\ndescription: AI Agent group primer\n---\nPrimer.\n")
    _write(resources / "aiagent" / "leaf.md", "---\ntopic: leaf\ndescription: d\n---\nLeaf body.\n")
    monkeypatch.setattr(bet, "RESOURCES", resources)
    monkeypatch.setattr(bet, "TEMPLATE", tmp_path / "SKILL.md.template")
    monkeypatch.setattr(bet, "GENERATED_PY", tmp_path / "generated.py")
    monkeypatch.setattr(bet, "GENERATED_SKILL", tmp_path / "SKILL.md")
    _write(tmp_path / "SKILL.md.template", "before\n{{TOPIC_REGISTRY}}\nafter")

    bet.main()

    generated_py = (tmp_path / "generated.py").read_text(encoding="utf-8")
    assert "'aiagent'" in generated_py
    assert "'leaf'" in generated_py
    assert "| Topic | Description |" in generated_py, "generated index must be a renderable markdown table"
    assert "leaf.md" not in generated_py, \
        "MCP-facing generated content must not carry filesystem paths — the tool already returns real content"
    assert "index.md" not in generated_py, \
        "MCP-facing generated content must not carry filesystem paths"

    skill_md = (tmp_path / "SKILL.md").read_text(encoding="utf-8")
    assert "before" in skill_md and "after" in skill_md
    assert "aiagent" in skill_md
    assert "| Topic | Description | File |" in skill_md, \
        "SKILL.md must carry a File column so a session without the MCP tool can read topics directly"
    assert "`aiagent/index.md`" in skill_md, "SKILL.md must show each group's own index.md path"
    assert "`aiagent/leaf.md`" in skill_md, "SKILL.md must show each leaf topic's source file path"
