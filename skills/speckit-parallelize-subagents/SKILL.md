---
name: speckit-parallelize-subagents
description: |
  Spec Kit Parallelize It (sub-agents + worktrees variant) — execute a Spec Kit tasks.md with parallel sub-agents, each isolated in its own git worktree branched from the current Spec Kit branch and merged straight back into it on completion. Walks the task list in order and keeps N sub-agents (default 3) continuously busy by batching the [P]-marked tasks into parallel chunks, while running non-[P] tasks as sequential barriers on the lead. Each task is marked [x] in tasks.md the moment its worktree merges cleanly. An optional phase-number argument caps how far to go: parallelize only up to that phase, then stop and hand back so a fresh session can resume — useful when a 15-phase task list would otherwise bloat one context window. Needs no experimental flags. Use after /speckit-tasks has generated a tasks.md AND when you want git-worktree isolation with sub-agents (not the shared-tree Agent Teams engine — for that, use speckit-parallelize-agent-teams). Trigger on "/speckit-parallelize-subagents", "parallelize the spec kit tasks with sub-agents", "run tasks.md in parallel worktrees", "parallelize it with subagents up to phase N".
argument-hint: "[agents=N] [phase=P] — both optional; defaults to 3 agents, all phases"
compatibility: "Requires a Spec Kit project (.specify/ + generated tasks.md) and a git repository"
metadata:
  author: "ai-coding-workflows"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

Consider the user input before proceeding (if not empty).

This is the **sub-agents + worktrees** variant. Each parallel task runs in its own git worktree (via the Agent tool's `isolation: "worktree"`), branched from the current Spec Kit branch, and you merge it back into that same branch when it finishes. It needs no experimental flags. If you instead want all teammates to share one working tree with no merging (Claude Code Agent Teams), use **speckit-parallelize-agent-teams**.

You are the **coordinator**. You parse the task list, dispatch worktree sub-agents, merge their branches back, keep them busy, and own `tasks.md` as the single source of truth. Sub-agents do the implementation work; you schedule, merge, gate, and record.

## Step 0: Parse the invocation

From `$ARGUMENTS`, extract two optional values:

- **agents** — the max number of concurrent sub-agents. Look for `agents=N`, `workers=N`, `N agents`, or a bare "use N". **Default 3.** This is a hard cap: never run more than this many sub-agents at once.
- **phase threshold** — the last phase to execute. Look for `phase=P`, `through P`, `until phase P`, `up to phase P`. **Default: none** → execute every phase. If a phase number is given, execute phases `1..P` inclusive, then stop and hand back (Step 7). Only honor a threshold when it is given explicitly; otherwise run the whole file.

Any other text is free-form guidance — keep it in mind.

## Step 1: Discover and load context

1. Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from the repo root. If it is missing or returns non-zero, STOP and report.
2. Parse the JSON for `FEATURE_DIR`.
3. Read these into your context — you will **inline** the relevant parts into sub-agent prompts so sub-agents never read them themselves:
   - `FEATURE_DIR/tasks.md` (required)
   - `FEATURE_DIR/spec.md` (required)
   - `FEATURE_DIR/plan.md` (required)
   - `.specify/memory/constitution.md` (if present)

   If any required file is missing, STOP.
4. From `plan.md`, extract `build_command` and `test_command`. If either is missing, ask the user before proceeding.

## Step 2: Parse tasks.md into a schedulable graph

Walk `tasks.md` top to bottom. For each task line `- [ ] TNNN ...` capture:

- **id** (`T044`), **status** (`[ ]` pending / `[x]` done), and skip any **removed** task (struck through, `~~T052~~`, or marked `[REMOVED]`).
- **parallelizable** — `[P]` present right after the id. Spec Kit's contract: a `[P]` task touches *different files* and has *no dependency on an incomplete task*. That guarantee is what lets independent worktrees merge back without conflicts.
- **phase** — the enclosing `## Phase N:` header and its kind (Setup / Foundational / User Story / Polish-or-Cross-Cutting).
- **explicit dependencies** — ids named in a `(Depends on T0xx)` note. A `[P]` task can still depend on an earlier task in its own group (e.g. `T024 [P] (Depends on T023)`); honor that — see "intra-batch dependencies" below.
- **has tests** — whether the phase contains any test task (used to decide whether to run `test_command` at its checkpoint).

Report the parse:

```
Parsed tasks.md — engine: sub-agents + worktrees, agents: {N}, threshold: {phase P | none}
- Phase 1 Setup: {n} tasks ({p} parallel)
- Phase 2 Foundational: {n} tasks ({p} parallel)
- Phase 3 US1: {n} tasks ({p} parallel)
  ...
Executing phases 1..{P or last}.
```

If there are no pending tasks within the threshold, STOP and report nothing to do.

## Step 3: Prepare the Spec Kit branch

Every worktree branches from this branch and merges back into it, so it must exist and be clean.

- `git rev-parse --abbrev-ref HEAD`. If on `main`/`master`/`trunk`, create `git checkout -b speckit/<feature-slug>`. Otherwise stay. Remember this as the **base branch** — all worktrees are created from it and all merges land on it.
- `git status --porcelain`. If dirty, STOP and report uncommitted changes.
- If `.gitignore` lacks `.worktrees/`, append it and commit (the Agent tool stores worktrees there).

## Step 4: Execute phase by phase, keeping N sub-agents busy

Process phases **in order**, `1` through the threshold (or the last phase). For each phase, schedule its tasks as a small dependency graph and keep up to `agents` worktree sub-agents in flight at all times that there is runnable `[P]` work.

### Readiness rule (recompute after every merge)

A pending, non-removed task **T** is *ready* when:

1. every phase before T's phase is fully done (phases are barriers — Spec Kit's "no user-story work until Foundational completes" etc.), **and**
2. every id in T's `(Depends on …)` note is done **and merged into the base branch**, **and**
3. every earlier **non-`[P]`** task in the *same phase* is done (a sequential task gates everything after it).

