---
name: openspec-artifact-review
description: Review the artifacts of one OpenSpec change before implementation. Run it in a fresh session. The session acts as an orchestrator and starts four independent reviewer sub-agents (testability, security, hidden assumptions, design contract), merges their findings into review.md in the change folder, and summarizes all issues and recommended fixes. It walks the user through the findings and applies fixes only on request.
argument-hint: "[change-name]"
disable-model-invocation: true
---

# OpenSpec Artifact Review

Change to review: $ARGUMENTS

You are the orchestrator. Four sub-agents do the reviewing; you prepare their
input, merge their output, write the report and apply what the user accepts.

Do not read the artifact contents until the reviewers have returned (step 5).
Your job is to judge their findings without having formed your own view first,
and the session stays usable for the walk-through on large changes.

## 1. Check the session is fresh

This session should contain nothing but this skill invocation. Conversation
history about the change, especially the one that wrote the specs, biases the
merge and the triage.

If there is earlier history, use AskUserQuestion to say so and offer "Stop so I
can start a fresh session" (recommended) and "Continue here". The reviewers
start clean either way.

## 2. Resolve the change

- If no change name was given, run `openspec list --json`. Use the only active
  change if there is exactly one. Otherwise ask with AskUserQuestion.
- Review exactly one active change. Archived changes are out of scope.
- Run `openspec status --change <name> --json` for `changeRoot`, `schemaName`
  and `artifactPaths`.
- If `artifactPaths` shows that the schema generates `review.md`, ask the user
  for a different report file name. Keep the report at the change root in any
  case: the schema can treat files under `specs/` as artifacts, while other
  files at the root are ignored by validate, status and archive.

## 3. Build the review input

Collect these facts. Gaps do not stop the review and need no question: review
what exists and note what is missing under "Coverage" in the report. Stop only
if the change folder has no artifacts at all.

- **Standard artifacts:** `proposal.md`, `specs/**/*.md`, `design.md`,
  `tasks.md`.
- **Non-standard artifacts:** every other file in the change folder, including
  files the schema generates beyond the standard ones. Include them in the
  review without announcing them. Skip `review.md` and dotfiles.
- **`decisions.md`:** if present, this holds settled decisions. See step 4.
- **Repo kind:** `specs-only` if no application source exists outside
  `openspec/` and tooling folders such as `.claude/` and `.github/` (check with
  `git ls-files`, or `find` outside a git repo). Otherwise `code`.
- **Referenced stores:** from `openspec context`. Reviewers fetch specs with
  `openspec show <spec-id> --type spec --store <store>`.

## 4. Start the reviewers

Start all four in one message so they run in parallel, each with
`subagent_type: general-purpose` and no model override. If `repo kind` is
`specs-only`, reviewer 4 still runs, in its specs-only mode.

| ID prefix | Reviewer | Brief |
|---|---|---|
| T | Testability and verifiability | `references/testability.md` |
| S | Security | `references/security.md` |
| A | Hidden assumptions | `references/assumptions.md` |
| D | Design contract | `references/design-contract.md` |

Give each reviewer the same prompt, with only the brief path and prefix
changing. Use absolute paths, based on this skill's base directory:

```
You are one of four independent reviewers of an OpenSpec change.
Read <base>/references/reviewer-common.md, then <base>/references/<brief>.md,
and follow them.

Change: <name>
Change root: <changeRoot>
Schema: <schemaName>
Repo kind: <code | specs-only>
Standard artifacts: <paths>
Non-standard artifacts: <paths>
decisions.md: <path | none>
Referenced stores: <ids | none>
Finding ID prefix: <T | S | A | D>
```

Pass no opinions, summaries or hypotheses about the change, so each reviewer
reaches its own conclusions.

If a reviewer fails or returns nothing usable, retry it once. If it fails again,
mark that part as not covered in the report. The verdict can then not be
"Ready".

## 5. Merge the findings

