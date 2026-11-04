# Chunk file template

File name: `docs/breakdown/chunks/NN-<id>.md`, with `NN` from the build script output. Keep it short; this is the starting point for the chunk's own deep-dive session, which produces the real spec.

```markdown
# <Title>

| | |
|---|---|
| ID | `<id>` |
| Area | <Area name> |
| Size | S / M / L |
| Wave | <n> |
| Depends on | `<id>` (<what this chunk uses from it>), … or "none" |
| Unlocks | `<id>`, … or "none" |

## Goal
One or two sentences: the single outcome of this chunk.

## In scope
- The high-level pieces of work that belong here.

## Out of scope
- Related work that belongs to another chunk (name the chunk id) or is excluded from the first version.

## Builds on
- What it consumes from its dependencies and from existing foundations in the repo.

## Provides
- What later chunks rely on from this one (modules, services, components, contracts, deployed environments).

## Done when
- Verifiable criteria. For client feature chunks: works end to end against the fake API layer.

## Decisions from the breakdown
- Stack or architecture decisions from the interview that apply here, with the reason.

## Open questions for the deep-dive session
- Implementation details deliberately deferred during the breakdown.
```
