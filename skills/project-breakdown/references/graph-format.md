# graph.json format and build script

`docs/breakdown/graph.json` is the single source of truth for chunks and edges. Waves, unlocks, the critical path and file numbering are computed by the script, never written by hand.

```json
{
  "project": {
    "name": "Pulse",
    "summary": "Real-time team check-in app for Android, iOS and web."
  },
  "areas": [
    { "id": "contract", "name": "API Contract" },
    { "id": "backend",  "name": "Backend" },
    { "id": "mobile",   "name": "Mobile (KMP)" },
    { "id": "infra",    "name": "Infrastructure", "color": "#8b5cf6" }
  ],
  "chunks": [
    {
      "id": "be-scaffolding",
      "title": "Backend scaffolding & architecture",
      "area": "backend",
      "size": "M",
      "summary": "Project setup, module layout, DB + migrations tooling, CI config.",
      "doneWhen": "Service boots locally and in CI with a health endpoint and an empty migration.",
      "dependsOn": []
    }
  ]
}
```

Fields:
- `areas[].color` is optional; the viewer assigns a distinct color per area in the listed order.
- `chunks[].id`: short kebab-case, prefixed by platform where it helps (`be-`, `android-`, `web-`, `kmp-`).
- `size`: `S`, `M` or `L`.
- `summary`: 1–3 sentences, shown in the viewer's side panel.
- `doneWhen`: one sentence, shown in the side panel.
- `dependsOn`: ids of hard dependencies only.

## Script

```
python3 <skill-dir>/scripts/build_graph.py docs/breakdown/graph.json [--check] [--out PATH]
```

- Validates: unique ids, known areas, known dependency ids, valid sizes, no cycles. Errors exit non-zero.
- Warns: redundant transitive edges, chunks that neither depend on nor unlock anything, waves with a single L chunk bottleneck.
- Computes: wave per chunk (1 + max wave of its dependencies), unlocks, critical path weighted by size (S=1, M=2, L=3), and the `NN-<id>.md` file order (by wave, then area order, then id).
- Without `--check`, writes `graph.html` next to `graph.json` (or to `--out`) from `assets/graph-viewer.html`.