Now read the artifacts and any existing `review.md`.

1. **Check citations.** Confirm that each cited requirement, quote or file
   exists. Fix small citation errors. Drop a finding whose evidence does not
   exist, and count the drops under "Coverage".
2. **Remove duplicates.** When reviewers report the same defect, keep one
   finding, note both IDs, and use the higher severity.
3. **Flag conflicts.** When reviewers propose incompatible fixes, keep both and
   mark them as a conflict for the user to decide. Do not pick a side.
4. **Respect settled decisions.** Drop any finding that challenges a choice
   recorded in `decisions.md`. Keep findings where an artifact disagrees with
   that file.
5. **Compare with the earlier run.** If `review.md` exists, mark each finding
   `new` or `recurring`, and mark those the user rejected earlier as
   `previously rejected`. Reviewers never see the earlier report, so it cannot
   anchor them.

Do not add findings of your own. Keep the reviewers' severities unless a finding
clearly breaks the definitions in `references/reviewer-common.md`, and note any
change you make.

## 6. Write the report and summarize

Write `<changeRoot>/review.md` using `references/report-template.md`,
overwriting any earlier report, with the verdict set by the rules in step 9.
Then show in chat:

- the verdict, the counts per severity and reviewer, and the report path
- conflicts between reviewers, with the fixes each one proposes
- every other finding, blockers first, as one short entry:
  `**<ID> (<severity>)** <artifact> > <requirement or section>: <the problem>.
  **Recommended fix:** <the fix>`
- upstream findings, labelled as such, and the number of findings marked
  `previously rejected`

Full wording and analysis stay in the file. Then stop. Do not ask questions or
edit artifacts. Say in one line that the user can ask to be walked through the
findings or name the fixes to apply.

## 7. Walk through the findings

Run this step only when the user asks for it. If the user instead names specific
fixes to apply, skip to step 8 for those fixes.

Skip findings marked `previously rejected` and the "Upstream" section. Use
AskUserQuestion and make every question stand on its own: name the artifact and
requirement, quote the current text, give the failure scenario in one sentence.
Use `preview` to show current and proposed text.

1. **Conflicts first**, one at a time, with each proposed fix as an option.
2. **Blockers, then majors**, one at a time, with options "Apply" (recommended
   unless you doubt the finding), "Edit" and "Reject". On "Edit", ask for the
   wording, or take it from the user's "Other" text.
3. **Minors last**, as one batch with `multiSelect`, up to four per question.
   Selected findings are applied, unselected ones stay open.

Must-specify assumptions are findings like any other. Assumptions classified as
safe to leave implicit are not part of the walk-through.

## 8. Apply accepted fixes

Apply each accepted fix to the artifact it targets, then carry it into the other
**standard** artifacts that rely on the old wording, without asking again. Do
not change the state of any task checkbox.

These limits apply to every edit:

- **Non-standard artifacts:** never edit without confirmation. At the end, list
  those that now look stale and what would change, and ask with AskUserQuestion.
- **`decisions.md`:** never edit. If an accepted fix or the user's own wording
  contradicts it, leave the file alone and report the contradiction.
- **Referenced stores, `openspec/specs/` and code:** never edit.
- **Git:** do not commit or push. The user reviews the diff.

Then run `openspec validate <name> --strict`. Fix anything your edits broke. If
it was already failing before your edits, report that instead.

## 9. Finish

After a walk-through or applied fixes, update `review.md`: the status of each finding, the files changed, stale
non-standard artifacts the user declined to update, and the final verdict.

Final verdict:

- **Not ready:** any blocker is open, or a reviewer did not complete.
- **Ready, with accepted risks:** no blocker is open, but the user rejected one.
  List each.
- **Ready:** no blocker is open and none was rejected.

If any blocker or major was fixed, say that the new wording itself has not been
reviewed and recommend a re-run in a fresh session.

End with the verdict, the files changed and the report path.
