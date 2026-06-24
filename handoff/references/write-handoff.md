# Write Handoff — Full Instructions

Generate a structured handoff document that preserves everything a new Claude Code session needs to continue this work without losing context, repeating mistakes, or re-discovering decisions.

## Phase 1: Auto-Gather Context

Collect all data automatically — do NOT interview the user. Run these in parallel where possible:

### Git State
```bash
git branch --show-current
git status
git log --oneline -20
git log --oneline main..HEAD  # commits on this branch (adjust base branch if needed)
git diff --stat main..HEAD    # files changed on this branch
```

### Build & Test State
- Run the project's build command (detect from build files: `./gradlew build`, `npm run build`, `cargo build`, etc.)
- Run the project's test suite (detect: `./gradlew test`, `npm test`, `cargo test`, etc.)
- Capture pass/fail counts and any error output

### Session Context (from conversation history)
Review the entire conversation to extract:
- **Goals:** What the user asked to accomplish and why
- **Completed work:** What was done, in what order
- **What worked:** Approaches, patterns, libraries that succeeded
- **What failed:** Approaches that were tried and abandoned — capture WHY they failed, including **exact error messages** (e.g., `HttpException: 401 Unauthorized at AuthApi.kt:20`, not "the HTTP call failed")
- **Decisions made:** Any choice between alternatives, with the rationale
- **Blockers:** Anything unresolved or blocking

### File Scan
- From `git diff --stat` and conversation context, compile the full list of files modified
- Grep modified files for `TODO`, `FIXME`, `HACK`, `XXX` markers

### Key Interfaces & Function Signatures
- From the conversation and modified files, identify the important interfaces, type definitions, function signatures, or contracts that the next session needs to know about
- Read these from the actual source code — do not paraphrase from memory
- Include function signatures (name, parameters, return type) for any functions the next session will need to call or modify — but **never include function bodies**
- The goal is: the next agent can see the API surface without reading every file

## Phase 2: Determine File Name

- **Directory:** `handoffs/` at the project root. Create it if it doesn't exist.
- **Pattern:** `HANDOFF-<task-slug>-<YYYY-MM-DD>.md`
- **Task slug:** Derive from the user's description (e.g., "create handoff for sync" → `sync`). If no explicit name, infer from the branch name. Use kebab-case, keep it short (1-3 words).
- **Collision:** If `HANDOFF-<slug>-<date>.md` already exists, append `-02`, `-03`, etc.

## Phase 3: Write the Document

Use this exact template. Every section is mandatory — write "Nothing notable." if a section is genuinely empty.

```markdown
# Handoff: <Task Name>
> Generated: <YYYY-MM-DD HH:MM> | Branch: `<branch>` | Status: <in-progress|blocked|ready-for-review>

## Goal
What we're trying to accomplish and why. 1-3 sentences.

## Progress Summary
High-level status: what phase of work is done, overall shape of what remains.

## Completed Work
- [Logical chunk of work] — files: `path/to/file.kt`, `path/to/other.kt`
- [Another chunk] — files: `...`

## What Worked
- [Approach/pattern/tool that succeeded and should be reused]
- [Another success]

## What Failed
- [Approach tried and abandoned] — **Why it failed:** [exact error message with file:line if applicable]
- [Another failed approach] — **Why it failed:** [exact error message with file:line if applicable]

## Decision Log
| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| [What was decided] | [Option A, Option B, ...] | [What we chose] | [Why] |

## Key Interfaces & Function Signatures
Paste actual signatures/contracts/type definitions from source code.
NO full code dumps and NO function bodies — just the minimal API surface the next session needs to call into or match.

Example:
\`\`\`kotlin
// SyncRepository.kt
suspend fun syncAll(force: Boolean = false): Result<SyncReport, SyncError>
suspend fun syncSince(lastSync: Instant): Result<SyncReport, SyncError>

// SyncError.kt
sealed interface SyncError {
    data class Network(val code: Int, val message: String): SyncError
    data object Unauthorized: SyncError
}
\`\`\`

## Files Modified
**Feature code:**
- `path/to/file.kt` — [brief description of change]

**Tests:**
- `path/to/test.kt` — [brief description]

**Config/Build:**
- `build.gradle.kts` — [brief description]

## Git State
- **Branch:** `<branch-name>`
- **Ahead/behind:** X ahead of main, Y behind
- **Uncommitted changes:** [list files or "Working tree clean"]
- **Recent commits on branch:**
  - `abc1234` — commit message
  - `def5678` — commit message

## Build & Test State
- **Build:** [passes | fails — paste exact error message with file:line]
- **Tests:** [X passing, Y failing]
  - Failing: `TestClass.testMethod` — exact assertion/error message, e.g. `expected 200 but was 401 at AuthApiTest.kt:45`

## Known Issues & Blockers
- [Issue or blocker, with context]

## Next Steps
1. **[Task description]** — files: `path/to/file.kt`, `other/file.kt` — [gotchas/dependencies]
2. **[Task description]** — files: `...` — [gotchas/dependencies]
3. **[Task description]** — files: `...` — [gotchas/dependencies]
```

## Quality Rules

- **Never invent information.** Only include what's in the conversation history or discoverable from git/build/code.
- **Scannable in under 2 minutes.** Be concise — bullet points over paragraphs.
- **"What Failed" is mandatory.** This is the highest-value section. The next session WILL try the same things if you don't warn it.
- **Decision Log needs rationale for every row.** A decision without reasoning is useless.
- **Key Interfaces from actual code.** Read the source, paste real function signatures (name, params, return type). Never include function bodies — just the contract. The next agent needs to know how to call things, not how they're implemented.
- **Exact error messages, always.** Never write "it threw an error" or "the HTTP call failed". Write `HttpException: 401 Unauthorized at AuthApi.kt:20` or `Unresolved reference: syncAll at SyncRepository.kt:34`. Include file, line number, and the actual message. This is non-negotiable.
- **Next Steps reference specific files.** Vague steps like "finish the feature" are worthless.
- **Write to disk only.** Do NOT auto-commit the handoff file.

## After Writing

Tell the user:
- The path to the generated handoff file
- A 2-3 sentence summary of what's in it
- Remind them they can resume with: "resume from the <task-slug> handoff"
