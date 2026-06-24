---
name: kmp-migration-analyzer
description: >
  Analyzes a native Android (Kotlin) codebase to plan its migration to Kotlin Multiplatform
  (KMP) and produces a sequential, ordered migration report with batches and "still compiles &
  runs" checkpoints. It is PURELY ANALYTICAL — it never edits source or performs the migration,
  and it never re-architects code (the goal is a behavior-identical 1:1 translation). Use this
  skill whenever the user wants to plan, scope, sequence, or assess an Android→KMP / Android→
  Kotlin Multiplatform / Android→Compose Multiplatform migration, asks "what do we migrate first",
  "in what order", "how do we batch this migration", "is this module KMP-ready", "what's blocking
  us from going multiplatform", "can this code go in commonMain / shared code", or wants a
  migration roadmap, readiness assessment, or checkpoint plan for moving an Android app (or a
  slice of it) to KMP. Trigger on phrases like "migrate to KMP", "migrate to Kotlin Multiplatform",
  "go multiplatform", "Compose Multiplatform migration", "KMP migration plan", "what's KMP-ready",
  "analyze for multiplatform", or "migration order/roadmap/batches". Do NOT use it to actually
  perform a migration, write production code, or apply coding-style refactors — it only analyzes
  and reports.
---

# KMP Migration Analyzer

This skill helps plan the migration of a **native Android Kotlin** codebase (or a slice of it)
to **Kotlin Multiplatform**. It does not perform the migration. Its single deliverable is a
**sequential migration report** that tells the user *what* must change, *in what order*, *how to
batch it*, and *where the safe checkpoints are* — the points at which the app still compiles and
runs even though the migration isn't finished.

## The one principle everything serves: behavior-identical, 1:1

The migration must change **nothing** about how the app behaves. The whole point is to isolate any
breakage to "caused by the migration" rather than "caused by us changing the code." So:

- **Never propose refactors, redesigns, or "improvements."** Translate what exists, as it exists.
- **Never hand off to the user's coding-practice skills** (data-layer, MVI, presentation, etc.).
  Applying preferred patterns would re-architect code and reintroduce exactly the behavioral risk
  we're trying to eliminate. The **only** skill this one references is `kmp-module-structure`, and
  only for **Gradle-9 quirks and convention-plugin / module structure on the KMP side**.
- **Compose Multiplatform is the UI target** — not SwiftUI or native iOS views — unless the user
  explicitly says otherwise.
- **You are read-only on the target codebase.** You inspect and report; you never edit source.
  The only files you write are the migration report(s) under `docs/migration/`.

## The two-phase migration model (this drives ALL ordering)

Every recommendation is sequenced around two phases. Understanding why this order exists is more
important than memorizing it: we want each step to be verifiable on a *working* app before the
next step, so a human can build and test after every move and know nothing silently broke.

- **Phase A — In-Android prep (project is still native Android, fully verifiable on Android).**
  Replace anything that would not be allowed in KMP common code *while the project is still a
  normal Android project*. Because the app still builds and runs as Android, each replacement can
  be tested against existing behavior before anything structural happens. Examples:
  Groovy Gradle → `.kts`, Retrofit → Ktor, RxJava → coroutines/Flow, Views/Fragments → Compose,
  Mockito → MockK, Moshi/Gson → kotlinx.serialization, SharedPreferences → DataStore,
  Glide → Coil, Hilt → Koin, JUnit → kotlin.test.
  After each Phase-A step, **the Android app still compiles & runs** — that's a checkpoint.

- **Phase B — Structural move into KMP.** Convert modules to KMP modules and move code into
  `commonMain`, replicating the *existing* module structure (see `references/ordering-rules.md`).
  Per-module rule: **migrate that module's tests first, then the module**, so behavior is verified
  as code moves. Each module/batch that compiles & runs after the move is a checkpoint.
  For the `:composeApp` / `:androidApp` split, the Gradle-9 AGP plugin changes, and convention
  plugins, consult the `kmp-module-structure` skill.

## How to run an analysis: two stages inside this one skill

The skill always starts with a cheap whole-project **Survey**, then does **Deep analysis** per
batch. On a small/single-module project the two collapse into one combined report. On a large
project the Survey produces a roadmap and the Deep stage runs per batch, possibly across sessions.

### Stage 1 — Survey (always first; cheap; whole-project)

Read only the **structural surface** — do *not* read every source file here, or a large project
won't fit in one pass:

- `settings.gradle(.kts)` → the module list and project structure.
- each module's `build.gradle(.kts)` → applied plugins and dependencies.
- the version catalog (`gradle/libs.versions.toml`) → libraries, versions, and **alpha versions**.
- `gradle.properties`, `AndroidManifest.xml` files, and a rough inventory of source areas
  (e.g. counts of `*.kt` files, presence of `res/`, `jni/`/`cpp/` for NDK, `*.java` files).

Then produce the roadmap (`docs/migration/00-roadmap.md`, template in
`references/report-templates.md`) containing:

1. **Module graph** + dependency edges; classify as single-module vs multi-module
   (per-feature / per-layer). Flag pure-Kotlin/JVM modules — they must become explicit KMP modules.
2. **Readiness heat-map** per module: already-KMP-clean vs. carries blockers, with blocker tags
   (Groovy, Retrofit, Views, RxJava, Mockito, Hilt, Java `java.time`, Moshi/Gson, etc.). Detect
   blockers by matching dependencies and imports against `references/library-map.md`.
3. **Global migration order** from `references/ordering-rules.md` (Phase-A items first; Groovy→kts
   before everything; leaf/independent modules before their dependents; tests before their module).
