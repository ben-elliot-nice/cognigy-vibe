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
    assert "```" in generated_py, "generated index must be fenced, renderable markdown"

    skill_md = (tmp_path / "SKILL.md").read_text(encoding="utf-8")
    assert "before" in skill_md and "after" in skill_md
    assert "aiagent" in skill_md
    assert "```" in skill_md
