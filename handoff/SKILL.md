---
name: handoff
description: |
  Create or resume from structured handoff documents for session continuity.
  Use this skill whenever the user says "create handoff", "write handoff",
  "handoff for X", "resume from handoff", "read handoff for X",
  "continue from X handoff", or "pick up where we left off on X".
  Creates task-named, timestamped handoff files that preserve goals, progress,
  decisions, failed approaches, interfaces, and next steps between sessions.
---

# Handoff — Session Continuity Documents

This skill has two modes. Detect which one the user wants and load ONLY the relevant instructions.

## Mode Detection

**Write mode** — user wants to CREATE a handoff:
- "create handoff for sync"
- "write handoff"
- "handoff for the auth feature"
- "save a handoff"

**Read/Resume mode** — user wants to CONTINUE from a handoff:
- "resume from the sync handoff"
- "read handoff for sync"
- "continue from sync handoff"
- "pick up where we left off on sync"

## Instructions

1. Determine the mode from the user's message.
2. Resolve the path to this skill's directory (the folder containing this SKILL.md file).
3. **Write mode:** Read `references/write-handoff.md` in this skill's directory and follow it exactly.
4. **Read/Resume mode:** Read `references/read-handoff.md` in this skill's directory and follow it exactly.

Do NOT read both files. Only load the one matching the detected mode.