Among ready tasks:

- **`[P]` tasks run concurrently, each in its own worktree.** Dispatch ready `[P]` tasks to sub-agents up to the `agents` cap. As each sub-agent finishes, merge it (below), mark the task, and immediately dispatch the next ready `[P]` task — that "refill on completion" loop is what keeps every agent as busy as it can be.
- **A non-`[P]` task is a barrier.** It may only start when nothing is in flight (let all worktrees merge first), and nothing else starts until it finishes. Run barrier tasks **yourself, on the base branch** in the main working tree — no worktree, no merge. (Setup and Foundational phases are often entirely sequential; you may run those phases on the base branch directly.)

**Intra-batch dependencies:** if a ready `[P]` task depends on another task in the *same* batch (e.g. `T024` depends on `T023`), do NOT run them in two separate worktrees at once — the second worktree wouldn't contain the first's changes. Either give both to **one** sub-agent as an ordered chunk in a single worktree, or run the dependency first and only mark the dependent ready in the next round (after the dependency merges).

**Keeping agents busy with the Agent tool:** dispatch each worktree sub-agent with `isolation: "worktree"` and `run_in_background: true`, so you are re-invoked as each one completes and can merge + refill individually rather than waiting for a whole batch. If you prefer simplicity, a batch-and-wait loop (dispatch up to N, wait for all, merge all, refill) is acceptable — it just lets a fast agent idle until its batch-mates finish.

### Dispatching a task to a worktree sub-agent

Use the Agent tool with `isolation: "worktree"`. Give each sub-agent a **self-contained** prompt — it doesn't share your conversation, so inline everything it needs:

