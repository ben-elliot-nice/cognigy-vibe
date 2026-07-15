---
name: work-on-issue-custom
description: Use when asked to work an issue by number in ben-elliot-nice/cognigy-vibe (cognigy-claude-plugin) - drives setup (worktree from origin/dev), research (tests, root cause, dedup search), an approval-gated approach, implementation, PR creation, a review-fix polling loop, and post-merge cleanup.
---

# Work on Issue (Custom)

**Repo-specific.** Built for `ben-elliot-nice/cognigy-vibe` (local clone: `cognigy-claude-plugin`). Before doing anything, verify `git remote get-url origin` matches — if it doesn't, stop and tell the user this skill's assumptions (branch names, test command, PR conventions) won't apply here.

**Usage:** invoked with an issue number/ID as the argument, e.g. `/work-on-issue-custom 123`.

**Announce at start:** "I'm using the work-on-issue-custom skill to work issue #<ID>."

## 1. Setup

1. Pull the issue: `gh issue view <ID>` (title, body, labels, comments) to understand scope.
2. `git fetch origin dev` — **do not** `git pull` or touch local `dev`; someone may have work in progress on it.
3. Create a worktree tracking the issue, branched from `origin/dev` (not local `dev`):
   - Branch name: `feat/<ID>-<slug>` (per this repo's CLAUDE.md convention).
   - Use `superpowers:using-git-worktrees` for the mechanics, but override its directory-selection step: **this project's worktrees live at `.claude/worktrees/`** (already gitignored), not `.worktrees/`. Don't ask the user about location — CLAUDE.md already specifies it.
   - Concretely: `git worktree add .claude/worktrees/feat/<ID>-<slug> -b feat/<ID>-<slug> origin/dev`.
   - **Do not rely on `EnterWorktree`'s default branching alone** — its `fresh` baseRef branches from `origin/<default-branch>`, and this repo's default branch is `main`, not `dev`. There is no `worktree.baseRef` override in `.claude/settings.json`, so `EnterWorktree name: feat/<ID>-<slug>` with no further action will silently create the branch from `origin/main` — even right after `git fetch origin dev`. Confirmed empirically on issue #256's worktree setup.
   - If you use `EnterWorktree`, verify the base immediately after, before any work:
     ```bash
     git merge-base --is-ancestor origin/dev HEAD && echo "OK: based on dev" || echo "WRONG BASE"
     ```
     If it reports the wrong base, rename/discard that branch and recreate via the explicit `git worktree add ... origin/dev` command above rather than continuing on it.
4. Enter the worktree (`EnterWorktree` with the created path, or `cd` if working via raw git).

## 2. Research

1. Run the test suite for a clean baseline: `cd cognigy-vibe-mcp && uv run pytest tests/ -v`. If it's not clean, report failures to the user before proceeding — don't assume they're pre-existing.
2. Read the issue and investigate the codebase to validate it and identify the root cause. Don't take the issue's framing at face value — confirm the actual mechanism.
3. Search for related issues to catch duplication or regressions:
   ```bash
   gh issue list --repo ben-elliot-nice/cognigy-vibe --search "<keywords from the issue>" --state all
   ```
   - **Open issues** with similar surface area → possible duplicate.
   - **Closed issues** with similar surface area → possible regression of a prior fix, or a fix that didn't fully address the root cause.
4. Report to the user: any duplication risk found (which issue #, why it looks related).
5. Report to the user: any regression/missed-fix risk found (which issue #, what it fixed, why this looks like the same root cause resurfacing).

## 3. Approach — approval gate

Present the three options below to the user and get an explicit choice before writing implementation code. Recommend one based on your research, but don't proceed without confirmation.

1. **Complex, large change surface** → `superpowers:brainstorming`, then `superpowers:writing-plans`.
2. **Medium complexity, root cause obvious, likely multiple files** → `superpowers:writing-plans` directly.
3. **Low complexity, small change surface**:
   - Write a test that reproduces the root cause first. If a test genuinely can't isolate it, explain why to the user before proceeding without one.
   - Run the suite and confirm the new test fails for the expected reason.
   - Implement the fix directly (no plan doc).
   - Run the suite and confirm it now passes, with no other regressions.

**Note:** options 1 and 2 invoke `writing-plans`, which enforces TDD as part of the skill. Option 3 does not invoke that skill, so TDD discipline (failing test → fix → passing test) must be enforced manually as written above — don't skip the red step.

## 4. Push

Once code is written, tested, and committed: `git push -u origin feat/<ID>-<slug>`.

## 5. Open the PR

`gh pr create --base dev ...` — both the PR title and body must reference the issue number. Include `Closes #<ID>` in the body so GitHub auto-closes it on merge (per CLAUDE.md).

## 6. Review loop — approval gate

Ask the user for permission before entering this loop. If approved:

- **Trigger**: this skill does **not** auto-comment `@claude-review` — wait for a human (the user, or someone else) to comment it manually on the PR to kick off the automated CI reviewer set up in `.github/workflows/claude-code-review.yml`.
- **Poll** every 5 minutes for up to 1 hour (12 checks) for a new review signal. Use an until-loop (e.g. via the `Monitor` tool, or a bash loop respecting this session's sleep constraints) rather than a raw long sleep.
- **Exit condition** — the CI reviewer posts findings as a plain PR comment via `gh pr comment`, and additionally leaves a formal `gh pr review --approve` when it found no critical/important issues. Check both, since either can be the terminal signal:
  - A formal GitHub review with state `APPROVED` (`gh pr view --json reviews`), **or**
  - A PR comment containing LGTM-style approval language (e.g. "looks good", "LGTM") — covers a human reviewer approving via comment instead of a formal review.
- **If a review arrives with findings (not an approval)**: read the findings, implement fixes, commit, push. Then start a **new** 5-min/1-hour waiting window for the follow-up review — don't carry over the old clock.
- **If no review arrives within an hour of waiting**: exit the loop and report to the user that no review was received, rather than waiting indefinitely.

## 7. Post-merge cleanup

**Trigger**: the user tells you the PR was merged and asks for cleanup (e.g. "pr was merged, clean up").

1. Confirm the merge: `gh pr view <PR#> --json state,mergedAt` should show `MERGED`.
2. On the issue: add the `pending release` label (`gh issue edit <ID> --add-label "pending release"`); remove the `wip` label if present (`gh issue edit <ID> --remove-label wip`) — check current labels first (`gh issue view <ID> --json labels`) since `wip` may not always be set.
3. Exit the worktree: `ExitWorktree` with `action: "keep"` if this session entered an existing worktree (not one it created via `EnterWorktree`) — it will refuse to remove one it didn't create. Otherwise `action: "remove"` works directly.
4. Remove the worktree directory: `git worktree remove .claude/worktrees/feat/<ID>-<slug>`.
5. Delete the local branch: `git branch -d feat/<ID>-<slug>` (expect a "not yet merged to HEAD" warning if local `dev` hasn't been fast-forwarded — this is expected since the merge happened on the remote, not local `dev`; the PR's `MERGED` state from step 1 is the source of truth).
6. Delete the remote branch: `git push origin --delete feat/<ID>-<slug>`.
