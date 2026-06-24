---
name: speckit-parallelize-agent-teams
description: |
  Spec Kit Parallelize It (Agent Teams variant) — execute a Spec Kit tasks.md with a Claude Code Agent Team that shares one working tree. Mirrors the task list into the team's shared task list, encoding [P] (parallel, file-disjoint) vs non-[P] (sequential barrier) and phase boundaries as task dependencies, then spawns N teammates (default 3) that self-claim ready work so every agent stays as busy as it can be. Each task is marked [x] in tasks.md the moment it completes. An optional phase-number argument caps how far to go: parallelize only up to that phase, then stop and hand back so a fresh session can resume — useful when a 15-phase task list would otherwise bloat one context window. Use after /speckit-tasks has generated a tasks.md AND when you want the Agent Teams engine (shared tree, no worktrees, no merges — for worktree isolation with sub-agents, use speckit-parallelize-subagents). Trigger on "/speckit-parallelize-agent-teams", "parallelize the spec kit tasks with an agent team", "run tasks.md with a team", "parallelize it with agent teams up to phase N".
argument-hint: "[agents=N] [phase=P] — both optional; defaults to 3 agents, all phases"
compatibility: "Requires a Spec Kit project (.specify/ + generated tasks.md) and Claude Code Agent Teams enabled (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1)"
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

This is the **Agent Teams** variant: all teammates share one working tree, relying on Spec Kit's `[P]` contract (different files) to keep concurrent work conflict-free — no worktrees, no merges. For per-task git-worktree isolation with merge-back instead, use **speckit-parallelize-subagents**.

You are the **team lead**. You build the shared task list, spawn teammates, and own `tasks.md` as the single source of truth. Teammates self-claim and implement; you encode the schedule, gate phases, and record completion.

## Step 0: Parse the invocation

From `$ARGUMENTS`, extract two optional values:

- **agents** — the number of teammates (and thus the hard concurrency cap; only this many teammates exist, so no more can ever run at once). Look for `agents=N`, `workers=N`, `N agents`. **Default 3.**
- **phase threshold** — the last phase to execute. Look for `phase=P`, `through P`, `until phase P`, `up to phase P`. **Default: none** → every phase. If given, execute phases `1..P` inclusive, then stop and hand back (Step 7). Only honor a threshold when explicitly given.

Any other text is free-form guidance — keep it in mind.

## Step 1: Preflight — confirm Agent Teams is available

Agent Teams is experimental and **off by default**. Check it is enabled (`echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`, or `env` in `~/.claude/settings.json`), and that the `TeamCreate`/`SendMessage` and `TaskCreate`/`TaskUpdate`/`TaskList` tools are available.

- If **enabled**, continue.
- If **not**, the env var is read at startup and can't be turned on mid-session. STOP and tell the user to add to `~/.claude/settings.json` and restart Claude Code:

  ```json
  { "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
  ```

  Then suggest: "If you'd rather not restart, **speckit-parallelize-subagents** does the same batching with worktree sub-agents and needs no flag."

## Step 2: Discover and load context

1. Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from the repo root. If missing or non-zero, STOP and report.
2. Parse the JSON for `FEATURE_DIR`.
3. Read these into context — you will **inline** them into the teammate spawn brief so teammates never read them themselves:
   - `FEATURE_DIR/tasks.md`, `FEATURE_DIR/spec.md`, `FEATURE_DIR/plan.md` (all required)
   - `.specify/memory/constitution.md` (if present)

   If any required file is missing, STOP.
4. From `plan.md`, extract `build_command` and `test_command`. If either is missing, ask the user before proceeding.

## Step 3: Parse tasks.md into a schedulable graph

Walk `tasks.md` top to bottom. For each task line `- [ ] TNNN ...` capture:

- **id** (`T044`), **status** (`[ ]` / `[x]`), and skip **removed** tasks (`~~T052~~` or `[REMOVED]`).
- **parallelizable** — `[P]` right after the id. Spec Kit's contract: a `[P]` task touches *different files* with *no dependency on an incomplete task* — that is exactly what lets `[P]` tasks run concurrently in one shared tree.
- **phase** — the enclosing `## Phase N:` header.
- **explicit dependencies** — ids in a `(Depends on T0xx)` note (a `[P]` task may still depend on an earlier `[P]` one, e.g. `T024 (Depends on T023)`).
- **has tests** — whether the phase contains a test task (decides whether `test_command` runs at its checkpoint).

Report:

```
Parsed tasks.md — engine: Agent Teams, agents: {N}, threshold: {phase P | none}
- Phase 1 Setup: {n} tasks ({p} parallel)
- Phase 2 Foundational: {n} tasks ({p} parallel)
  ...
Executing phases 1..{P or last}.
```

If there are no pending tasks within the threshold, STOP — nothing to do.

## Step 4: Prepare the branch

Teammates share **one** working tree, so all work lands on the current branch — no merging, but it must be clean.

- `git rev-parse --abbrev-ref HEAD`. If on `main`/`master`/`trunk`, `git checkout -b speckit/<feature-slug>`. Else stay.
- `git status --porcelain`. If dirty, STOP and report.

## Step 5: Build the team and its shared task list

The shared task list does the scheduling for you: teammates only claim tasks whose blockers are all resolved, so encoding `[P]`/barrier/phase structure as `blockedBy` edges means the team self-schedules correctly and stays busy.

