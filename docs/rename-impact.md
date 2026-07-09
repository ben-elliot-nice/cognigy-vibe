# Rename Impact Assessment

Reference catalog for two independent, **not yet executed** renames. Each table lists every current location referencing the old name, so either rename can be picked up later as one deliberate, isolated change. This document does not perform any rename.

## A. GitHub repo rename (`cognigy-claude-plugin` → `cognigy-vibe`)

| Location | Current reference | Action needed |
|---|---|---|
| Git remote | `git@github.com:ben-elliot-nice/cognigy-claude-plugin.git` | Rename repo on GitHub (or update remote if renamed externally), then `git remote set-url origin <new-url>` locally and in any other clones/worktrees. |
| `plugin/.claude-plugin/plugin.json:9-10` | `"homepage"` / `"repository"` both `https://github.com/ben-elliot-nice/cognigy-claude-plugin` | Update both URLs to the new repo path. |
| `README.md:1` | `# cognigy-claude-plugin` (title) | Update to new repo name. |
| `README.md:4-6` | Three Actions badge URLs embed `ben-elliot-nice/cognigy-claude-plugin` | Update all three badge `src` and link URLs. Note: the "Publish to PyPI" badge (line 6) additionally points at a deleted `publish.yml` workflow — a separate, unrelated fix (see the 1.7.0 docs-pass spec, item 1). |
| `README.md:22` | `curl -LsSf https://raw.githubusercontent.com/ben-elliot-nice/cognigy-claude-plugin/dev/plugin/bin/cognigy-setup.sh` | Update raw.githubusercontent.com URL. |
| `README.md:51` | `claude plugin marketplace add ben-elliot-nice/cognigy-claude-plugin` | Update marketplace add command. |
| `CLAUDE.md:143` | `claude plugin marketplace add ben-elliot-nice/cognigy-claude-plugin` | Update marketplace add command (Required Plugins section). |
| `cognigy-mcp/README.md:5` | `Part of the [cognigy-claude-plugin](https://github.com/ben-elliot-nice/cognigy-claude-plugin).` | Update link text and URL. This line is also the PyPI long-description's back-link (see `pyproject.toml`'s `readme` field) — changing it affects the published PyPI page too. |
| `cognigy-mcp/README.md:128-129` | `git clone https://github.com/ben-elliot-nice/cognigy-claude-plugin` / `cd cognigy-claude-plugin/cognigy-mcp` | Update clone URL and directory name in the `cd` command. |
| `plugin/skills/submit-issue/SKILL.md:71` | `--repo ben-elliot-nice/cognigy-claude-plugin` (gh CLI flag) | Update `--repo` argument. |
| `plugin/skills/submit-issue/SKILL.md:95` | `https://github.com/ben-elliot-nice/cognigy-claude-plugin/issues/new` | Update issue URL. |
| `plugin/skills/init-cognigy-vibe/SKILL.md:88` | `[issue #172](https://github.com/ben-elliot-nice/cognigy-claude-plugin/issues/172)` | Update issue URL. Not in the plan's original grep-derived list — found on re-verification; the source file did not exist (or the reference was absent) when the plan was written. |
| `cognigy-mcp/cognigy_mcp/setup.py:71` | `f"ben-elliot-nice/cognigy-claude-plugin@v{ver}"` passed to `claude plugin marketplace add` | Update the hardcoded owner/repo string in the setup wizard's install step. |
| `cognigy-mcp/tests/test_setup.py:131,147` | Two test assertions expect the marketplace-add call with `ben-elliot-nice/cognigy-claude-plugin@v...` | Update both expected-call assertions to match the new string once `setup.py` changes. |
| `.github/CODEOWNERS:1` | `* @ben-elliot-nice` | Not a repo-name reference — this is the GitHub *username*, unaffected by a repo rename. No action needed; listed here only to record it was checked and ruled out. |
| `pyproject.toml` `[project.urls]` | Absent | No `[project.urls]` table exists in `cognigy-mcp/pyproject.toml` — nothing to update on PyPI's project-links metadata. Confirmed absent; re-check if this section is added later. |
| `.claude-plugin/marketplace.json` | No embedded repo URL — only `"source": "./plugin"` | No file edit needed. The repo name is only used *externally*, as the identifier passed to `claude plugin marketplace add <owner>/<repo>`, not stored inside this file. |
