---
name: android-jacoco-setup
description: >-
  Set up JaCoCo code-coverage on a Gradle-based Android project — apply the jacoco
  plugin, pin its tool version (fetched fresh from Maven Central) in the version
  catalog, and enable unit-test + instrumentation-test coverage on the debug build
  type so AGP generates the coverage report tasks. It adapts to the project layout:
  if the project uses convention plugins in `build-logic`/`buildSrc`, it adds a
  dedicated JaCoCo convention plugin there; for a single-module project without
  convention plugins it edits the module's `build.gradle(.kts)` directly. Use this
  skill whenever the user wants to "set up JaCoCo", "configure code coverage", "add
  coverage to Gradle", "enable test coverage reports", or enable
  `enableAndroidTestCoverage` / `enableUnitTestCoverage`. The
  android-instrumentation-coverage skill cross-references this skill to set up
  coverage on demand. This skill MODIFIES build files (it commits a real setup);
  for non-invasive, on-the-fly JVM coverage use android-jvm-test-coverage instead.
---

# Android JaCoCo setup

Add a real, committed JaCoCo coverage setup to a Gradle Android project. Unlike the
read-only coverage skills, this one **edits build files** — so confirm the target
module(s) with the user before writing, and make the smallest change that fits the
project's existing structure.

Let `SKILL_DIR` be this skill's directory.

## Step 1 — Fetch the latest JaCoCo version

Always pin a current release rather than guessing:

```bash
python3 "$SKILL_DIR/scripts/latest_jacoco_version.py"
```

This prints the latest `org.jacoco:org.jacoco.core` version from Maven Central (e.g.
`0.8.13`). Use that value below. If the fetch fails (offline), tell the user and ask
for a version rather than hardcoding a stale one.

## Step 2 — Detect the project layout

Decide which of the two setups applies:

- **Convention-plugin project** — there is an included build with convention plugins:
  a `build-logic/` (or `buildSrc/`) module whose `build.gradle.kts` has a
  `gradlePlugin { plugins { register(...) } }` block and `*ConventionPlugin.kt`
  sources. Check `settings.gradle.kts` for `includeBuild("build-logic")` and list
  `build-logic/src/main/kotlin/*.kt`.
- **Single-module project** — no convention plugins; coverage config goes straight
  into the module's `build.gradle(.kts)`.

## Step 3a — Convention-plugin project

Add JaCoCo as its own convention plugin, mirroring the project's existing naming.

1. **Add the version-catalog entry.** Under `[versions]` in the catalog (usually
   `gradle/libs.versions.toml`), add:
   ```toml
   jacoco = "<latest-from-step-1>"
   ```

2. **Create the convention plugin.** Copy `assets/JacocoConventionPlugin.kt` into the
   convention-plugin source dir (e.g. `build-logic/src/main/kotlin/`). It applies the
   `jacoco` plugin, pins `toolVersion` from `libs.versions.jacoco`, and enables
   `enableUnitTestCoverage` + `enableAndroidTestCoverage` on `debug` for Android
   library/application modules. Read it before copying — if the project's convention
   plugins use a different version-catalog accessor helper, match it.

3. **Register the plugin id**, matching the existing namespace prefix. Read the
   sibling plugins' `id = "..."` lines to find the project's prefix (shown below as
   `<prefix>`, e.g. `myapp.`), then add to the `gradlePlugin { plugins { } }` block in
   `build-logic/build.gradle.kts`:
   ```kotlin
   register("jacoco") {
       id = "<prefix>.jacoco"
       implementationClass = "JacocoConventionPlugin"
   }
   ```

4. **Apply it to the target module(s).** Add the id to each module's `plugins { }`,
   alongside the convention plugins it already uses:
   ```kotlin
   plugins {
       id("<prefix>.android.library")
       id("<prefix>.jacoco")
   }
   ```

## Step 3b — Single-module project (no convention plugins)

Edit the module's `build.gradle.kts` directly.

1. **Version catalog.** If the project has a `libs.versions.toml`, add
   `jacoco = "<latest>"` under `[versions]` and reference it as
   `libs.versions.jacoco.get()`. If there is genuinely no catalog, inline the version
   string (and mention that a catalog is the more conventional home).

2. **Apply and configure** in the module's `build.gradle.kts`:
   ```kotlin
   plugins {
       // ...existing plugins...
       jacoco
   }

   jacoco {
       toolVersion = libs.versions.jacoco.get()
   }

   android {
       buildTypes {
           debug {
               enableUnitTestCoverage = true
               enableAndroidTestCoverage = true
           }
       }
   }
   ```
   For a pure Kotlin/JVM single module (no `android {}`), just apply `jacoco` and set
   `toolVersion`; the `enable*Coverage` flags are AGP-only.

## Step 4 — Verify the setup compiles and wires up

Confirm the build still configures and the coverage tasks now exist:

```bash
./gradlew :module:tasks --all 2>/dev/null | grep -iE "coverage"
```

After enabling the flags you should see the AGP coverage report task(s) (e.g.
`createDebugAndroidTestCoverageReport` / `createDebugUnitTestCoverageReport`,
depending on AGP version). A failed configuration means the edit was off — fix it
before reporting success.

If this project has a verification gate (e.g. a `/verify` command), run it before
declaring the change done.

## Notes

- **Scope:** this enables both unit-test and instrumentation-test coverage. If the
  user only wants one, drop the other flag (and tell them). For non-invasive JVM-only
  coverage that needs no committed config at all, point them to
  `android-jvm-test-coverage`.
- **Don't duplicate setup:** if the module already applies the jacoco convention
  plugin or has the flags set, report that it's already configured rather than adding
  it twice.
- **Cross-reference:** `android-instrumentation-coverage` calls this skill to enable
  coverage on a module that isn't set up yet, then resumes its run.
