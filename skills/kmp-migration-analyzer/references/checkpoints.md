# Checkpoints

A **checkpoint** is a point in the sequence where the app should **compile and run** even though the
migration isn't finished. Checkpoints are the whole reason the work is ordered the way it is: they
let a human stop, build, test, and confirm nothing broke before continuing. Every report must place
checkpoints explicitly and state the concrete command to verify each one.

## Marker format

Use one of these exact markers in the report so they're easy to scan:

- Phase A (still native Android):
  `✅ CHECKPOINT — Android app should compile & run here`
- Phase B (after a module/batch moves to KMP):
  `✅ CHECKPOINT — <module/batch> migrated to KMP; Android app (and iOS app, if targeted) compiles & runs`

Immediately under each marker, give the **verification step** (see below).

## Where checkpoints go

Place a checkpoint after any step that leaves the project in a green, runnable state:

- **After Groovy → `.kts`** conversion (project still builds, no code changed).
- **After convention-plugin / `build-logic`** migration (project still builds).
- **After each Phase-A library swap** (e.g. Retrofit→Ktor) once the whole project compiles against
  the new API and existing tests pass. One checkpoint per swap is ideal — it isolates that swap.
- **After Views → Compose** conversion of a screen/module (the screen runs on Android, now in Compose).
- **After each module's tests** are migrated and pass (before the module's production code moves).
- **After each Phase-B module/batch** is converted to KMP and the apps build and run.

Do **not** place a checkpoint in the middle of a single change that leaves the build red. If a change
can't reach a green state on its own, it belongs grouped with the rest of its batch up to the next
green point.

## Verification step per checkpoint

State the actual command(s) the user runs to prove the checkpoint holds. Pick based on what exists in
the project; prefer the project's own Gradle tasks. Typical phrasings:

- **Compiles (Android):** `./gradlew assembleDebug` (or the specific module:
  `./gradlew :feature:x:assembleDebug`).
- **Unit tests:** `./gradlew test` (or `:module:test`) — run the **existing** suite; it must still
  pass, since behavior hasn't changed.
- **Instrumented / UI tests:** `./gradlew connectedDebugAndroidTest` where applicable.
- **Runs:** install and launch on a device/emulator and smoke-test the affected screen/flow.
- **Phase B (multiplatform):** additionally `./gradlew :composeApp:assemble` and an iOS build
  (e.g. open the Xcode workspace / `./gradlew :composeApp:linkDebugFrameworkIosSimulatorArm64`) once
  iOS is targeted.

When tests exist for the code being changed, **the verification is "the existing tests still pass."**
That is the strongest possible signal that the migration step was behavior-preserving — which is the
entire objective. If a module has no tests, say so and recommend a manual smoke-test of the flow, and
note that the absence of tests makes that step higher-risk.

## Why this matters (include a short version in the report's intro)

Checkpoints convert a scary "rewrite the whole app" into a series of small, reversible, verifiable
steps. If something breaks, the user knows it was the **last** step — not some change made days ago —
because every prior step was verified green. This is what makes a large migration tractable and is the
reason the report is sequential rather than a flat to-do list.