1. `TeamCreate` with `team_name: "speckit-<slug>"`, a short `description`.
2. **Mirror each in-threshold, pending task into the team list** with `TaskCreate`, in file order. Put the task's full line text plus its Spec Kit id (e.g. "T044") and which user story / phase it belongs to in the description — teammates read this for *what* to do; the shared context comes from their spawn brief (Step 6). Then wire dependencies with `TaskUpdate addBlockedBy`, tracking as you go, per phase, the ids seen so far and the most recent **barrier** (non-`[P]`) task:
   - **explicit deps** → block on the team-task ids of its `(Depends on …)`.
   - **a `[P]` task** → also block on the most recent earlier **barrier** task in its phase (if any). It does *not* block on sibling `[P]` tasks, so siblings run together.
   - **a non-`[P]` (barrier) task** → block on **all** earlier tasks in its phase (it waits for the running `[P]` batch to drain) — and, being a barrier, every later task in the phase will block on it via the rule above.
3. **Add one checkpoint task per phase**, after its tasks: `TaskCreate` "Phase N checkpoint: build/test/commit", `addBlockedBy` = all of phase N's team-task ids, and immediately `TaskUpdate owner: "team-lead"` so teammates skip it (the lead runs checkpoints). Make every task in phase N+1 also `addBlockedBy` the phase-N checkpoint — that single edge enforces the phase barrier ("no user-story work until Foundational completes").

Because the threshold only mirrors phases `1..P`, there is simply no later work for teammates to claim — the threshold needs no extra logic.

## Step 6: Spawn teammates and run

Spawn `agents` teammates with the **Agent tool**, each with `team_name: "speckit-<slug>"`, a distinct `name` (e.g. `dev-1`), and `subagent_type: "general-purpose"` (it needs edit/write/bash — read-only types like Explore/Plan cannot implement). Give each the same **self-contained standing brief**:

```
You are a teammate on the Spec Kit build team. Work the shared task list:
claim the lowest-id available (pending, unowned, unblocked) task with TaskUpdate (owner = your name),
do exactly what its description says, then mark it completed and claim the next. Stay busy.

Touch ONLY the file path(s) named in a task — [P] tasks are partitioned by file so we never collide.
Do NOT edit tasks.md (the lead owns it). Do NOT read spec.md, plan.md, constitution.md — everything is below.

## Story / feature context
{paste the User Story sections from spec.md that the in-scope tasks reference}

## Technical context
{paste tech stack, project structure, paths, conventions from plan.md}

## Constitution
{paste constitution.md, or omit this heading if there is none}

## Build command
{build_command}

## Rules
- One task at a time; include the minimal wiring it needs (imports, DI, nav, build files).
- If a task pairs a test with the code it covers, write the test first.
- Run the build for what you touched if feasible before marking a task completed.
- If you can't finish a task, leave it in_progress and SendMessage the team-lead with "BLOCKED {id}: {what you need}" — never mark a blocked task completed.
- Do not claim a task whose description says "Phase N checkpoint" — those are the lead's.
```

Then run the coordination loop:

- Teammates self-claim and complete tasks; they go idle between turns (idle is normal — be patient, don't nudge unless it actually stalls progress).
- **You own `tasks.md`.** When a team task is marked completed (you'll see it in `TaskList` / idle notifications), flip its `- [ ] {id}` to `- [x] {id}` in `tasks.md`. This keeps one authoritative record and covers the known lag where a teammate forgets to mark the shared list — if `TaskList` shows a teammate idle with its task still `in_progress` but the file is clearly written, verify and mark it.
- **Run each phase checkpoint yourself** when its blockers clear (its blockedBy tasks are all completed): run `build_command`; if the phase had test tasks, run `test_command`; on failure STOP and report the implicated phase/tasks. Then `git add -A && git commit -m "feat(phase {N}): {title}"`, and `TaskUpdate` the checkpoint completed so the next phase unblocks.
- On a **BLOCKED** message: leave that team task `in_progress` and its `tasks.md` line `[ ]`; its dependents simply never unblock. Keep the rest running. Reassign with `SendMessage` if another teammate can take it.

## Step 7: Threshold reached or all phases done — hand back

When every in-threshold checkpoint is complete:

1. Shut the team down: `SendMessage` each teammate `{ "type": "shutdown_request" }`, wait for them to terminate, then `TeamDelete`.
2. Ensure every completed task is `[x]` in `tasks.md` and the last checkpoint is committed.
3. Report:

```
Done through Phase {P or last}.
- Tasks completed: {done}/{attempted}   (blocked: {ids + reasons, or "none"})
- Build: PASS    Tests: PASS (or "n/a")
- Branch: speckit/<slug>   Last commit: {hash}
{If a threshold stopped you early:}
- Stopped at the Phase {P} threshold. Remaining: Phases {P+1}..{last}.
  Resume in a FRESH session with: /speckit-parallelize-agent-teams phase={next milestone}
  (a fresh session keeps the next chunk's context clean — that's the point of the threshold).
```

If a threshold stopped you early, do not start the next phase — hand back so the user resumes fresh.

## Failure handling

- Build/test failure at a checkpoint → STOP, name the phase and likely tasks; work is committed up to the prior passing checkpoint.
- A teammate stalls (idle with an unfinished task and no progress) → `SendMessage` to re-engage it or reassign the task to another teammate; as a last resort, complete it yourself on the lead.
- Repeated BLOCKED on one task → report it, keep everything that doesn't depend on it running; never silently mark a blocked task done.
- Always `TeamDelete` before finishing (it fails if teammates are still active — shut them down first), so a later run can create a fresh team.
