# OVERVIEW.md template

`docs/breakdown/OVERVIEW.md` is the map across the whole project. Fill every section; write "none" rather than dropping a section.

```markdown
# <Project name> — Project Breakdown

> Initial plan created with Project Breakdown v2 on <date>. This is starting context for the chunk sessions, not a living spec. Each chunk session produces its own detailed documents.

## Vision
2–4 sentences: what the product is, who it's for, which platforms.

## Scope of the first version
**In:** feature list.
**Out:** explicitly excluded features.

## Tech stack
| Area | Choice | Why (main reason) | Alternatives considered |
|---|---|---|---|

## Areas
| Area | What it covers | Chunks |
|---|---|---|

## Existing foundations
What already exists in the repo and is built upon (or "none — greenfield").

## Structural approach
- Clients develop against a fake API layer built from the contract and connect to the real backend in a final integration chunk per client.
- Any other project-wide rule decided in the interview.

## Waves
| Wave | Chunks (parallelizable) |
|---|---|
| 1 | `id` (Area, size), … |

**Critical path:** `a` → `b` → `c` (the longest chain by size; delays here delay the project).

## Chunk index
| # | Chunk | Area | Size | Wave | Depends on | Unlocks |
|---|---|---|---|---|---|---|
| 01 | [Title](chunks/01-id.md) | … | M | 1 | — | `x`, `y` |

## Global open questions
Questions that affect several chunks and must be settled by whichever chunk session reaches them first.

## Viewing the graph
Open `graph.html` in a browser. Regenerate after editing `graph.json`:
`python3 <skill-dir>/scripts/build_graph.py docs/breakdown/graph.json`

## Starting a chunk session
Use this prompt to begin work on a chunk in a fresh session:

    We're starting chunk `<id>` from docs/breakdown/chunks/<NN-id>.md.
    Read docs/breakdown/OVERVIEW.md for the project context and that chunk file
    for scope, dependencies and open questions. Check that every chunk it depends
    on is complete, and read what they provide. Then interview me about the open
    questions and edge cases for this chunk before planning the implementation.
    Stay within the chunk's scope; anything outside it belongs to another chunk.
```