```
Implement Spec Kit task {id}: {full task line text}.

You are running inside a git worktree branched from the Spec Kit branch; your working
directory is the worktree root and all paths are relative to it. Touch ONLY the file
path(s) named in this task. Do not edit tasks.md. Commit your work in this worktree.

## Story / feature context
{paste the relevant User Story section from spec.md, or the phase's goal for Setup/Foundational/Polish}

## Technical context
{paste tech stack, project structure, paths, and conventions from plan.md}

## Constitution
{paste constitution.md, or omit this heading if there is none}

## Build command
{build_command}

## Rules
- Do exactly this task (and the minimal wiring it requires: imports, DI, nav, build files).
- If the task list pairs a test with the code it covers and both are in your chunk, write the test first.
- Run the build command for the parts you touched if feasible. Then commit with: feat({id}): {short summary}.
- Report "DONE {id}" with your branch name and a one-line summary, or "BLOCKED {id}: {what you need}". After 3 failed build attempts, report BLOCKED rather than thrash.
- If the inlined context is insufficient, report BLOCKED naming exactly what's missing. Do NOT read spec.md, plan.md, constitution.md, or tasks.md, and do not touch files outside this task.
```

### Merging a finished worktree (you own the base branch and tasks.md)

When a sub-agent reports **DONE {id}** with its branch, from the base branch run:

```bash
git merge <agent-branch> --no-edit
```

- Clean merge → flip `- [ ] {id}` to `- [x] {id}` in `tasks.md`. Because the lead owns `tasks.md` and sub-agents never touch it, there is one authoritative record.
- Conflict in `tasks.md` only (a sub-agent shouldn't touch it, but defensively): `git checkout --ours tasks.md`, `git add tasks.md`, continue the merge.
- Conflict in **code** files: this means two tasks that were supposed to be `[P]`/file-disjoint overlapped. STOP and report which task ids and files conflict — don't guess a resolution.

On **BLOCKED**, do not merge; leave the task `[ ]`, note the reason, and keep scheduling the rest. A blocked task's dependents simply never become ready. The sub-agent's branch stays available for inspection.

Because each new worktree is created from the *updated* base branch, later tasks automatically see everything merged before them.

### Phase checkpoint

After a phase's tasks are all done and merged (and nothing is in flight):

1. Run `build_command` on the base branch. If it fails, STOP and report which phase/tasks/merge is implicated.
2. If the phase contained test tasks, run `test_command`. If it fails, STOP and report.
3. Commit the phase checkpoint if there's anything staged: `git commit -am "chore(phase {N}): checkpoint"` (merges are already committed; this just captures any lead-run barrier work).

Then move to the next phase.

## Step 5: Threshold reached or all phases done — hand back

When you finish the last phase within the threshold (or the whole file):

1. Make sure no worktrees are still in flight and every merged task is `[x]` in `tasks.md`.
2. Report:

```
Done through Phase {P or last}.
- Tasks completed/merged: {done}/{attempted}   (blocked: {list ids + reasons, or "none"})
- Build: PASS    Tests: PASS (or "n/a")
- Branch: speckit/<slug>   Last commit: {hash}
{If a threshold stopped you early:}
- Stopped at the Phase {P} threshold. Remaining: Phases {P+1}..{last}.
  Resume in a FRESH session with: /speckit-parallelize-subagents phase={next milestone}
  (a new session keeps the next chunk's context clean — that's the point of the threshold).
```

If you stopped early because of a threshold, do not start the next phase — hand back so the user can resume fresh.

## Failure handling (any step)

- Build/test failure at a checkpoint → STOP, name the phase, tasks, and the merge that introduced it; leave work committed up to the prior passing checkpoint.
- Code merge conflict between two "parallel" tasks → STOP and report the ids/files; they were not actually file-disjoint.
- A sub-agent goes unresponsive or BLOCKED → leave its task `[ ]`, keep scheduling everything that doesn't depend on it; never merge or mark a blocked task done. Its branch remains for the user to inspect.
