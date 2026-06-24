# MADR Sections — Reference

Every section of the MADR template, what it is for, whether it is mandatory or optional, and a short
worked example. Use this to decide what to include and to ask the user the right questions.

The minimal ("MADR light") form is just the mandatory sections (plus Decision Drivers, recommended).
The full form adds all optional sections. Only include an optional section when it carries real
information — an empty optional section is worse than no section.

---

## Title — **mandatory**

A short, descriptive name for the decision. State the problem solved and, ideally, the chosen
solution so the ADR is searchable at a glance. Becomes the kebab-case filename.

> **Example:** `Use PostgreSQL as the primary data store`

---

## Metadata — *optional*

A YAML front-matter block with up to five fields. Useful for governance and traceability; skip on
lightweight ADRs.

- **status** — `proposed | rejected | accepted | deprecated | superseded by NNNN`
- **date** — `YYYY-MM-DD`, the date of the last meaningful update
- **deciders** — who is accountable for / makes the decision
- **consulted** — subject-matter experts consulted (two-way conversation)
- **informed** — stakeholders kept in the loop (one-way)

> **Example:**
> ```yaml
> status: accepted
> date: 2026-06-22
> deciders: Platform team
> consulted: Security, DBA guild
> informed: All engineering
> ```

---

## Context and Problem Statement — **mandatory**

Two or three sentences describing the situation and the problem that forces a decision. Often best
phrased as a question. Give enough context that a newcomer understands *why* a choice was needed.

> **Example:** "Our prototype stores everything in flat JSON files, which no longer scales past a
> few thousand records and offers no transactional guarantees. We need a primary data store that
> supports relational queries and ACID transactions for the upcoming billing feature."

---

## Decision Drivers — *optional (recommended)*

The forces, qualities, concerns, and constraints that pushed the decision one way — *what made you
come to the decision*. These are the criteria the options are judged against.

> **Example:**
> - Legal/compliance risk — billing data must be auditable
> - Fear of a user-data breach → mature security and access controls required
> - Team already knows SQL; limited ops budget
> - Must support transactions

---

## Considered Options — **mandatory**

The alternatives that were genuinely investigated, listed at the same level of abstraction. A bare
list is fine here; detailed analysis goes in "Pros and Cons of the Options".

> **Example:**
> - PostgreSQL
> - MongoDB
> - Keep flat files + add a query layer

---

## Decision Outcome — **mandatory**

The option chosen **and the justification**. State it plainly and tie it back to the decision
drivers. This is the heart of the ADR.

> **Example:** Chosen option: **PostgreSQL**, because it satisfies the transactional and relational
> requirements, the team is already productive with SQL, and managed offerings keep the ops burden
> low — best meeting the legal/auditability and security drivers.

---

## Consequences — **mandatory**

What becomes easier and what becomes harder as a result. Use the `Good, because …` / `Bad,
because …` phrasing to force an honest two-sided view; add `Neutral, because …` where it fits.

> **Example:**
> - Good, because transactions and relational integrity are guaranteed by the engine.
> - Good, because a large hiring pool and tooling ecosystem exist.
> - Bad, because horizontal scaling is harder than with some NoSQL stores.
> - Bad, because schema migrations now need managing.

---

## Confirmation / Validation — *optional*

How the team will confirm the decision is actually implemented as intended — the checks that enforce
it. This turns a decision into something verifiable.

> **Example:** "Enforced via code review of the persistence layer and an architecture fitness test
> in CI that fails if any module imports a non-Postgres data client."

---

## Pros and Cons of the Options — *optional*

A deeper, per-option breakdown of the alternatives — the detailed analysis behind "Considered
Options". Include it when the alternatives are close or the decision is contested; skip it for
obvious calls. Use `Good / Neutral / Bad, because …` per option.

> **Example:**
> ### MongoDB
> - Good, because it scales horizontally with little effort.
> - Neutral, because the team would need to learn its query model.
> - Bad, because multi-document transactions are weaker than Postgres's, raising billing-integrity risk.

---

## More Information — *optional*

Anything else worth keeping: links to related ADRs or docs, the evidence gathered, how much the team
agreed, the confidence level, and when the decision should be revisited.

> **Example:** "Supersedes 0001. Confidence: high. Benchmark notes in /docs/benchmarks/db-2026.md.
> Revisit if write throughput exceeds 50k/s."
