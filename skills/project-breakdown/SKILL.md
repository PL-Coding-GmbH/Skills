---
name: project-breakdown
description: Plan a software application from a vision into an ordered dependency graph of session-sized work chunks (foundations, contract, per-platform features, integration), with waves showing what can be built in parallel. Use when starting to plan an app from scratch or a large new build where the vision exists but components, stack and order are unclear. Interviews rigorously at the architecture level only, writes per-chunk files plus an overview, and generates an interactive graph viewer. Not for designing a single component in detail.
---

# Project Breakdown

Turn a product vision into an **ordered dependency graph of high-level work chunks**, so the team knows what to build in which order and which chunks can run in parallel sessions.

This skill stays at the architecture level. It does **not** design components (no API endpoints, no class layouts, no protocol details). Each chunk is later explored in depth in its own session; the files this skill writes are the starting context for those sessions, not a living spec.

## What a chunk is

A chunk is one piece of work a single agent session can complete within a 1M-token context, comfortably before the point where you'd want to clear context. Examples: "WebSocket client infrastructure incl. connection lifecycle", "Design system and theme for the Android app", "API contract", "Backend authentication".

Every chunk must pass all four checks:

1. **One outcome.** It can be described in one sentence without "and also".
2. **Verifiable.** There is a clear done state (tests pass, screen works against fakes, pipeline deploys to staging).
3. **Mergeable.** It leaves the codebase in a working state on its own.
4. **One codebase.** It touches exactly one deployable or platform layer (backend, one client app, a shared client module, infrastructure). A feature like auth becomes separate chunks per platform, never one chunk spanning backend and client.

Sizes: **S** (a focused fraction of a session), **M** (a solid session), **L** (a full session, the maximum). Anything bigger than L must be split. Merge S chunks into a related chunk when they would otherwise be trivial standalone work (a single CI config file belongs in the scaffolding chunk; a dedicated CI/CD chunk only exists when the pipeline work is substantial). Stack choices change sizes: two native apps means two sets of client chunks, a shared KMP or cross-platform module means one shared set plus thinner platform chunks.

## The interview rule

Ask a question only if its answer could **add or remove a chunk, change a dependency edge, or change a chunk's size enough to split or merge it.** Everything else is an implementation detail: do not ask it now, write it into the relevant chunk file under "Open questions" for the deep-dive session.

Never fill gaps with assumptions. If something graph-relevant is unknown and not answerable from the repo or what the user said, ask. Do not re-ask what is already in the conversation, in existing breakdown files, or in the repo.

**How to ask:** use the `AskUserQuestion` tool whenever the answer has natural options (up to 4 questions per call, 2–4 options each, recommended option first with "(Recommended)" in the label, `multiSelect` for scope selection). The user can always type a custom answer. Use plain text only for truly open questions (the initial vision). Batch related questions per area; don't fire one question per turn when four fit in one call.

## Files this skill writes

All output goes to `docs/breakdown/` relative to the repo root (or the current directory in a plain session):

```
docs/breakdown/
  INTERVIEW.md     decisions log, appended after every phase (lets an interrupted run resume)
  OVERVIEW.md      the map: vision, stack, areas, waves, chunk index, session prompt template
  graph.json       single source of truth for chunks and edges
  graph.html       generated interactive viewer (never edit by hand)
  chunks/NN-<id>.md   one file per chunk, NN = order printed by the build script
```

Templates: `references/overview-template.md`, `references/chunk-template.md`. Area and foundation checklists: `references/interview-checklists.md`. Graph schema and script usage: `references/graph-format.md`.

Write to `INTERVIEW.md` at the end of every phase. Write a decision there the moment it is made, not at the end.

## Workflow

Create a task list with the phases below so progress is visible.

### Phase 0 — Read existing context

1. If `docs/breakdown/` already exists, read `INTERVIEW.md` and `graph.json` and ask whether to **resume**, **revise**, or **start over**. Never silently overwrite.
2. If the working directory is a repository with code, explore it before asking anything (use an Explore subagent for larger repos): languages and frameworks, modules and deployables, existing features, design system, networking, auth, CI, infrastructure files. Record findings in `INTERVIEW.md` under "Existing foundations".
3. Existing parts are **not** graph nodes. They are listed in OVERVIEW.md as existing foundations, and chunks reference them in their "Builds on" section. Only work still to be done becomes a chunk. If something exists but is clearly incomplete, ask whether finishing it is a chunk.

### Phase 1 — Vision and high-level areas

