#!/usr/bin/env python3
"""Validate a Project Breakdown v2 graph.json, compute waves and the critical
path, print the chunk order, and render the interactive graph viewer.

Usage:
    python3 build_graph.py docs/breakdown/graph.json [--check] [--out PATH]
"""
import argparse
import json
import sys
from pathlib import Path

SIZE_WEIGHT = {"S": 1, "M": 2, "L": 3}
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "graph-viewer.html"
PLACEHOLDER = "/*__GRAPH_DATA__*/null"


def fail(errors):
    print("ERRORS:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)


def validate(data):
    errors = []
    areas = data.get("areas") or []
    chunks = data.get("chunks") or []
    if not chunks:
        errors.append("graph has no chunks")
    area_ids = [a.get("id") for a in areas]
    if len(set(area_ids)) != len(area_ids):
        errors.append("duplicate area ids")
    ids = [c.get("id") for c in chunks]
    seen = set()
    for i in ids:
        if not i:
            errors.append("chunk without id")
        elif i in seen:
            errors.append(f"duplicate chunk id '{i}'")
        seen.add(i)
    for c in chunks:
        cid = c.get("id", "?")
        if c.get("area") not in area_ids:
            errors.append(f"'{cid}': unknown area '{c.get('area')}'")
        if c.get("size") not in SIZE_WEIGHT:
            errors.append(f"'{cid}': size must be S, M or L (got {c.get('size')!r}); split anything bigger than L")
        if not c.get("title"):
            errors.append(f"'{cid}': missing title")
        for d in c.get("dependsOn", []):
            if d == cid:
                errors.append(f"'{cid}': depends on itself")
            elif d not in seen:
                errors.append(f"'{cid}': depends on unknown chunk '{d}'")
    return errors


def find_cycle(chunks):
    deps = {c["id"]: c.get("dependsOn", []) for c in chunks}
    state, stack = {}, []

    def visit(n):
        state[n] = 1
        stack.append(n)
        for d in deps[n]:
            if state.get(d) == 1:
                return stack[stack.index(d):] + [d]
            if d not in state:
                r = visit(d)
                if r:
                    return r
        state[n] = 2
        stack.pop()
        return None

    for n in deps:
        if n not in state:
            r = visit(n)
            if r:
                return r
    return None


def compute(data):
    chunks = data["chunks"]
    by_id = {c["id"]: c for c in chunks}
    area_order = {a["id"]: i for i, a in enumerate(data["areas"])}

    wave = {}

    def w(cid):
        if cid not in wave:
            ds = by_id[cid].get("dependsOn", [])
            wave[cid] = 1 + max((w(d) for d in ds), default=0)
        return wave[cid]

    for c in chunks:
        w(c["id"])

    unlocks = {c["id"]: [] for c in chunks}
    for c in chunks:
        for d in c.get("dependsOn", []):
            unlocks[d].append(c["id"])

    # critical path weighted by size
    order_topo = sorted(chunks, key=lambda c: wave[c["id"]])
    best, prev = {}, {}
    for c in order_topo:
        cid = c["id"]
        ds = c.get("dependsOn", [])
        p = max(ds, key=lambda d: best[d], default=None)
        best[cid] = SIZE_WEIGHT[c["size"]] + (best[p] if p else 0)
        prev[cid] = p
    end = max(best, key=best.get)
    path = []
    while end:
        path.append(end)
        end = prev[end]
    path.reverse()

    ordered = sorted(chunks, key=lambda c: (wave[c["id"]], area_order[c["area"]], c["id"]))
    width = max(2, len(str(len(ordered))))
    files = {c["id"]: f"{str(i + 1).zfill(width)}-{c['id']}.md" for i, c in enumerate(ordered)}

    # warnings
    warnings = []
    ancestors = {}

    def anc(cid):
        if cid not in ancestors:
            s = set()
            for d in by_id[cid].get("dependsOn", []):
                s.add(d)
                s |= anc(d)
            ancestors[cid] = s
        return ancestors[cid]

    for c in chunks:
        ds = c.get("dependsOn", [])
        for d in ds:
            for other in ds:
                if other != d and d in anc(other):
                    warnings.append(f"'{c['id']}' -> '{d}' is redundant (already implied via '{other}'); keep only if '{c['id']}' uses '{d}' directly")
                    break
    if len(chunks) > 1:
        for c in chunks:
            if not c.get("dependsOn") and not unlocks[c["id"]]:
                warnings.append(f"'{c['id']}' is isolated (no dependencies, unlocks nothing)")
    max_wave = max(wave.values())
    for n in range(1, max_wave):
        in_wave = [c for c in chunks if wave[c["id"]] == n]
        if len(in_wave) == 1 and in_wave[0]["size"] == "L":
            warnings.append(f"wave {n} is a single L chunk ('{in_wave[0]['id']}'): a bottleneck, consider splitting it")

    return wave, unlocks, path, ordered, files, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graph")
    ap.add_argument("--check", action="store_true", help="validate and print only, don't write HTML")
    ap.add_argument("--out", help="output HTML path (default: graph.html next to graph.json)")
    args = ap.parse_args()

    gpath = Path(args.graph)
    try:
        data = json.loads(gpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        fail([f"cannot read {gpath}: {e}"])

    errors = validate(data)
    if errors:
        fail(errors)
    cycle = find_cycle(data["chunks"])
    if cycle:
        fail(["dependency cycle: " + " -> ".join(cycle)])

    wave, unlocks, path, ordered, files, warnings = compute(data)
    area_name = {a["id"]: a["name"] for a in data["areas"]}
    max_wave = max(wave.values())

    print(f"{data.get('project', {}).get('name', 'Project')}: {len(ordered)} chunks in {max_wave} waves\n")
    for n in range(1, max_wave + 1):
        row = [c for c in ordered if wave[c["id"]] == n]
        print(f"Wave {n} ({len(row)} parallel):")
        for c in row:
            print(f"  {files[c['id']]:<40} {area_name[c['area']]:<22} {c['size']}")
    print("\nCritical path: " + " -> ".join(path))
    if warnings:
        print("\nWARNINGS:")
        for wmsg in warnings:
            print(f"  - {wmsg}")

    if args.check:
        return

    enriched = {
        "project": data.get("project", {}),
        "areas": data["areas"],
        "criticalPath": path,
        "chunks": [
            {**c, "dependsOn": c.get("dependsOn", []), "wave": wave[c["id"]],
             "unlocks": unlocks[c["id"]], "file": "chunks/" + files[c["id"]]}
            for c in ordered
        ],
    }
    payload = json.dumps(enriched, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        fail([f"placeholder missing in template {TEMPLATE}"])
    out = Path(args.out) if args.out else gpath.with_name("graph.html")
    out.write_text(html.replace(PLACEHOLDER, payload), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
