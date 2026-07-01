# Read/Resume Handoff — Full Instructions

Resume work from an existing handoff document. Orient the session with full context before starting any work.

## Phase 1: Find the Handoff

1. Extract the task slug from the user's request (e.g., "resume from sync handoff" → slug is `sync`)
2. Glob for matching files: `handoffs/HANDOFF-<slug>-*.md` at the project root
3. If multiple matches: pick the latest by date in the filename
4. If no matches: try a broader glob `handoffs/HANDOFF-*<slug>*.md` in case the slug is a substring
5. If still no matches: list all files in `handoffs/` and ask the user which one they meant
6. If exactly one match: use it

## Phase 2: Read and Parse

Read the handoff file. Extract:
- Goal
- Progress summary
- What failed (critical — these are the guardrails)
- Known issues & blockers
- Next steps (these drive what happens now)
- Key interfaces
- Decision log

## Phase 3: Verify Current State

Run these commands and compare against the handoff's "Git State" section:

```bash
git branch --show-current
git status
git log --oneline -5
```

Flag any discrepancies:
- **Wrong branch:** "Handoff expects branch `feature/sync` but you're on `main`. Switch branches?"
- **Unexpected commits:** "There are commits after the handoff was written — someone may have continued work."
- **Dirty working tree:** "There are uncommitted changes not mentioned in the handoff."
- **Branch behind:** "Branch is behind remote — may need to pull."

## Phase 4: Present Orientation

Summarize in a concise block — no more than ~15 lines:

```
**Resuming: <Task Name>**
**Goal:** <1 sentence>
**Status:** <where we left off>
**Branch:** <branch> (✅ matches handoff / ⚠️ discrepancy)

**Key constraints from last session:**
- <what failed and shouldn't be retried>
- <important decisions already made>

**Immediate next steps:**
1. <first thing to do>
2. <second thing>
3. <third thing>
```

## Phase 5: Wait for Confirmation

After presenting the orientation, **STOP and wait for the user to confirm** before doing any work. Say:

> "Ready to pick up from here. Want me to start with step 1, or would you like to adjust the plan?"

Do NOT begin implementation until the user explicitly says to proceed.
