---
name: android-jvm-test-coverage
description: >-
  Measure JVM unit-test coverage for a module in a native Android Gradle project
  and print the Android-Studio-style report — the module total plus per-package
  and per-class Class/Method/Line/Branch percentages. Use this skill whenever the
  user wants test coverage for local JVM unit tests (the `src/test` suite, run via
  `testDebugUnitTest` or `test`), asks "what's the coverage of this module/package/
  class", "how well is X tested", wants a coverage report without opening Android
  Studio, or wants the same numbers Android Studio's "Run with Coverage" gives but
  from the command line. Works on both Android library/app modules and pure
  Kotlin/JVM modules. This is for JVM unit tests, NOT on-device instrumented
  (androidTest) coverage.
---

# Android JVM unit-test coverage

Produce the coverage report Android Studio shows for a JVM unit-test run — module
total, per-package, and per-class Class / Method / Line / Branch percentages —
straight from the command line, without modifying any committed build files.

## How it works

`./gradlew testDebugUnitTest` produces **no** coverage on its own; Gradle has no
built-in coverage engine. This skill applies **JaCoCo** at runtime through a Gradle
init script. JaCoCo instruments the compiled bytecode in-process during the normal
JVM test run (no device, no `androidTest`) — the same engine AGP's
`enableUnitTestCoverage` uses internally.

Two bundled files do the work:

- `assets/jvm-coverage.init.gradle.kts` — applied via `--init-script`. It is
  **non-invasive**: it touches no `build.gradle.kts` and produces no git diff. It
  attaches JaCoCo to each module's unit-test task and registers a `jvmCoverage`
  task that emits a JaCoCo XML report. It auto-selects the right test task
  (`testDebugUnitTest` for Android modules, `test` for pure Kotlin/JVM modules).
- `scripts/render_coverage.py` — parses that XML into the Android-Studio-style
  table.

## Always run this in a sub-agent

A coverage run compiles the module, executes its tests, and emits a large amount
of Gradle output before any number appears. None of that belongs in the main
conversation. So **dispatch the run to a single sub-agent** and let it return only
the finished coverage table(s).

Dispatch one general-purpose sub-agent and give it:

- the module Gradle path(s) and matching directory(ies) (see the table below),
- the absolute path to this skill's `assets/jvm-coverage.init.gradle.kts` and
  `scripts/render_coverage.py`,
- the instruction: run steps 2–3 of the workflow, then return **only** the
  rendered table(s) — and, if the Gradle run fails, the `BUILD FAILED` block
  verbatim instead.

If you are *already* running inside a sub-agent, perform the steps directly:
sub-agents cannot dispatch further sub-agents in Claude Code.

## Presenting the result

The renderer's output **is** the report. When you relay the sub-agent's result to
the user, reproduce the rendered table **verbatim** inside a fenced code block so
its monospace column alignment (the `Class … Method … Line … Branch …` layout and
`n/a` cells) is preserved exactly as shown under "Output shape".

Do **not**:

- reformat the table into a Markdown table or any other layout,
- rename, reorder, or merge columns,
- add a "key findings", "gaps", or "what stands out" analysis section unless the
  user explicitly asks for interpretation.

Report the numbers as produced; if the user wants analysis, they will ask.

## Workflow

Let `SKILL_DIR` be this skill's directory. Run all Gradle commands from the project
root (where `gradlew` lives).

### 1. Identify the module

Map what the user named to a Gradle module path and its directory:

| Gradle path            | Directory                  | Type        |
|------------------------|----------------------------|-------------|
| `:core:domain`         | `core/domain`              | pure Kotlin |
| `:core:crypto`         | `core/crypto`              | Android lib |
| `:feature:auth:data`   | `feature/auth/data`        | Android lib |

(The init script handles the Android-vs-Kotlin difference automatically; you only
need the path and directory.)

### 2. Run the coverage task

```bash
./gradlew :core:crypto:jvmCoverage \
  --init-script "$SKILL_DIR/assets/jvm-coverage.init.gradle.kts"
```

The XML lands at `<module-dir>/build/reports/jvm-coverage/coverage.xml`.

To cover **every** module in one pass, run the task unqualified — Gradle invokes it
on each subproject that registered it:

```bash
./gradlew jvmCoverage \
  --init-script "$SKILL_DIR/assets/jvm-coverage.init.gradle.kts"
```

### 3. Render the report

```bash
python3 "$SKILL_DIR/scripts/render_coverage.py" \
  core/crypto/build/reports/jvm-coverage/coverage.xml \
  --module :core:crypto
```

For a whole-project run, call the script once per module's XML (loop over the
`coverage.xml` files under each module's `build/reports/jvm-coverage/`).

To focus the per-class detail on one package, add `--package` (repeatable); the
module total still reflects the whole module:

```bash
python3 "$SKILL_DIR/scripts/render_coverage.py" \
  core/crypto/build/reports/jvm-coverage/coverage.xml \
  --module :core:crypto --package com.example.core.crypto.internal
```

## Output shape

```
MODULE :core:crypto  —  Class  90%  Method  82%  Line  78%  Branch  64%

  com.example.core.crypto
    Class  88%  Method  80%  Line  76%  Branch  61%
      AesGcm                            Class 100%  Method  90%  Line  85%  Branch  70%
      Sha256                            Class 100%  Method 100%  Line 100%  Branch n/a

  com.example.core.crypto.internal
    Class 100%  Method 100%  Line  95%  Branch  80%
      CharArrayUtf8                     Class 100%  Method 100%  Line  95%  Branch  80%
```

`n/a` means JaCoCo emitted no counter of that kind for the node (e.g. a class with
no branches has no Branch %), exactly as Android Studio leaves such cells blank.

## Notes

- **Generated code is excluded** to match what Android Studio treats as "your
  code": `R`/`BuildConfig`/`Manifest`, DI factories, `di/` packages, Compose
  `ComposableSingletons`, and `kotlinx.serialization` `$$serializer` classes. Adjust
  the `coverageExcludes` list in the init script if a project needs different rules.
- **No coverage rows?** Confirm the module actually has a `src/test` suite. Modules
  with only `src/androidTest` have no JVM unit tests and produce an empty report —
  this skill does not cover on-device instrumented tests.
- **Robolectric modules** (e.g. those with `unitTests.isIncludeAndroidResources =
  true`) work unchanged — their unit tests still run on the JVM.
- The init script and XML live under `build/`, which is git-ignored, so running the
  skill never dirties the working tree.
