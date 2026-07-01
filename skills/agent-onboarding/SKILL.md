---
name: agent-onboarding
description: |
  Onboard a future AI session to a specific slice of an existing codebase before a
  migration, refactor, or extension. Produces onboarding docs under ./onboarding/ — a
  repo-global glossary that is amended across slices, plus per-slice decision records and
  (when existing code is affected) a navigation map. Use this skill whenever the user is about to change part of
  an unfamiliar or inherited codebase and says things like "onboard an agent to this slice",
  "prepare context before I refactor X", "scope this change", "I'm about to extend/migrate Y",
  "where do I start in this repo", or "onboard me to this codebase". Reach for it even when
  the user doesn't say "onboarding" but is clearly trying to build durable context for an
  upcoming change rather than make the change itself.
---

# Agent onboarding

You are building context for a **future** AI session that will make one specific change to an
existing codebase. You are not making the change. You are not mapping the whole repo. Everything
you produce is in service of that one upcoming change — a migration, a refactor, or an extension.

You run in the main conversation, so two things are available to you that a one-shot subagent
can't do: you can **interview the user** when the code doesn't explain itself (step 4), and you can
**dispatch parallel sub-agents** to read faster (see Parallelization).

**Why scope so tightly.** Broad, AI-generated, repo-wide context files measurably *reduce* a future
agent's task success and inflate its cost — only narrow, curated context helps. Working memory holds
~4 chunks; a monorepo doesn't fit. So you always ask "what is about to change?", never "what does
this whole codebase do?" If you find yourself documenting things outside the slice, you've drifted.

## Output

Onboarding output lives under `./onboarding/`. The glossary is **repo-global** — one shared file at
the root of the folder — while decision records and navigation are **per-slice**, in their own
subfolder:

```
./onboarding/
├── glossary.md                  (one central glossary, shared across all slices)
└── slice-<name>/
    ├── decision-records.md       (always)
    └── navigation.md             (only when existing code is affected)
```

`<name>` is a short, concise kebab-case name for the change, e.g. `slice-goal-detail-refactor`,
`slice-auth-token-migration`, `slice-export-pdf`.

The glossary is global on purpose: terminology belongs to the repo, not to one change. A future
slice should *find* `Episode` or `PSMP` already defined, not re-document it. So you **amend** the
central glossary, you don't recreate it per slice (see step 3).

**Do not write to `AGENTS.md`, `CLAUDE.md`, or any project-rules file.** Those are *inputs* you read
(see step 2), never targets you write. Keep all onboarding output inside `./onboarding/`.

| File | Scope | Purpose | When |
| --- | --- | --- | --- |
| `onboarding/glossary.md` | Repo-global | The first place a future agent looks when a term, abbreviation, or concept is unclear. | Always — created once, amended on every later slice. |
| `slice-<name>/decision-records.md` | Per-slice | The answers to "why is it like this?" — captured from the user, not invented. These are tied to a specific change. | Always |
| `slice-<name>/navigation.md` | Per-slice | What this change touches: which files, which parts of them. Metadata only, no code. | Only when the change modifies existing code; skip it for an isolated greenfield feature (and note that you skipped it). |

## The four steps

### 1. Scope to a slice — and map what it touches

Pin down the one change first.

- User already named a scope (a file, a feature, a module, "the bug in X", "migrate Y to Z") → use it.
- User said "onboard me" / "where do I start" with no scope → ask one question: **"What's the next
  change you'll be making in this repo?"** Scope to that answer.
