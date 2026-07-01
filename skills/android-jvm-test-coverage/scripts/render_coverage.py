#!/usr/bin/env python3
"""Render a JaCoCo XML report as the Android-Studio-style coverage table.

Android Studio's coverage tool window shows, for a unit-test run:
  - the module total
  - each package
  - each class within a package

with Class %, Method %, Line %, and Branch % columns. This script reproduces
that view from the JaCoCo XML produced by the bundled init script.

Usage:
    python3 render_coverage.py <coverage.xml> --module :core:domain
    python3 render_coverage.py <coverage.xml> --module :core:crypto --package com.example.core.crypto

`--package` (optional, repeatable) limits the class-level detail to matching
packages; the module total always reflects the whole module.
"""

import argparse
import sys
import xml.etree.ElementTree as ET

# JaCoCo emits these counter types per node. We surface the four that match the
# columns Android Studio shows.
COUNTERS = [("CLASS", "Class"), ("METHOD", "Method"), ("LINE", "Line"), ("BRANCH", "Branch")]


def aggregate(nodes):
    """Sum JaCoCo counters across one or more XML nodes.

    Returns {counter_type: (percent_or_None, covered, total)}. A counter is only
    emitted by JaCoCo when it applies (e.g. a class with no branches has no BRANCH
    counter), so a counter absent from every node renders as "n/a".

    Passing several nodes folds them together — used to merge a top-level class
    with its nested/synthetic classes (lambdas, sealed subclasses, anonymous
    classes), matching how Android Studio shows one row per top-level class.
    """
    totals = {counter_type: [0, 0] for counter_type, _ in COUNTERS}  # [covered, total]
    seen = set()
    for node in nodes:
        for counter in node.findall("counter"):
            counter_type = counter.get("type")
            if counter_type not in totals:
                continue
            seen.add(counter_type)
            missed = int(counter.get("missed", "0"))
            covered = int(counter.get("covered", "0"))
            totals[counter_type][0] += covered
            totals[counter_type][1] += missed + covered
    result = {}
    for counter_type, _ in COUNTERS:
        covered, total = totals[counter_type]
        if counter_type not in seen:
            result[counter_type] = (None, 0, 0)
        else:
            percent = (covered / total * 100.0) if total else None
            result[counter_type] = (percent, covered, total)
    return result


def top_level_class(jacoco_name):
    """'com/.../Argon2id$derive$2' -> 'Argon2id'; '.../Result$Success' -> 'Result'.

    Everything before the first '$' is the top-level (outer) class. Nested and
    synthetic classes fold into it.
    """
    return jacoco_name.split("/")[-1].split("$")[0]


def format_metrics(metrics):
    """Render the four counters as an aligned 'Class 100%  Method 92%  ...' string."""
    cells = []
    for counter_type, label in COUNTERS:
        percent, _, _ = metrics[counter_type]
        value = f"{percent:3.0f}%" if percent is not None else " n/a"
        cells.append(f"{label} {value}")
    return "  ".join(cells)


def readable_package(jacoco_name):
    """'com/example/core/domain' -> 'com.example.core.domain'."""
    return jacoco_name.replace("/", ".") if jacoco_name else "(default package)"


def main():
    parser = argparse.ArgumentParser(description="Render JaCoCo XML as an Android-Studio-style table.")
    parser.add_argument("xml", help="Path to the JaCoCo coverage.xml")
    parser.add_argument("--module", required=True, help="Module label to print, e.g. :core:domain")
    parser.add_argument(
        "--package",
        action="append",
        default=[],
        help="Limit class detail to packages containing this substring (repeatable).",
    )
    args = parser.parse_args()

    try:
        tree = ET.parse(args.xml)
    except FileNotFoundError:
        print(
            f"No coverage XML at {args.xml}.\n"
            "Did the jvmCoverage task run for this module, and does the module "
            "have JVM unit tests (src/test)?",
            file=sys.stderr,
        )
        return 1
    except ET.ParseError as error:
        print(f"Could not parse {args.xml}: {error}", file=sys.stderr)
        return 1

    report = tree.getroot()

    # Module total.
    module_metrics = aggregate([report])
    print(f"MODULE {args.module}  —  {format_metrics(module_metrics)}")

    if module_metrics["LINE"][2] == 0:
        print("  (no covered classes — the .exec data was empty or all classes were excluded)")
        return 0

    packages = sorted(report.findall("package"), key=lambda node: node.get("name", ""))
    for package in packages:
        package_name = package.get("name", "")
        readable = readable_package(package_name)
        if args.package and not any(needle in readable for needle in args.package):
            continue

        print()
        print(f"  {readable}")
        print(f"    {format_metrics(aggregate([package]))}")

        # Fold each class's nested/synthetic classes into its top-level class so
        # there is one row per top-level class, as Android Studio shows it.
        groups = {}
        for clazz in package.findall("class"):
            groups.setdefault(top_level_class(clazz.get("name", "")), []).append(clazz)
        for class_label in sorted(groups):
            metrics = aggregate(groups[class_label])
            print(f"      {class_label:<32}  {format_metrics(metrics)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
