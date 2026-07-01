---
name: git-commit
description: |
  Commit all uncommitted changes in the current git repo as one or more atomic
  Conventional Commits. Use when the user says "/git-commit", "commit my changes",
  "commit the work", "make commits for what I did", or otherwise asks Claude to
  commit pending work. Splits unrelated changes into separate commits, writes
  Conventional Commit messages, and stops at local commits — does not branch or push.
argument-hint: "[optional context about what was changed]"
---

# Git Commit

## Overview

Look at every uncommitted change in the current repo (staged, unstaged, untracked) and produce one or more atomic Conventional Commits. Group related changes together; split unrelated changes into separate commits. The commit messages must read as if a human developer wrote them — no Claude co-author line, no "Generated with…" footer, no AI-attribution.

This skill commits. It does **not** branch, push, reset, rebase, or run any other git operation.

## Workflow

1. **Verify repo:** `git rev-parse --is-inside-work-tree`. If not in a git repo, stop and report.
2. **Collect state in parallel** (one message, multiple Bash calls):
   - `git branch --show-current`
   - `git status --porcelain` (never use `-uall`)
   - `git diff` (unstaged tracked changes)
   - `git diff --cached` (staged changes)
   - `git log --oneline -20` (style reference for messages)
3. **Branch check:** if branch is `main`, `master`, or `develop`, print a one-line warning (`Note: committing directly to <branch>.`) and continue.
4. **Empty check:** if `git status` shows nothing, report `Nothing to commit.` and stop.
5. **In-progress check:** if mid-rebase / mid-merge / mid-cherry-pick (look for `.git/MERGE_HEAD`, `.git/rebase-*`, `.git/CHERRY_PICK_HEAD`), stop and tell the user.
6. **Read diffs** — enough of each to understand intent. For large diffs, sample representative hunks. Don't skim past anything that determines the commit type.
7. **Skip likely-secret files** — never stage or commit files matching:
   - `.env`, `.env.*`
   - `*credentials*`
   - `*.pem`, `*.key`
   - `id_rsa*`

   List them to the user and ask whether they actually want them committed before proceeding.
8. **Group changes by intent.** One concern per commit. Decision test: *"Could I revert just this commit and have a coherent codebase?"* If no, split. Examples:
   - New file + the import that wires it in → 1 commit.
   - Rename + every reference update → 1 commit.
   - Feature + an unrelated typo fix → 2 commits.
   - Migration + the code using the new schema → 2 commits (migration first).
   - **Two unrelated changes inside the same file → 2 commits** (see "Splitting Within a File").
9. **Use the calling agent's context.** If `$ARGUMENTS` (or any context the calling agent passed) is non-empty, treat it as ground truth for *why* changes were made, type/scope selection, grouping decisions, and commit-body content. If empty, infer from diffs + recent `git log` style.
10. **For each commit group:**
    - If current staging conflicts with the group plan, unstage with `git restore --staged .`.
    - Stage exactly the changes in this group:
      - **Whole-file groups:** `git add <file1> <file2> ...`.
      - **Hunk-level groups (same file split across commits):** see "Splitting Within a File" below.
    - **Never** `git add -A`. **Never** `git add .`.
    - Pick the `type(scope): description` per the rules below.
    - Commit with the HEREDOC pattern (see "Commit Message Format"). **No co-author line. No AI-attribution. No tooling footer.**
    - If a pre-commit hook fails: read the failure, fix the underlying issue, re-stage, make a **new** commit. Never `--amend`. Never `--no-verify`.
11. **Final report:** run `git status` and print one line per commit (`<short-sha>  <subject>`).

## Conventional Commits

**Format:** `type(scope): description`

- Imperative mood, lowercase start, no trailing period.
- Optional body after a blank line — explains *why*, not what.
- Breaking change → append `!` to the type: `feat(api)!: rename foo to bar`.

### The 10 types

