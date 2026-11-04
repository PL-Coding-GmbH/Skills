---
name: finalize
description: Finish a chunk of work so it is actually ready to push. Runs Principle VII gates 3 and 4 in cost order and fixes what they surface — instrumentation suite on a device → combined coverage against thresholds → Figma parity for any screens named with --screens → /verify code review — then reconverges whatever the fixes invalidated. Ends in READY_TO_PUSH or BLOCKED, never a partial claim.
argument-hint: "[--base=<ref>] [--screens=<Screen>,...]"
user-invocable: true
disable-model-invocation: true
---

# /finalize — make a chunk of work push-ready

You are the **main agent**. Sub-agents under `.claude/agents/` cannot dispatch
further sub-agents, so every fan-out happens from your context.

## What this is, and what it is not

`.claude/hooks/foldio-verify/push-gate.sh` **decides**; it deliberately never
**performs**. It reads artifacts Gradle already produced, denies in
milliseconds, and prints the exact commands that would clear the denial —
because a long-running hook that times out does not block, so the gate would
be weakest on exactly the biggest changes.

`/finalize` is the performer on the other side of that split. It runs the
long, visible, resumable work the gate names, fixes what fails, and stops
when the gate would allow the push.

Two rules follow from that, and they are not negotiable:

- **Never restate a number, threshold, module kind, module list or refresh
  command that `scope.sh` and `status.sh` already report.** Ask them. A finalize that prints different commands than the gate does is
  worse than no finalize, because it sends the user to run something that
  will not clear the denial.
- **Never invent scope.** Modules come from `scope.sh`, the screens to check
  against Figma come from `--screens`, findings come from `/verify`.

Gates 1 and 2 (compiles, JVM unit tests) are already covered by the Stop and
SubagentStop hooks, so `/finalize` does not run them as a step of their own.
They reappear only inside Stage 7, where a fix may have broken them.

## Arguments

The user invoked: `/finalize $ARGUMENTS`

`$ARGUMENTS` is optional. Recognized flags, any order, both optional:

- `--base=<ref>` — git ref the chunk of work is measured against. Default:
  `master`. It is exported as `FOLDIO_BASE_BRANCH` for every hook helper
  **and** passed to `/verify` as `--base=<ref>`, so both halves look at the
  same diff.
- `--screens=<Screen>[,<Screen>...]` — the screens to check against Figma.
  Comma-separated, no spaces. Each entry is a composable name
  (`VerifyWaitingScreen`) or a path to its file. Omit the flag and Stage 5
  does not run at all.

Any other token, or a malformed flag, → emit `INVALID_INVOCATION` (Stage 8
format) with the offending token in `Notes` and stop.

## The attempt budget

Every fixing stage (3, 4, 5, 6) and the reconverge (7) gets **at most 3
fix-and-recheck cycles**. This mirrors `FOLDIO_MAX_BLOCKS=3` in
`stop-gate.sh`, and for the same reason: a gate the agent cannot satisfy must
end loudly rather than grind.

On the 4th failure of a stage, stop that stage, record it under `Remaining`
with the verbatim command that reproduces it, and **carry on to the next
stage anyway** — a coverage gap that needs a large test suite should not
prevent the review from running. A stage that exhausted its budget forces the
final verdict to `BLOCKED`.

Never silently reduce scope to make a stage pass. If you skip something,
`Remaining` says so.

## The scripts this skill drives

Two read-only reporting scripts under `.claude/hooks/foldio-verify/`. Both
take plain arguments, print a stable format, and always exit 0 — call them
directly, and never source `lib/*.sh` yourself:

- `sh .claude/hooks/foldio-verify/scope.sh [--base=<ref>]` — prints `MODULES`
  (what changed) and `SCOPE` (what the change reaches).
- `sh .claude/hooks/foldio-verify/status.sh <module> ...` — prints the
  coverage table the push gate decides from.

Neither is a gate and no hook calls either of them; that separation is what
stops a reporting script from being able to change a verdict.

Never set `FOLDIO_DRY_RUN`, `FOLDIO_STOP_FORCE_MODULES`,
`FOLDIO_PUSH_FORCE_MODULES` or `FOLDIO_SKIP_*`. Those are test seams. Setting
one during a finalize produces a run that verified nothing and says it did.