4. **Proposed batches** — which modules to migrate together in one working session, size-bounded so
   each batch reaches a checkpoint. This is the user's "how do we batch this" decision support.
5. **Checkpoint plan** — where the app is expected to compile & run (`references/checkpoints.md`).
6. **Decisions to Resolve (global)** — project-wide clarifications (NDK present? alpha versions?
   unknown libraries?). See ambiguity handling below.

If the project is a single module (or small enough to analyze fully in one pass), continue
straight into Stage 2 for the one batch and emit a single combined report instead of stopping.

### Stage 2 — Deep analysis (per batch / per user-given slice)

For one batch (or the slice the user hands you), read the relevant source and produce
`docs/migration/batch-NN-<name>.md` (template in `references/report-templates.md`), linking back to
the roadmap. For each module in the batch, enumerate:

- **Every blocker occurrence**, mapped through `references/library-map.md` to its category + action
  + exact target coordinate(s). Cite `file_path:line` so the user can find each one.
- **Library version lookups.** For each migration target, look up the latest **KMP-compatible**
  version on Maven Central (see `references/library-map.md` for how). For libraries not in the map,
  search Maven Central / the web to determine whether a KMP build exists; if it's ambiguous, raise
  it as a Decision rather than guessing.
- **expect/actual candidates.** Android SDK / system APIs with no common equivalent stay on Android
  and need an iOS `actual`. Where the iOS behavior is non-obvious (AlarmManager scheduling, sensors,
  GPS/location), flag it as a Decision and note that the iOS mechanism must be explored.
- **Resources.** Android `res/` → Compose Multiplatform resources (same structure, different
  folder). List what moves; no behavior change.
- **Build-config fields.** Any `buildConfigField` → BuildKonfig + a convention plugin.
- **Tests.** Classify each test's framework. Migrate **only** the Java-based ones that won't work
  in KMP (Mockito → MockK, JUnit → kotlin.test, Compose/Espresso UI & E2E → shared Compose UI
  testing, Java assertions → AssertK, flow tests → Turbine). **Leave Kotlin-friendly tests that
  already run in KMP unchanged.** Migrate a module's tests *before* the module. **Never change test
  logic** — only swap the framework adapter, so the tests still assert the same behavior.
- **Ordered task list with checkpoints** for the batch (Phase-A items → tests → structural move),
  each checkpoint stating the concrete verification command.
- **Decisions to Resolve (batch-local).**

## Detection: what to look for and what it means

The full mapping lives in `references/library-map.md` (read it before classifying anything). It has
three categories:

1. **Direct migration** (Phase A): there IS a KMP-ready replacement — e.g. Retrofit→Ktor,
   SharedPreferences→DataStore, Moshi/Gson→kotlinx.serialization, RxJava→coroutines/Flow,
   Glide→Coil, Hilt→Koin, JUnit→kotlin.test, Mockito→MockK, `java.time`→kotlinx-datetime,
   permissions→Moko, WindowSizeClass→CMP adaptive, BuildConfig→BuildKonfig, Groovy→`.kts`,
   Views→Compose. Report the exact target coordinate(s) the user uses.
2. **Keep on Android + add iOS via expect/actual**: Android-specific SDKs with no common
   equivalent stay as-is on Android; you note an iOS `actual` is needed. Known equivalents:
   notifications → **KMPNotifier**; Splash Screen API → keep Android `MainActivity`, add an **iOS
   storyboard**. Jetpack dependencies that KMP already supports **stay as-is, no action**.
3. **Always clarify with the user**: NDK usage; alpha versions in the catalog; libraries usable in
   KMP common but with no obvious equivalent; system APIs whose iOS behavior differs. See
   `references/clarify-cases.md`.

## Ambiguity handling (hybrid: gather, then batch-ask)

Run as autonomously as possible. Gather **all** findings first, using web/Maven research to resolve
uncertainty so you ask as few questions as possible. Then:

- Identify the subset of **blocking** decisions — the ones that change ordering or batching
  (typically: NDK strategy, an alpha version that turns out not to be KMP-supported, or how to
  handle a library with no equivalent). Ask **those** in a single batched `AskUserQuestion` so the
  order can be finalized.
- Put **everything else** in the report's **Decisions to Resolve** section, each with options and a
  recommendation, so the user resolves them by reading rather than being interrupted.

## Report rules

- Reports go in the analyzed project's `docs/migration/` folder (`00-roadmap.md` +
  `batch-NN-<name>.md`). They are **sequential** — read top to bottom and worked through in order.
- Mark every safe point with `✅ CHECKPOINT — Android app should compile & run here` (Phase A) or
  `✅ CHECKPOINT — <module/batch> migrated; app compiles & runs` (Phase B), and include the concrete
  verification command, e.g. `./gradlew :app:assembleDebug` plus running the existing test suite.
- Cite `file_path:line` for every concrete finding so the user can act on it directly.
- Read `references/report-templates.md` for the exact section order of each report.

## Reference files (read these as needed)

- `references/library-map.md` — detection signals → category → action → exact target coordinates +
  Maven Central lookup. **Read before classifying any dependency.**
- `references/ordering-rules.md` — two-phase model details, module/Gradle structure rules,
  dependency ordering, and batching heuristics.
- `references/checkpoints.md` — the catalog of "compiles & runs" gates and how to phrase the
  verification step for each.
- `references/clarify-cases.md` — the always-ask-the-user catalog (NDK, alpha versions, unknown
  libs, divergent system APIs) and how to frame each question.
- `references/report-templates.md` — the exact skeletons for `00-roadmap.md` and `batch-NN-*.md`.
