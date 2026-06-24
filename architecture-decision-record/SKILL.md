---
name: architecture-decision-record
description: >
  Create an Architectural Decision Record (ADR) in the MADR format under docs/decisions.
  Use this skill whenever an architectural decision is being made or has just been made in
  the project — choosing a database, framework, library, language, communication protocol,
  auth approach, architectural pattern/style, build or deployment strategy, API shape, or any
  other hard-to-reverse, project-shaping technical choice — even if the user does not say "ADR".
  Also use it on explicit requests like "create an ADR", "write a decision record",
  "document this decision", "record this in MADR", or "add an ADR for X". When a decision
  surfaces in conversation, proactively offer to capture it with this skill rather than letting
  it go unrecorded. Do NOT use it for routine code changes, bug fixes, or non-architectural choices.
---

# Architecture Decision Record (MADR)

This skill creates Architectural Decision Records using the **MADR** (Markdown Any Decision
Records) template and stores them as numbered, immutable-once-accepted markdown files. An ADR
captures *one* architectural decision: the problem, the options weighed, the option chosen, and
the consequences — so future maintainers understand *why* the system is the way it is.

The point of an ADR is the reasoning, not ceremony. Keep it honest and concise. Don't invent
drivers, options, or consequences the user never mentioned — ask, or leave the optional section out.

## When to engage

Engage when an architectural decision is being made or has just been settled in the conversation,
or when the user explicitly asks for a decision record. A decision is "architectural" when it is
costly to reverse and shapes the structure, qualities, or constraints of the system (see the
description for examples). For small, easily reversed, or non-structural choices, an ADR is
usually overkill — say so rather than creating noise.

**Never write the file silently.** Always confirm first (step 1).

## Workflow

### 1. Confirm intent and detail level

Before writing anything, confirm with the user:

- **Whether** they actually want a record for this decision.
- **At what level of detail.** Offer two levels:
  - **Minimal (MADR light)** — Title, Context & Problem Statement, Considered Options, Decision
    Outcome, Consequences. (Decision Drivers strongly recommended even here.) Best for most
    day-to-day decisions.
  - **Full** — all of the above plus the optional sections: Metadata, Decision Drivers,
    Confirmation/Validation, Pros & Cons of the Options, and More Information. Best for high-stakes
    or contested decisions where the alternatives deserve a written comparison.

If the user already implied the level ("just a quick record" → minimal; "document this thoroughly"
→ full), go with it and confirm briefly.

### 2. Resolve the location

ADRs live under **`docs/decisions/`** relative to the project root, unless the user specifies a
different directory. Use the user's path if they give one.

### 3. Read the index FIRST and check for duplicates

Look for **`docs/decisions/index.md`** (or `index.md` in the chosen directory).

- **If it exists, read it before doing anything else.** Scan it (and the existing `NNNN-*.md`
  ADR files) for a decision that is **identical or directly contradicts** the one about to be
  recorded — same subject, same or opposite choice. If you find one, **stop and remind the user**:
  name the existing ADR and ask whether they want to:
  - **Proceed anyway** (create a new ADR — e.g. revisiting an old decision),
  - **Supersede** the existing ADR (create the new one and mark the old one
    `superseded by NNNN`, and link the new one back with "Supersedes NNNN"), or
  - **Cancel**.
- If no index exists, scan the directory's existing `NNNN-*.md` files for an obvious duplicate
  before continuing.

### 4. Compute the next stable ID

The ID is a zero-padded **4-digit** number, incrementing and never reused.

- Find the highest existing `NNNN` among files named `NNNN-*.md` in the directory
  (**exclude `index.md`** — it is never numbered). Next ID = highest + 1.
- If there are no ADRs yet, start at **`0001`**.
- Filename = `NNNN-<kebab-case-title>.md`, e.g. `0001-use-postgresql-for-primary-storage.md`.

### 5. Gather only the missing information

Reuse everything already established in the session — do **not** re-ask for facts you already have.
Then ask only for the fields still missing for the chosen detail level. Be explicit about what is
mandatory vs optional so the user can skip optional parts:

| Section | Mandatory? |
|---|---|
| Title | **Mandatory** |
| Metadata (status, date, deciders / consulted / informed) | Optional |
| Context and Problem Statement | **Mandatory** |
| Decision Drivers | Optional (recommended) |
| Considered Options | **Mandatory** |
| Decision Outcome (with justification) | **Mandatory** |
| Consequences (Good / Bad) | **Mandatory** |
| Confirmation / Validation | Optional |
| Pros and Cons of the Options | Optional |
| More Information | Optional |

For the meaning, intent, and a worked example of each section, read
[`references/madr-sections.md`](references/madr-sections.md).

### 6. Write the ADR

Copy the template at [`assets/adr-template.md`](assets/adr-template.md) and fill it in:

- Use the chosen detail level — for **minimal**, delete the optional sections rather than leaving
  empty placeholders.
- Set `date` to **today's actual date** in `YYYY-MM-DD` format.
- Default `status` to `accepted` unless the user says it is still `proposed` (or `rejected`,
  `deprecated`, etc.).
- Keep `Good, because …` / `Bad, because …` phrasing for consequences — it forces honest tradeoff
  thinking.
- Write the file to `docs/decisions/NNNN-<kebab-title>.md`.

### 7. Update or create the index

After the ADR file is written:

- **If `index.md` exists** → keep it up to date: add a row for the new ADR (ID, title, status,
  date, link), and if this ADR supersedes another, update the superseded entry's status too.
- **If `index.md` does NOT exist:**
  - If this is the **first ADR** in the project (no other ADR files existed before this one) →
    **ask the user whether to create an index**. If yes, scaffold it from
    [`assets/index-template.md`](assets/index-template.md) and add the first row.
  - If **other ADRs already exist** without an index → treat the absence as **intentional** and do
    **not** create one (and don't nag about it).

### 8. Report

Tell the user the path of the new ADR, its ID and status, and whether the index was created/updated.

## Notes

- One decision per ADR. If the conversation settled several distinct decisions, create one ADR each
  (each gets its own incrementing ID).
- Accepted ADRs are a historical log — don't rewrite an old accepted ADR to reflect a new decision.
  Create a new ADR that supersedes it instead.