- User insists on whole-repo scope on a large repo → name the tradeoff (broad context hurts the
  future agent's success rate and cost) and let them decide.

As part of this step, work out **which files the change will touch and which parts of each** —
the functions, classes, or sections involved. This is *metadata only*: paths and named code units,
not pasted code. It's the raw material for `navigation.md`, and it tells you whether this change
modifies existing code (navigation file needed) or is isolated greenfield (skip it).

### 2. Find the existing rules ("system prompt")

Before reading code, find any file that already governs how agents and contributors work in this
repo. These are the repo's standing instructions — its "system prompt." Look for:

- General agent/contributor rules: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*`, `CONTRIBUTING.md`,
  or similar.
- A **GitHub Spec Kit constitution**: `.specify/memory/constitution.md` (Spec Kit projects keep
  their governing principles here). If present, it's authoritative — treat its principles as hard
  constraints.
- An **OpenSpec config**: `openspec/config.yml` (and, if it points to or sits beside them, the
  `openspec/project.md` conventions). These define the project's spec-driven workflow and rules.

Several of these may coexist; read whichever are present.

Read the parts relevant to your slice for **hard constraints** (required patterns, forbidden
approaches, conventions the future agent must honour). Surface those constraints into your output
where they belong — usually as glossary entries or decision records. **Read these files only; never
edit them.**

### 3. Read in hypothesis loops, and grow the central glossary

**First, check for an existing glossary at `./onboarding/glossary.md`.** If it's there, read it
before you read any code — it's the accumulated vocabulary of every prior slice, and you'll
*amend* it, not replace it. If it isn't there, you'll create it. Either way there is only ever one
glossary for the repo.

Read the slice by predicting, then checking. "I think auth lives in `auth/`." Open it. Wrong? Update
your mental model. Right? Move on. Aim for hypothesis density, not coverage — don't read top-to-bottom.
If your predictions are wrong more than about 1 in 3, the slice is probably mis-scoped; return to step 1.

While reading, grow the glossary. **The glossary documents domain terminology — not code.** It is
the place a future agent looks to understand a *word*, not to understand what a class or function
*does*. So the test for every candidate entry is: **would this be unclear to a competent developer
who is new to this repo's domain?**

What goes in:

- **Abbreviations and acronyms that aren't self-explaining** — `PSMP`, `GiftWrap`, `RSVP` — anything
  a newcomer would have to ask about.
- **Domain concepts particular to this product** — `Feed`, `Episode`, `Slice` — terms that carry a
  specific meaning here that you can't infer from general programming knowledge.
- **Names that are *not* self-explaining** — a class or function whose name doesn't reveal what it
  represents.

What stays out:

- **Self-descriptive names.** A class like `ScheduledMessageTimePickerBottomSheet` already says
  exactly what it is — adding it teaches a future agent nothing. The same goes for any clearly named
  class or function.
- **Per-symbol descriptions of what code does.** This is not code documentation. Do not walk the
  class and function names of the slice and describe each one's behaviour — a `tree` command and the
  code itself already do that.
- **Genuinely generic terms** — `User`, `Repository`, `Service`.

Pull terms from wherever the domain vocabulary actually lives — names, yes, but especially
**inline comments and doc comments**, which is where abbreviations and intent usually hide. Read
every inline comment that relates to the slice.

Add only terms that aren't already defined — if an entry exists and is still accurate, leave it; if
the slice taught you something that makes an existing entry wrong or thin, refine it in place. Don't
duplicate, and don't scope entries to "this slice": the glossary serves the whole repo.

The glossary is the single most important artifact: a future agent that's confused about *what a
term means* should be able to resolve it here without re-reading the code. When a term is genuinely
domain vocabulary and you're unsure whether it's obvious, include it; when it's just a descriptive
name, leave it out. Each entry is a 2–3 line description; go longer only when there's a real reason
the term can't be explained briefly.

### 4. Read as an outsider, then interview the user

Now reread the affected code as a developer who was **not** on the team that built it. An outsider
asks "why" constantly, and wherever the code doesn't answer and no comment explains, you've found
something a future agent will also stumble on. Collect every such question, for example:

- Why is it done this way and not the obvious way?
- Why does this stick to a deprecated function when a modern replacement exists?
- Why is the logic shaped like this?

Also collect **inconsistencies** the slice reveals, such as:

- Domain or data logic living in the presentation layer (or vice versa).
- Two different libraries used for the same purpose within the affected modules.
- Naming, patterns, or conventions that contradict each other.

You usually can't answer these from the code — that's the point. **Gather them all, then present one
consolidated list to the user** (a single batched set of questions, not a slow one-by-one
interrogation). Record their answers in `decision-records.md`. These recorded decisions are what stop
a future agent from "fixing" something that's deliberate, or faithfully copying something that was a
mistake.

## Parallelization

Because this skill runs in the main conversation, you may dispatch parallel **Explore** sub-agents to
move faster — confirm with the user before spawning them:

- Step 1 affected-file discovery and step 3 hypothesis reading can run as parallel Explore agents,
  each given a distinct area of the slice.
- Drafting `glossary.md` and `navigation.md` can happen concurrently.

The step-4 interview always stays in the main loop — it needs the human.

## Templates

### onboarding/glossary.md  (repo-global — amend, don't replace)

```markdown
# Glossary

| Term | Means in this code | Where it appears | Not to be confused with |
| --- | --- | --- | --- |
| <term> | 2–3 line plain-language meaning | path/to/file.ext:line | <similar term, if any> |
```

### slice-<name>/decision-records.md  (per-slice)

```markdown
# Decision records — <slice>

## <short question / topic>
- **Context:** path/to/file.ext:line — what the code does that raised the question.
- **Decision / answer:** what the user said (intent, history, constraint).
- **Date:** YYYY-MM-DD
```

### slice-<name>/navigation.md  (per-slice)

```markdown
# Navigation — <slice>

One line: what change this maps, and what it does NOT cover.

## Affected files
- `path/to/file.ext` — which functions / classes / sections the change touches, and why.

## To change X, expect to touch
- A, then B, then C — the pattern, stated as named units, not pasted code.
```

`navigation.md` is metadata: paths and named code units only. No code snippets — a future agent can
open the file itself; what it can't easily reconstruct is *which* files and parts matter together.

## What changes by repo shape

Same artifacts, different fill rate.

| Repo | Adjustment |
| --- | --- |
| **Small / clean** | Glossary often carries most of the value. Navigation may be a few lines or skipped if greenfield. |
| **Medium / clean** | The sweet spot. All three files, each kept tight. |
| **Large / monorepo** | Per-slice only. One onboarding folder per change. If you're tempted to write one for the whole monorepo, you've broken step 1 — go back. |
| **Messy / legacy** | Delta reading moves up: run `git log -p --follow` on the worst affected files first — their history explains why they look the way they do, and seeds step-4 questions. The glossary gains a "deprecated names still in code" subsection. The decision record becomes the largest artifact. |

## Stop conditions

- No build file / not actually a codebase → say so and stop.
- User insists on whole-repo scope on a very large repo → name the tradeoff, let them choose.
- Hypothesis predictions wrong more than ~1 in 3 → the slice is mis-scoped. Stop and re-scope.

## What you don't do

- Don't generate per-file summaries — a `tree` command does that for free.
- Don't turn the glossary into code documentation — it captures domain terminology, not a
  description of what each class or function does, and it skips self-descriptive names entirely.
- Don't generate import-graph or architecture diagrams — low value, high rot.
- Don't write to `AGENTS.md` / `CLAUDE.md` / project-rules, a Spec Kit `constitution.md`, or an
  OpenSpec `config.yml` — these are all read-only inputs.
- Don't put code snippets in `navigation.md` — it's a metadata map, not a copy of the code.
- Don't invent answers to step-4 "why" questions — those come from the user, recorded as decisions.