---

## Stage 0 — Parse arguments

1. Tokenize `$ARGUMENTS`. Empty → default (`base=master`).
2. Match each token against `--base=<ref>` or `--screens=<list>`. Anything
   else → `INVALID_INVOCATION` (Stage 8 format) and stop.
3. Confirm the ref resolves: `git rev-parse --verify --quiet <ref>` or
   `origin/<ref>`. Neither → `INVALID_INVOCATION` with "base ref does not
   exist".
4. `--screens=` with an empty value → `INVALID_INVOCATION`. Absent is how you
   say "no Figma check"; empty is a typo.

## Stage 1 — Scope

```bash
sh .claude/hooks/foldio-verify/scope.sh --base=<ref>
```

Output:

```
MODULES :core:sync :feature:auth:data
SCOPE :app :core:sync :feature:auth:data :feature:auth:presentation
```

`MODULES` and `SCOPE` are different lists used for different things, and
mixing them up is a real failure:

- **`MODULES` is what changed.** Coverage is measured over this, because a
  module's coverage is a property of its own code.
- **`SCOPE` is what the change reaches.** Gradle builds a module's
  dependencies, never its dependents, so Stage 7 compiles and unit-tests this
  wider list — a signature change in `:core:domain` breaks consumers whose own
  tasks the narrow list never runs.

`scope.sh` already folds in the cases worth knowing about: it covers
committed, uncommitted and untracked work (the right scope for a chunk that
is about to be pushed but may not be committed), and it widens to every module
when a version-catalog, convention-plugin or root build file changed.

An `ERROR` line instead of `SCOPE` → report it and stop; do not fall back to
a narrower scope. Empty `MODULES` → emit `NOTHING_TO_FINALIZE` (Stage 8
format) and stop.

Record both lists; every later stage refers back to them.

## Stage 2 — Baseline read (free, no Gradle)

```bash
sh .claude/hooks/foldio-verify/status.sh <module> <module> ...
```

Pass Stage 1's `MODULES` list literally — shell state does not survive between
Bash tool calls, so there is no variable to carry.

This is read-only by construction and takes milliseconds. Its table is the
authoritative to-do list for Stages 3 and 4 — do not derive your own.

Handle the structural rows before spending anything on a device:

- `no-jacoco` → run the `android-jacoco-setup` skill for that module. Nothing
  downstream can measure it until this is done.
- `no tests` (production code, no `src/test` and no `src/androidTest`) → the
  module needs a suite written from scratch. Treat it as a Stage 4 coverage
  gap, and expect it to consume the whole budget.
- `no sources` → nothing to do, ignore.

## Stage 3 — Instrumentation suite on a device

This runs **before** coverage, not after it, and the ordering is load-bearing:
`foldioCombinedCoverage` dependsOn `testDebugUnitTest` only. It merges
whatever `.ec` files happen to be on disk. Produce the report first and you
get a unit-test-only number wearing a combined report's name.