| Type | When |
|---|---|
| `feat` | Adds new user-facing capability |
| `fix` | Corrects wrong behavior (a bug) |
| `perf` | Same behavior, measurably faster/lighter — performance was the goal |
| `refactor` | Code restructure with no behavior change (rename, extract, simplify) |
| `style` | Whitespace/formatting/semicolons only — NOT visual UI styling |
| `test` | Test-only changes (adding, fixing, removing tests) |
| `docs` | Documentation only (README, KDoc, comments, MD files) |
| `build` | Changes that affect the shipped build (Gradle, deps, packaging) |
| `ci` | CI config only (GitHub Actions, workflows, pipelines) |
| `chore` | Repo housekeeping that doesn't ship (lint config, .gitignore, dotfiles, scripts) |
| `revert` | Reverts a previous commit |

### Picking rule (top-down, first match wins)

1. **Does user-facing behavior change?**
   - New capability → `feat`
   - Corrects bug → `fix`
   - Faster/lighter, same result, perf was the goal → `perf`
2. **No behavior change. What changed?**
   - Production code structure only → `refactor`
   - Whitespace/formatting/semicolons only → `style`
   - Tests only → `test`
   - Docs/comments only → `docs`
   - Shipped build inputs (Gradle deps, version catalogs, packaging) → `build`
   - CI workflows only → `ci`
   - Reverts an earlier commit → `revert`
   - Anything else maintenance → `chore`

### Confusion-point clarifications

- `feat` written together with its tests → still **one** `feat` commit. `test` is reserved for test-only commits.
- `chore(deps)` vs `build(deps)`: pick `build` when the dependency ships in the artifact (libraries, Gradle plugins). Pick `chore` for tooling that doesn't ship (eslint, ktlint, pre-commit hooks).
- `refactor` that happens to speed things up → only use `perf` if perf was the *goal*. Otherwise it's `refactor`.
- `style` is **not** UI styling. UI changes are `feat` or `fix`. `style` is purely the formatter.

### Scope

Optional. Use the module/area actually changed (e.g., `auth`, `network`, `ui`, `deps`, `nav`, `data`). One scope per commit; if the change spans many areas, leave the scope off.

### Examples

| Change | Message |
|---|---|
| Add login screen | `feat(auth): add login screen with email/password` |
| Fix crash on null user | `fix(profile): handle null user in profile screen` |
| Extract use case | `refactor(auth): extract ValidateCredentialsUseCase` |
| Update Ktor version (ships) | `build(deps): bump Ktor to 3.1.0` |
| Tighten ktlint config | `chore: tighten ktlint rules` |
| Add ViewModel tests | `test(auth): add LoginViewModel unit tests` |
| Fix typo in README | `docs: fix typo in setup instructions` |
| Speed up list rendering | `perf(home): cache item keys to reduce recomposition` |
| Reformat with new style guide | `style: apply ktlint formatting` |
| Update GitHub Actions cache | `ci: bump actions/cache to v4` |
| Roll back broken merge | `revert: revert "feat(auth): add login screen"` |

## Atomic Commit Discipline

One logical change per commit. Not "save progress."

**Decision test:** *"Could I revert just this commit and have a coherent codebase?"* If no, split it.

| Scenario | Commits |
|---|---|
| New file + its test | 1 commit |
| Rename + update all references | 1 commit |
| New feature + unrelated formatting | 2 commits |
| Migration + code using new schema | 2 commits (migration first) |
| Two unrelated bug fixes | 2 commits |

**Never commit broken compilation.**

## Splitting Within a File

When a single file contains two unrelated changes that must land in separate commits, **don't fall back to one combined commit** — split at the hunk level. This works whenever the changes touch **different, non-overlapping line ranges**.

The technique uses `git apply --cached` with a hand-crafted patch. `git add -p` is interactive and not usable here.

**Sequence:**

1. Get the full diff for the file:
   ```bash
   git diff -- <file> > /tmp/full.diff
   ```
