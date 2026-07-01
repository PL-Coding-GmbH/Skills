# Ordering & Batching Rules

How to turn a pile of detected blockers into a **sequence** a human can execute safely. The goal of
ordering is that the app is *buildable and testable* after every step, so any regression is caught
immediately and attributed to the step that caused it.

## The two phases (recap, with the "why")

- **Phase A — In-Android prep.** Everything that isn't allowed in KMP common code, replaced *while
  the project is still native Android*. Why first: an Android project still builds and runs normally,
  so each replacement can be validated against existing behavior with the existing tooling. Nothing
  has moved yet, so a failure here is unambiguous.
- **Phase B — Structural move into KMP.** Convert modules to KMP and move code into `commonMain`,
  mirroring the existing structure. Why second: it only becomes *possible* once Phase-A blockers are
  gone, and it's the riskier step, so we want a fully green Android app going into it.

## Global ordering rules (apply in this priority)

1. **Groovy → Kotlin DSL (`.kts`) first, project-wide.** Everything downstream (convention plugins,
   KMP plugin application, version-catalog ergonomics) assumes `.kts`. Do `settings.gradle` and every
   `build.gradle` before other Phase-A work. This is itself a checkpoint (the project still builds).
2. **Convention plugins / `build-logic` next.** If the project has a `build-logic` included build or
   convention plugins, migrate them to support KMP module types (`com.android.kotlin.multiplatform.library`,
   the KMP plugin) before converting modules that depend on them. Consult `kmp-module-structure` for
   the Gradle-9 plugin specifics.
3. **Phase-A library swaps**, ordered by blast radius — do the lowest-level, most-depended-on ones
   first (e.g. networking/serialization/DI) so higher layers compile against the new API once.
4. **Within a module: tests before the module.** Migrate a module's tests to the KMP-compatible
   framework *before* moving the module's production code, so the moved code is verified by tests that
   already pass. (Test *logic* is never changed — only the framework adapter.)
5. **Leaf/independent modules before their dependents.** A module can only move to `commonMain` once
   everything it depends on is already KMP-ready. Topologically sort the module graph; migrate leaves
   first. Pure-Kotlin/JVM "domain" modules are usually leaves and are a good first Phase-B batch —
   but remember they must become **explicit KMP modules**, not left as plain JVM.
6. **UI (Views → Compose) is gated.** A screen can't go to Compose Multiplatform until it's Compose
   at all. So Views→Compose conversion is Phase-A work that must precede the Phase-B move of any UI
   module. If only part of a module uses Views, only those parts block that module.

## Module-structure replication rules

The migrated structure **mirrors** the existing one — do not redesign it.

- **Single-module Android app** → one shared module + thin per-platform app modules. Per
  `kmp-module-structure`: a `:composeApp` **KMP library** module holds the shared code/UI, and a thin
  `:androidApp` application module holds the `Activity`, manifest, and Android-only plugins. iOS gets
  its app target. (This split is mandatory under Gradle 9 — see that skill.)
- **Multi-module app (per feature / per layer)** → replicate the *same* modules and the *same*
  dependency edges as KMP modules. A `:feature:x:domain` stays `:feature:x:domain`, now multiplatform.
- **Pure-Kotlin/JVM modules** → convert to explicit KMP modules (add the KMP plugin + targets). They
  do not "just work" as-is in a KMP graph.
- **`androidApp` keeps Android-only things**: the splash-screen setup, Google Services/Firebase
  plugins, the `MainActivity`. These stay on Android; iOS gets its own equivalents (e.g. an iOS
  storyboard for the launch screen).

## Batching heuristics

A **batch** is a set of modules migrated together in one working session, ending at a checkpoint.

- Keep a batch small enough to finish and verify in one session. A good unit is "one feature's
  layers" or "a few leaf modules plus the next layer up."
- A batch must end at a point where **the app compiles & runs** — never split mid-way through a
  change that leaves the project red.
- Respect the topological order: don't batch a module before its dependencies' batch.
- Group by shared blockers when it reduces churn (e.g. all modules using Retrofit can adopt the new
  Ktor client in the same batch so the new networking code is written once).
- The **first batch** is usually: Groovy→kts + convention plugins + the lowest-level shared module
  (often `core:domain` / a pure-Kotlin module) — small, foundational, and a clean early checkpoint.
- The **last batches** are the UI/app modules, after their dependencies are all KMP-ready.

## What stays put (don't sequence work for these)

- Jetpack libraries KMP already supports (Compose, Lifecycle, ViewModel, Navigation-Compose,
  DataStore, Room) — no migration step.
- Android-specific SDKs with no common equivalent — they stay on Android; the only "work" is adding
  an iOS `actual`, which is noted, not ordered as a blocker removal.