Scope: every module in `MODULES` whose kind (the Stage 2 table's KIND column)
is `combined` or `instrumentation` and whose row is not already `ok`.
Nothing to run → skip to Stage 4.

1. **Get a device.** If `adb devices` shows no online emulator:
   ```bash
   python3 .claude/skills/android-instrumentation-coverage/scripts/select_emulator.py --min-sdk 26
   android emulator start <avd>
   ```
   Poll `adb devices` for up to 3 minutes. Follow the `android-cli` skill if
   it will not boot.

2. **Run the suites strictly one at a time, each through the device lock:**
   ```bash
   ANDROID_SERIAL=<serial> python3 \
     .claude/skills/android-combined-test-coverage/scripts/device_lock.py \
     -- ./gradlew <module>:connectedDebugAndroidTest
   ```

   **Do not parallelize this stage.** Worktree fan-out is the right instinct
   for CPU-bound per-module work and the wrong one here: two connected runs
   for the same test package on one emulator destroy each other's execution
   data, and the loser dies with "Process crashed" having produced test
   results but no `.ec`. That is precisely the `device-run-no-data` state the
   push gate reports, and it is invisible until the gate reports the module as
   never having run.

3. **Fix failures here**, not later. Use `superpowers:systematic-debugging`
   for anything that is not obvious, and `android-integration-testing` /
   `android-ui-testing` for the conventions the fixed test must follow. A
   failing instrumentation test is a fact; do not weaken an assertion or add
   `@Ignore` to get past this stage.

Re-run only the module that failed. Budget 3.

## Stage 4 — Coverage report and thresholds

1. **Produce the reports.** `status.sh` already prints the exact refresh
   command for every module without a current result, under "To refresh the
   modules with no current result". Run those, verbatim. They come from the
   same renderer `push-gate.sh` denies with, which is the only reason the
   commands here cannot drift from the ones that clear the denial.

   For `combined` / `instrumentation` modules this is
   `<module>:foldioCombinedCoverage`, and it must be **its own Gradle
   invocation**, separate from Stage 3's connected run. Asking for both in one
   call lets Gradle write the report before the connected tests have deposited
   their `.ec` files.

   The renderer prints a literal `ANDROID_SERIAL=<serial>` placeholder in the
   connected-run line. Substitute the real serial from `adb devices`; Stage 3
   has already run that half, so here you normally need only the second
   (coverage) line it prints.

2. **Re-read `sh .claude/hooks/foldio-verify/status.sh <module> ...`.** Every
   row must be `ok`.

3. **For each `low` row**, `render_coverage.py` (already invoked by the gate,
   and printable directly) names the weakest classes. Write real tests for
   them:
   - pure logic, ViewModels, mappers, validators → `android-unit-testing`
   - anything crossing a database / network / clock / WorkManager boundary →
     `android-integration-testing`
   - Compose UI and E2E flows → `android-ui-testing`

   Do not chase the percentage. Tests written to move a number and assert
   nothing will come back as `/verify` findings in Stage 6, and they make the
   module harder to change. `:core:crypto` is at 100% in `thresholds.json` —
   for security-critical algorithmic code the number is a floor on
   *behaviour*, not on lines executed.

4. New tests invalidate the report that was just produced (`coverage.py`
   records the content it measured, not just an mtime). Re-run **only that
   module's** refresh commands — and its device pass too, but only if the new
   tests live under `src/androidTest`.

Budget 3.

## Stage 5 — Figma parity for the screens you named

**Runs only when `--screens=` was passed.** No flag → skip the stage entirely
and record why in the report. Never go looking for screens yourself: an
unasked-for Figma pass burns emulator-free but expensive render cycles on
screens the user did not change, and a screen the user cares about is one they
will name.

For each entry in `--screens=`:

1. **Resolve it to a file.** A path is used as-is. A bare composable name is
   resolved by searching the modules from Stage 1:
   ```bash
   grep -rln "fun <Screen>(" --include='*.kt' <module-dir>/src/main
   ```
   Zero matches, or more than one → stop and ask which file. Do not pick.

2. **Read the file and collect its screen-state `@Preview` functions**, and
   for each one the Figma frame URL in the inline comment directly above the
   `@Preview` annotation (one blank line between them is fine — that is the
   house style).

3. **A named screen whose previews carry no Figma URL is a hard stop for that
   screen**, not a guess and not a search. Report it as
   `NO FRAME — <Screen>` and move to the next one. `android-preview-figma-verify`
   refuses to guess a pairing, and you must not guess one for it.

4. **Make sure Android Studio has synced.** `render-compose-preview` renders
   from Studio's VFS, not from disk. Stages 3 and 4 just edited files from the
   CLI, so without a reload you get a byte-identical render of the pre-fix
   source and a match that means nothing. If you cannot confirm a sync, report
   Stage 5 as **NOT RUN — Studio out of sync** and ask the user to reload. A
   false match here is worse than no check.

5. **Invoke `android-preview-figma-verify` once per (preview, frame) pair**,
   passing both sides explicitly: the file plus the preview composable name,
   and the Figma URL. It reports only; it never edits.

6. **Fix the deviations it grades as significant**, following
   `android-compose-components` / `android-presentation-mvi`. Figma is the
   source of truth. A deviation you keep on purpose gets written down in the
   report with its reason — an undocumented deviation is a failure of this
   stage.

Budget 3.

## Stage 6 — Code review

Invoke `/verify --base=<ref>` with the same ref Stage 0 resolved.

Act on its verdict:

- `FIXES_REQUIRED` → fix every surviving finding. `/verify` has already
  filtered to HIGH-confidence `BLOCKER` / `MAJOR` at its validator stage and
  then audited them, so everything that reaches you is in scope. The one way
  to close a finding without changing code is to quote the discovered rule
  that contradicts it — record that quote in the report.
- `TESTS_FAILED` → fix the tests. This is a fact, immune to audit filtering.
- Findings prefixed `[UNVERIFIED]` → **report, do not auto-fix.** The audit
  could not confirm them cheaply, so a meaningful share are false positives
  and chasing them churns code for nothing. They go in the report for the
  user to judge.
- `PASS` / `SKIPPED` → done.

Re-run `/verify` with the same args after fixing, per its own re-invocation
contract. Budget 3 invocations total.

## Stage 7 — Targeted reconverge

Every fix made in Stages 3–6 invalidated something earlier. Without this
stage `/finalize` finishes green and the push gate still denies with "no
coverage report matching the code on disk".

Reconverge only what was actually invalidated. Diff the working tree against
the state at Stage 1 to get `fixed_files`, then:

| what changed | what to re-run |
|---|---|
| any `.kt` / `.kts` | `<module>:assembleDebug` + `<module>:testDebugUnitTest` for every module in `SCOPE` (`:build` + `:test` for JVM-only modules). Usually warm from the Stop hook. |
| production code in a measured module | that module's refresh command, as printed by `status.sh` |
| …and that module needs a device | its `connectedDebugAndroidTest` through `device_lock.py` first |
| a UI source in a screen Stage 5 verified | re-verify only that screen's previews |
| anything at all | one more `/verify --base=<ref>` |

Exit condition, both parts required:

- `sh .claude/hooks/foldio-verify/status.sh <module> ...` shows every row
  `ok`, and
- the last `/verify` returned `PASS` or `SKIPPED` **against the current tree**
  — not against the tree as it was before the Stage 6 fixes.

Budget 3 passes over the table. A fix in the reconverge that invalidates the
reconverge is the signal to stop and hand back, not to keep going.

## Stage 8 — Verdict

```
## Verdict
READY_TO_PUSH | BLOCKED | NOTHING_TO_FINALIZE | INVALID_INVOCATION

## Coverage
<the final status.sh table, verbatim>

## Instrumentation
<one line per module: PASS <module> or FAIL <module> + failing test FQNs; or "not run — no module needs a device">

## Figma
<one line per verified preview: MATCH, or the deviation and how it was resolved;
 documented deviations with their reason;
 NO FRAME lines for named screens whose previews carry no Figma URL;
 or "not run — <--screens not passed / Studio out of sync>">

## Review
<surviving /verify findings and how each was resolved, plus every [UNVERIFIED] finding>

## Remaining
<every stage that exhausted its budget, with the verbatim command that reproduces it>
```

`READY_TO_PUSH` requires **all** of: `Coverage` fully `ok`, `Instrumentation`
with no FAIL, `Figma` with no unresolved significant deviation, `Review` clear
of BLOCKER/MAJOR, and `Remaining` empty. Anything else is `BLOCKED`. There is
no partial pass and no "green apart from".

`/finalize` does **not** commit and does **not** push. On `READY_TO_PUSH` with
a dirty tree, say so and suggest `/git-commit` — the push gate is the
authority on whether the work may leave the machine, and this skill should not
be the thing that decides the work is committable.

## Honesty contract

The whole point of this skill is that its verdict can be trusted. So:

- Never report a stage as passed that you did not run.
- Never narrow scope to reach `READY_TO_PUSH`.
- Never weaken a test, add `@Ignore`, or lower a threshold to clear a gate.
  `thresholds.json` exists only to raise a module above 80, never to lower
  one — a module below 80 gains tests.
- If a gate is stuck, `BLOCKED` with an accurate `Remaining` is the correct
  and useful outcome.