1. If the user hasn't described the vision, ask for it in plain text: what the product does, who uses it, which platforms, what the first shippable version must include.
2. Derive the **areas**: one per deployable or platform (backend, each client, shared client module, admin panel, …) plus cross-cutting areas (infrastructure, API contract). Use the area discovery list in `references/interview-checklists.md` to find areas the user didn't mention (real-time, push, payments, media, background jobs, admin tooling, third-party integrations). Ask about each candidate the vision leaves open.
3. Establish **scope**: which user-facing features are in the first version. Use a multiSelect question with the features you inferred; anything excluded is recorded as out of scope.
4. **Approval gate 1:** present the areas and in-scope feature list in a short message and get explicit confirmation before continuing.

### Phase 2 — Tech stack and trade-offs

For every area whose stack is not already fixed by the repo or the user:

1. Present 2–3 realistic options with a compact trade-off: what each means for **number and size of chunks** (code sharing, per-platform duplication), team familiarity, ecosystem fit for the required capabilities, and operational cost. Recommend one and say why.
2. Ask with `AskUserQuestion`. Record the decision and the main reason in `INTERVIEW.md`.

Only decide what affects the graph (e.g. "KMP shared module vs. two native apps", "managed backend vs. custom server", "REST vs. GraphQL" only if it changes chunks). Library-level choices are open questions for chunk sessions.

### Phase 3 — Area deep-dive

Go area by area. For each, ask only the graph-relevant questions from `references/interview-checklists.md`, and proactively walk the **foundation checklist**. Foundations are the most important output of the early graph: independent, project-internal building blocks (scaffolding/architecture, design system, real-time client, persistence, infrastructure, CI/CD, auth per platform, fake API layer) that can be built in parallel at the start and later combined into features. Push to identify all of them; for each candidate, confirm it is needed and whether it is big enough to stand alone or folds into another chunk.

Stop drilling once you can draw every chunk and edge with confidence. If you find yourself asking about payloads, schemas, screen layouts or library APIs, you have gone too deep: write it down as an open question instead.

### Phase 4 — Draft the graph

Apply the structural rules below, then write `graph.json` (format in `references/graph-format.md`) and run:

```
python3 <skill-dir>/scripts/build_graph.py docs/breakdown/graph.json --check
```

Fix every error (unknown ids, cycles, oversized chunks) and review the warnings (redundant transitive edges, isolated chunks). Then show the user the draft in chat: a wave table (wave → chunks with area and size), the critical path, and any judgment calls you made. Ask specifically about anything you are unsure of.

**Approval gate 2:** iterate until the user explicitly approves the graph. Log each change in `INTERVIEW.md`.

#### Structural rules

- **Edges are hard dependencies only.** B depends on A only if B cannot start without A's output. "Would be nicer after" is not an edge. Avoid transitive edges (if C needs B and B needs A, C does not also list A unless it uses A's output directly).
- **Scaffolding first per codebase.** Each codebase gets a scaffolding/architecture chunk (build system, module structure, base architecture, CI config when small). Most other chunks of that codebase depend on it.
- **Contract first.** When clients talk to a backend built in this plan, an **API contract** chunk is an early root. It is one chunk; split by domain only for very large applications.
- **Clients develop against fakes.** Each client (or shared client module) gets a **fake API layer** chunk that depends on the contract and models production behavior, including error cases. Client feature chunks depend on the fake layer, never on backend chunks.
- **Integration at the end.** Each client gets a final **integrate with real backend** chunk that depends on the client's feature chunks, the backend chunks it consumes, and the deployment/infrastructure chunk. This is the only place where client and backend meet.
- **Per-platform features.** A user-facing feature becomes one chunk per platform (backend part, each client part), each depending on that platform's foundations.
- **Infrastructure is its own chunk** (provisioning, environments, deployment). CI/CD is its own chunk only if substantial; otherwise it folds into scaffolding.
- **Size check.** Every chunk passes the four checks above and is S, M, or L.

### Phase 5 — Write the files

1. Run the script without `--check` to get the final order and file names:
   `python3 <skill-dir>/scripts/build_graph.py docs/breakdown/graph.json`
   It prints the `NN-<id>.md` name for every chunk and writes `graph.html`.
2. Write one chunk file per chunk from `references/chunk-template.md`. Keep each one short: it is initial context for the chunk's deep-dive session. Every deferred detail from the interview goes into the right chunk's "Open questions".
3. Write `OVERVIEW.md` from `references/overview-template.md`, including the chunk session prompt template.

### Phase 6 — Visual

`graph.html` was generated in Phase 5. It is self-contained (no network needed): waves as columns left to right, nodes colored by area, arrows for dependencies; clicking a node highlights what it depends on and what it unlocks and shows the chunk summary in a side panel.

Tell the user the path and offer to open it. If the user later changes `graph.json`, re-run the script; never edit `graph.html` by hand.

## Finish

End with a brief summary: number of chunks, number of waves, how many chunks can start in parallel in wave 1, the critical path, and the path to `OVERVIEW.md` and `graph.html`.
