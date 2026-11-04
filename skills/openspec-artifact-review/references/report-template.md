# Report template for review.md

Use this structure. Leave out a section only if the note beside it says so. Keep
the findings' fields as the reviewers returned them, including the fields their
briefs add. Sort findings blockers first, then majors, then minors.

Status values: `open`, `applied`, `applied with edits`, `rejected`.
Run marks: `new`, `recurring`, `previously rejected`. Use run marks only when an
earlier report existed.

```markdown
# Artifact review: <change-name>

**Verdict:** <Not ready | Ready, with accepted risks | Ready>
**Reviewed:** <YYYY-MM-DD>, schema `<schema>`, repo kind `<code | specs-only>`

| Reviewer | Blocker | Major | Minor |
|---|---|---|---|
| Testability | n | n | n |
| Security | n | n | n |
| Hidden assumptions | n | n | n |
| Design contract | n | n | n |

## Conflicts between reviewers
<!-- Leave out if there are none. -->
<Finding IDs, what each proposes, why they can't both apply, the user's decision.>

## Findings

### <ID>: <title>
**Status:** <status> · **Run:** <run mark>
<The reviewer's fields. For merged duplicates, list both IDs.>

## Security analysis

### Trust boundaries
<The boundary sections, including those where the spec stops the attack.>

### Test versus production
<The invariant sections.>

## Assumptions safe to leave implicit
| Assumption | Where it is implied | Why it is safe |
|---|---|---|

## New abstractions
<!-- Leave out in specs-only repos. -->
<Each abstraction: keep and document, challenge, or fine as is, with one line.>

## Upstream: shared specs
<!-- Leave out if there are none. -->
<Findings in referenced stores, with the store and spec ID. Not edited here; they
need a change in that store. A blocker here makes the verdict Not ready.>

## Coverage
- Artifacts reviewed: <list>
- Missing artifacts: <list, or none>
- Testability: <requirements and scenarios checked, flagged>
- Security: <boundaries and invariants examined>
- Hidden assumptions: <areas not applicable>
- Design contract: <mode, what was checked>
- Reviewers that did not complete: <list, or none>
- Findings dropped because their evidence did not exist: <count>
- Findings dropped because they challenged decisions.md: <count>

## Applied changes
<!-- Added after the walk-through. -->
- Files changed: <list>
- Stale non-standard artifacts the user chose not to update: <list, or none>
- Contradictions with decisions.md: <list, or none>
- Accepted risks: <rejected blockers, or none>
```
