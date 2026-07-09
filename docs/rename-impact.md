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

## B. `cognigy-mcp/` directory rename (→ `cognigy-vibe-mcp/`)

Renaming the source directory to match the published PyPI package name (`cognigy-vibe-mcp`).

| Location | Current reference | Action needed |
|---|---|---|
| Directory itself | `cognigy-mcp/` (contains `cognigy_mcp/` Python package, `tests/`, `pyproject.toml`, `README.md`, `uv.lock`) | `git mv cognigy-mcp cognigy-vibe-mcp`. Note the *Python import package* is `cognigy_mcp` (underscore) — decide separately whether the import package name also changes, or only the containing directory. This catalog only covers the directory path; a Python package rename is a larger, separate concern (would touch every `import cognigy_mcp` / `from cognigy_mcp...` statement across the codebase) and is out of scope for this row. |
| `.mcp.json` | `"COGNIGY_VIBE_SOURCE_DIR": "./cognigy-mcp"` | Update to `./cognigy-vibe-mcp`. |
| `README.md:118` | `` `.mcp.json` is pre-configured for dev mode ... `COGNIGY_VIBE_SOURCE_DIR=./cognigy-mcp` `` | Update path in prose. |
| `README.md:94` | `[cognigy-mcp/README.md](cognigy-mcp/README.md)` link | Update relative link path. |
| `README.md:144` | Repository layout section: `` cognigy-mcp/  the cognigy-vibe-mcp Python server (+ tests, own README) `` | Update directory name in the layout tree. |
| `CLAUDE.md:101` | `` CI will reject any PR to `dev` that changes the version in `cognigy-mcp/pyproject.toml` `` | Update path. |
| `CLAUDE.md:157` | `` `COGNIGY_VIBE_SOURCE_DIR=./cognigy-mcp` ... The server runs from local source (`./cognigy-mcp`) `` | Update both path mentions. |
| `CLAUDE.md:183` | `` Bump `cognigy-mcp/pyproject.toml` to the intended next version `` | Update path (Prerelease flow section). |
| `docs/architecture.md:19` | `` **Location:** `cognigy-mcp/` `` | Update path. |
| `docs/architecture.md:171,173,175` | Three references to `cognigy-mcp/cognigy_mcp/tools/`, `cognigy-mcp/tests/tools/`, `cognigy-mcp/pyproject.toml` | Update all three paths. |
| `.github/workflows/_release.yml:37,39,72,95` | Reads/writes `cognigy-mcp/pyproject.toml`, stages `cognigy-mcp/pyproject.toml` in a commit | Update all four path references — this is a version-bump-on-release workflow; a wrong path here silently breaks the release automation, so this row is highest-risk if the rename is ever executed. |
| `.github/workflows/_release.yml:122,128` | Two `cd cognigy-mcp` steps, immediately preceding `uv build` and `uv publish` respectively | Update both `cd` targets to `cognigy-vibe-mcp`. Not in the plan's original grep-derived list — found on re-verification. Same risk profile as the row above: a stale path here means the build/publish steps `cd` into a directory that no longer exists, hard-failing the release job. |
| `.github/workflows/check-explain-topics.yml:27` | References `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py` | Update path. |
| `.github/workflows/check-version-bump.yml:23-24,30` | Reads `cognigy-mcp/pyproject.toml` from both working tree and `origin/main`; error message names the path | Update all path references including the error-message string. |
| `.github/workflows/check-no-version-bump.yml:8,25-26` | Path filter trigger (`'cognigy-mcp/pyproject.toml'`) plus two path reads | Update the path filter (a wrong path here means the guard silently stops firing on the renamed directory) and both reads. |
| `.github/workflows/on-prerelease.yml:25,27` | Reads `cognigy-mcp/pyproject.toml`, error message names the path | Update path and error-message string. |
| `cognigy-mcp/pyproject.toml` | File's own location; `readme = "README.md"` resolved relative to its own directory | No content change needed inside the file — `readme = "README.md"` stays correct after a directory rename since it's a relative path. Only the file's *location* moves with `git mv`. |
| `cognigy-mcp/README.md:50,129,134` | Own-README self-references: `` Path to `cognigy-mcp/` source tree ``; `` cd cognigy-claude-plugin/cognigy-mcp ``; `` COGNIGY_VIBE_SOURCE_DIR=./cognigy-mcp `` | Update all three. Not in the plan's original grep-derived list — found on re-verification; the brief's search excluded paths under `cognigy-mcp/` itself, but this file is prose documentation (not code) and its self-references to the directory's own path still need updating on rename. Line 129 is inside the same `cd cognigy-claude-plugin/cognigy-mcp` clone instruction already flagged for the Catalog A repo rename — a directory rename touches this line a second, independent time. |

Every CI workflow row above is a hard string match (`grep '^version = ' cognigy-mcp/pyproject.toml`, path filters, etc.) — none of them resolve the path dynamically. If this rename is executed, all rows in this table must land in the **same commit**, or CI breaks between commits (release automation reading a now-nonexistent path).
