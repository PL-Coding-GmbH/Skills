# Clarify Cases

Some findings have **no safe default** — guessing would risk either a wrong migration plan or a
behavioral change. These must be surfaced to the user. The approach is **hybrid**: resolve as much as
possible with research first, then split what remains into *blocking* questions (asked now) and
*non-blocking* ones (recorded in the report).

## Blocking vs. non-blocking

- **Blocking** = the answer changes the **ordering or batching** of the migration. Ask these in a
  single batched `AskUserQuestion` before finalizing the roadmap. Examples: whether NDK code is in
  scope at all; whether an alpha-version dependency is KMP-supported (if not, its dependents can't
  move); the strategy for a core library that has no KMP equivalent.
- **Non-blocking** = the answer affects *how* a specific piece is migrated but not the overall order.
  Record these in the report's **Decisions to Resolve** section with options + a recommendation, so
  the user resolves them by reading rather than being interrupted.

Always do the research **before** asking, so questions are few and informed.

## The catalog

### 1. NDK / native code
**Detect:** `externalNativeBuild`, `ndkVersion`, `CMakeLists.txt`, `jni/` or `cpp/` dirs, `.so`
files, `System.loadLibrary(...)`, `external fun`.
**Why clarify:** there is no mechanical Android→KMP path for native code; options range from a
Kotlin/Native cinterop, to keeping it Android-only behind expect/actual, to dropping it.
**Ask (blocking):** "This project uses the NDK in `<path>`. How should native code be handled —
shared via cinterop, kept Android-only with an iOS alternative, or out of scope for now?"

### 2. Alpha / pre-release versions in the catalog
**Detect:** versions in `libs.versions.toml` containing `alpha`, `beta`, `rc`, `dev`, `SNAPSHOT`,
or `-M` milestone tags.
**Why clarify:** a bleeding-edge Android version may add capabilities that the KMP build of the same
library doesn't yet expose, so a 1:1 translation might be impossible until KMP catches up.
**What to do first (research):** look up the library on Maven Central; check whether the same (or a
close) version publishes KMP targets and whether the specific feature the project uses is available
there.
**Ask (blocking, only if research is inconclusive or shows a gap):** "`<lib>` is on `<alpha version>`
on Android, but the KMP build at that version <doesn't expose X / lags at version Y>. Do you want to
pin to the KMP-supported version, wait, or keep this Android-only for now?"

### 3. Library usable in KMP common but with no obvious equivalent
**Detect:** a dependency that isn't in `library-map.md` and whose Maven Central listing doesn't
clearly show KMP targets, OR a library that *could* be replaced several ways with no canonical choice.
**Why clarify:** picking the wrong replacement could change behavior or lock the project into an
unwanted dependency.
**Ask (blocking if it's a core/widely-used lib; otherwise Decisions to Resolve):** present what you
found (KMP support status, candidate replacements) and ask which direction the user prefers.

### 4. System APIs whose iOS behavior differs or is non-obvious
**Detect:** `AlarmManager` / `WorkManager` scheduling, `SensorManager` / sensor reads,
`LocationManager` / Fused Location / GPS, biometrics, background execution, exact-time scheduling.
**Why clarify:** these usually become expect/actual, but the iOS side often behaves differently
(e.g. iOS background scheduling and exact alarms have different constraints than Android), so the
iOS `actual` needs design, not a mechanical port — and that can affect behavior parity.
**What to do first (research):** note the closest iOS mechanism (e.g. `UNUserNotificationCenter` /
`BGTaskScheduler` for scheduling, `CoreLocation` for GPS, `CoreMotion` for sensors).
**Record (usually non-blocking):** in Decisions to Resolve, describe the Android usage, the candidate
iOS mechanism, and the parity risk; recommend exploring the iOS behavior before implementing the
`actual`. Promote to a blocking question only if it's central to the app's core flow.

## How to frame questions

- Keep each question to one decision, with 2–4 concrete options and your recommended option first.
- Lead with what you already determined from research, so the user is confirming/choosing, not
  starting from scratch.
- Never block on something you can reasonably default; never default on something that could silently
  change behavior. When unsure which side of that line a case is on, prefer recording it in Decisions
  to Resolve over interrupting.
