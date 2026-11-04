---
name: verify
description: Unified IDE-local verification gate. Diff-vs-base review pipeline — skip-check → context discovery → parallel reviewers (bug + convention + security) → issue-validator → targeted Gradle tests → verify-audit → high-signal report (HIGH-confidence BLOCKER/MAJOR findings only).
argument-hint: "[--base=<ref>]"
user-invocable: true
disable-model-invocation: false
---

# /verify — orchestrated IDE-local code-review gate

You are the **main agent**. You orchestrate all sub-agent dispatches. Sub-agents under `.claude/agents/` cannot dispatch further sub-agents (Claude Code architectural constraint — see https://code.claude.com/docs/en/subagents-and-plugins.md). All parallel fan-out happens from your context.

This command is the single verification gate for any finished piece of work in this repo — spec-kit task, refactor, bug fix, scratch experiment. It diffs the working branch against a base ref and runs a tight, high-signal review. Only issues that any developer who knows the project's conventions would say "yes, that has to be fixed before this is pushed" reach the final report.

## Arguments

The user invoked: `/verify $ARGUMENTS`

`$ARGUMENTS` is optional. The only recognized flag is:

- `--base=<ref>` — git ref to diff against. Default: `master`.

Any other token, any malformed flag, or any unrecognized form → emit `INVALID_INVOCATION` (Stage 7 format) with the offending token in `Notes` and stop.

## Sub-agent registry

| name | model | role |
|---|---|---|
| `skip-checker` | haiku | Stage 1 — decides SKIP yes/no |
| `bug-reviewer` | opus | Stage 4 — logic bug pass over the diff |
| `convention-reviewer` | sonnet | Stage 4 — convention compliance grounded in discovered markdown |
| `security-reviewer` | opus | Stage 4 — security, behavior deviation, missing test coverage |
| `issue-validator` | opus | Stage 6 — confirms each emitted issue independently |
| `verify-audit` | sonnet | Stage 8 — discipline pass over the initial report; emits per-finding KEEP / CUT / UNSURE |

Dispatch them with `subagent_type: "<name>"` on the `Agent` tool.

---

## Stage 0 — Parse arguments

1. Tokenize `$ARGUMENTS`. Empty → default (`base=master`).
2. For each token, match `--base=<ref>`. Anything else → `INVALID_INVOCATION` (Stage 7 format) and stop.

## Stage 1 — Skip check

Compute `changed_files = git diff <base>...HEAD --name-only`. If empty, emit `SKIPPED` (Stage 7 format) with reason "no diff vs <base>" and stop.

Otherwise dispatch **one** `skip-checker` `Agent` call. Pass `diff_command` (e.g. `git diff <base>...HEAD`) and `changed_files` (newline-separated).

If the agent returns `{"skip": true, ...}`, jump straight to Stage 7 with verdict `SKIPPED` and the agent's reason in `Notes`. Do not proceed past Stage 1.

## Stage 2 — Context discovery (orchestrator, sequential reads)

Read into your context (these are ground truth for downstream leaves). Collect their absolute paths in a `discovered_files` list:

- Repo root `CLAUDE.md` (always).
- Repo root `AGENTS.md` (if exists).
- `.specify/memory/constitution.md` (if exists).
- Any `specs/<feature>/{plan,spec,tasks}.md` and every file under `specs/<feature>/contracts/` where either the path appears in `changed_files`, or `<feature>` matches the active feature named in `CLAUDE.md`'s "Current feature" line.

Also resolve, for each changed `*Test.kt` / `*Test.java` file in the diff:

- The Gradle `module` (walk up the path until you hit a `build.gradle.kts`).
- The `bucket` — `unit` if under `src/test/` or `src/jvmTest/` or `src/commonTest/`; `integration` or `ui_or_e2e` if under `src/androidTest/` (use the file name to disambiguate — files with `UiTest` / `ScreenTest` / `Compose` in the name are `ui_or_e2e`, others are `integration`).
- The `production_files` it claims to cover (mirror the test's package + drop the `Test` suffix from the class name; Grep if not found).

Record one boolean from these scans:

- `has_android_test_changes` — `true` if any changed file is under `src/androidTest/`.

## Stage 3 — Diff summary (orchestrator, no sub-agent)

Run `git diff <base>...HEAD <files>` and produce a 5–10 line factual summary of what changed. Keep it short — it's an aid for the reviewers, not user output.

## Stage 4 — Parallel review fan-out (SINGLE MESSAGE, MANY AGENT CALLS)

In **one assistant turn**, dispatch the following in parallel — separate `Agent` tool calls within the same message:

1. `bug-reviewer` × 1. Payload: `diff`, `diff_summary`, `discovered_files`.
2. `convention-reviewer` × 1. Payload: same.
3. `security-reviewer` × 1. Payload: same.

Test files in the diff are part of `diff` and are reviewed by all three under the same rules as production code — a weak or tautological test is a finding like any other.

**Hard rule:** parallel `Agent` calls in one assistant turn. Sequential dispatch is a bug.

Collect every JSON response. Build a single `findings` list of issues (each tagged with its origin `category`).

## Stage 5 — Targeted Gradle tests

Determine affected Gradle modules from the changed `.kt` / `.kts` paths.

- Always: `./gradlew <module>:testDebugUnitTest` per affected module (use `<module>:test` for JVM/KMP modules without an Android `Debug` source set).
- Conditional: `./gradlew <module>:connectedDebugAndroidTest` per affected module **only if** `has_android_test_changes` is `true`. If conditional triggers and `adb devices` shows no online device, follow the `android-cli` skill (`~/.claude/skills/android-cli/SKILL.md`) to boot an emulator; poll `adb devices` for up to 3 minutes before failing.

Capture PASS / FAIL and the full failing-test names verbatim.

## Stage 6 — Per-issue validation (SINGLE MESSAGE, PARALLEL)

Dedupe `findings` by `(file, line, title)`. For every surviving issue, dispatch **one** `issue-validator` `Agent` call in a single turn — passing only that one `issue` object (not the full diff, not other findings).

Filter the validated set to **HIGH-confidence + severity ∈ {BLOCKER, MAJOR}**. Everything else is dropped (any MEDIUM- or LOW-confidence result, and any MINOR / NIT severity, even when validated). The surviving set is what you report and what feeds the verdict.

## Stage 7 — Aggregate initial verdict + write report to /tmp

Initial verdict priority (first match wins):

1. `INVALID_INVOCATION` — Stage 0 rejected args.
2. `SKIPPED` — Stage 1 said skip or empty diff.
3. `TESTS_FAILED` — Stage 5 reported any failure.
4. `FIXES_REQUIRED` — Stage 6 surviving findings include any BLOCKER or MAJOR.
5. `PASS` — none of the above.

### Write the initial report to /tmp (input for Stage 8)

If the initial verdict is `SKIPPED` or `INVALID_INVOCATION`, skip the rest of Stage 7 and skip Stage 8 entirely — there are no findings to audit. Emit the final output (Stage 9 format) directly using the initial verdict and the `Notes` reason.

Otherwise:

```bash
mkdir -p /tmp/foldio-verify.$$
```

`Write` the following to `/tmp/foldio-verify.$$/report.md`:

```
## Verdict
<initial verdict>

## Tests
<one line per Gradle task: `PASS <task>` or `FAIL <task>` + indented failing test FQNs>

## Findings
<numbered list; each item: severity, category, file:line, title, evidence, explanation, rule_citation if convention, spec_reference if security/coverage>

## Notes
<anything else>
```

Number every finding sequentially across categories (1, 2, 3, …). The numbers are what Stage 8's audit table references.

## Stage 8 — Verify-audit discipline pass (SINGLE AGENT CALL)

Skipped when Stage 7 short-circuited at `SKIPPED` or `INVALID_INVOCATION`.

Dispatch **one** `verify-audit` `Agent` call. Payload:

- `report_path` — `/tmp/foldio-verify.$$/report.md`.
- `audit_output_path` — `/tmp/foldio-verify.$$/audit.md`.
- `changed_files` — the Stage 1 `changed_files` list (newline-separated).
- `discovered_files` — the Stage 2 `discovered_files` list (newline-separated absolute paths).
- `worktree_root` — the repo root absolute path (output of `git rev-parse --show-toplevel`).

The agent will `Write` the audit table to `audit_output_path` and reply with that path. `Read` the file. It contains a markdown table:

```
| # | Finding | Verdict | Trigger | Reason |
|---|---|---|---|---|
| 1 | <finding 1 title> | KEEP | none | ... |
| 2 | <finding 2 title> | CUT | quoted rule doesn't exist | ... |
| 3 | <finding 3 title> | UNSURE | bug finding requires out-of-diff context | ... |
```

## Stage 9 — Apply audit + emit final output

Apply the audit row-by-row to the Stage 7 findings list (numbers match):

- `KEEP` → finding stays in the final report unchanged.
- `CUT` → finding is removed from the final report.
- `UNSURE` → finding stays, but prefix its title with `[UNVERIFIED]` so the user knows the audit couldn't confirm it cheaply.

**Recompute the verdict** from the post-audit findings list using the Stage 7 vocabulary. The verdict can downgrade for reviewer findings — e.g. if every `BLOCKER` was `CUT`, `FIXES_REQUIRED` can become `PASS`. It does **not** downgrade past `TESTS_FAILED`, which is immune to audit filtering: a failing test is a fact about the codebase, not a subjective reviewer finding.

Emit the final user-facing output:

```
## Verdict
<recomputed verdict>

## Tests
<one line per Gradle task: `PASS <task>` or `FAIL <task>` + indented failing test FQNs>

## Findings
<post-audit findings: KEEP-rated and UNSURE-rated (prefixed `[UNVERIFIED]`). Grouped by category. Omit section if empty.>

## Audit
<the full markdown table from Stage 8, including CUT rows so the user sees what was filtered and why>

## Notes
<anything noteworthy; reason for SKIPPED / INVALID_INVOCATION; brief comment if the audit changed the verdict>
```

Omit sections that are empty / not applicable. Stop after emitting.

## Re-invocation contract

If the recomputed verdict is `FIXES_REQUIRED` or `TESTS_FAILED`, address every surviving finding (or document why a finding is rejected by quoting the discovered rule that contradicts it), then re-run `/verify` with the same args. Only consider a piece of work shippable / mergeable once `/verify` returns `PASS` or `SKIPPED`.