2. Read `/tmp/full.diff` and decide which hunks (`@@ ... @@` blocks) belong to commit A vs commit B.
3. Build `/tmp/group_a.diff` containing **only**:
   - The `diff --git`, `index`, `---`, `+++` header lines from the original.
   - The hunks assigned to group A (each starting with its own `@@` line).
4. Stage just group A:
   ```bash
   git apply --cached /tmp/group_a.diff
   ```
5. Sanity-check: `git diff --cached -- <file>` should show only group A; `git diff -- <file>` should show only group B.
6. Commit group A with its Conventional Commit message.
7. Stage the rest of the file:
   ```bash
   git add <file>
   ```
   The working tree still holds group B because `git apply --cached` only touches the index. Now `git add` stages those remaining lines against the new HEAD.
8. Commit group B.
9. Run `git diff` and `git diff --cached` — both must be empty for that file.

**Verifying patches before applying:**
```bash
git apply --cached --check /tmp/group_a.diff   # dry-run; non-zero exit = patch won't apply cleanly
```
If `--check` fails, the hunks were split incorrectly (line numbers off, missing context). Rebuild the patch.

**Hunk header reference** — hunks use this format:
```
@@ -<old_start>,<old_count> +<new_start>,<new_count> @@ optional-section-header
 context line
-removed line
+added line
 context line
```
Don't edit the numbers — copy each hunk verbatim from the original diff. Keep at least the 3 lines of context git already includes.

**When this does NOT work — fall back to a single combined commit:**
- Hunks overlap on the same lines (e.g., a refactor and a feature both rewrote the same function body).
- The file is a binary file or rename/delete (no line-level hunks to split).
- Splitting would leave one commit with broken compilation.

In those cases, commit the file once with a message that names the dominant intent and mention the secondary change in the body.

## Calling-Agent Context

If the calling agent passed extra context as `$ARGUMENTS`, treat it as ground truth about what changed and why. Use it to:

- Pick more accurate types and scopes.
- Resolve grouping ambiguity when diffs alone aren't enough.
- Inform the commit body (the *why*).

If no context is provided, infer everything from the diffs plus the recent `git log` style.

## Commit Message Format

Always use a HEREDOC. The message must look fully human-authored — **no co-author line, no "Generated with Claude" footer, no AI-attribution, no tooling notice**:

```bash
git commit -m "$(cat <<'EOF'
feat(auth): add login screen with email/password

Wires the new LoginScreen into the auth nav graph.
EOF
)"
```

Subject line first. Blank line. Optional body explaining *why*. Nothing else.

## Safety

- Never `git add -A`. Never `git add .`. Always stage explicit files.
- Skip likely-secret files; warn the user instead of staging them.
- Never `--no-verify`. Hook failure → fix the underlying issue + make a **new** commit (never `--amend`).
- Do not push. This skill stops at local commits.
- Protected branch (`main`/`master`/`develop`) → print a one-line warning and continue.
- Never include a Claude co-author line, AI-attribution, or tooling footer in any commit message.

## Edge Cases

- **Nothing to commit** → report and stop.
- **Mid-rebase / mid-merge / mid-cherry-pick** → stop and tell the user.
- **Pre-commit hook fails twice** for the same group → stop and report; don't loop.
- **Detached HEAD** → warn explicitly before committing.
- **Renames** that git tracks as delete + add → stage both sides together so git records the rename.

## Red Flags

| Thought | Reality |
|---|---|
| "I'll just `git add -A`" | No — stage explicit files only. |
| "These two changes are loosely related" | Split them. The revert test decides. |
| "Pre-commit hook is annoying, `--no-verify`" | No. Fix the hook failure. |
| "Commit failed, let me `--amend`" | No. New commit each time. |
| "Big mixed diff is one feature" | Read it again. Group by intent. |
| "I'll add a co-author line just this once" | No. The message must look human-authored. |
