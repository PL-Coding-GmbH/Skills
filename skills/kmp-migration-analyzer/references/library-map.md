# Library & API Map

The single source of truth for classifying what you find in the Android codebase. Every dependency,
import, and SDK reference falls into exactly one of three categories:

1. **Direct migration** — there is a KMP-ready replacement. Do it in **Phase A** (while still
   Android) so behavior can be verified before anything structural moves.
2. **Keep on Android + add iOS via expect/actual** — no common replacement; the Android code stays,
   and an iOS `actual` must be added.
3. **Always clarify with the user** — ambiguous; do not guess. See `clarify-cases.md`.

For each direct-migration target, report the **exact canonical target coordinate(s)** below — these
are the user's real version-catalog `module = "group:artifact"` entries — not a generic guess. Then
resolve the latest **KMP-compatible** version on Maven Central (see "Version lookup" at the bottom).

---

## Table of contents
- [Category 1 — Direct migration (Phase A)](#category-1--direct-migration-phase-a)
- [Category 2 — Keep on Android + expect/actual](#category-2--keep-on-android--add-ios-via-expectactual)
- [Category 3 — Always clarify](#category-3--always-clarify)
- [Detection signals (how to find each)](#detection-signals-how-to-find-each)
- [Version lookup on Maven Central](#version-lookup-on-maven-central)

---

## Category 1 — Direct migration (Phase A)

| Detected (Android) | Action / target | Canonical target coordinate(s) |
|---|---|---|
| **Retrofit** (+ OkHttp as HTTP layer) | → Ktor client | `io.ktor:ktor-client-core`, `io.ktor:ktor-client-okhttp` (Android engine), `io.ktor:ktor-client-darwin` (iOS engine), `io.ktor:ktor-client-content-negotiation`, `io.ktor:ktor-client-logging`, `io.ktor:ktor-client-auth`, `io.ktor:ktor-serialization-kotlinx-json` |
| **SharedPreferences** / `PreferenceManager` | → DataStore (Preferences) | `androidx.datastore:datastore-preferences-core` |
| **Moshi / Gson** (JSON ser/deser) | → kotlinx.serialization | `org.jetbrains.kotlinx:kotlinx-serialization-json` |
| **RxJava / RxAndroid / RxKotlin** (Java async/reactive) | → Kotlin coroutines + Flow | `org.jetbrains.kotlinx:kotlinx-coroutines-core` (add `:kotlinx-coroutines-swing` only if a Desktop target exists) |
| **Glide / Picasso / Fresco / Coil(2)** (image loading) | → Coil 3 | `io.coil-kt.coil3:coil-compose`, `io.coil-kt.coil3:coil-network-ktor3` |
| **Dagger / Dagger Hilt** (DI) | → Koin | `io.insert-koin:koin-core`, `io.insert-koin:koin-android`, `io.insert-koin:koin-compose`, `io.insert-koin:koin-compose-viewmodel`, `io.insert-koin:koin-androidx-compose`, `io.insert-koin:koin-androidx-navigation` |
| **`java.time.*`** (Java DateTime API) | → kotlinx-datetime | `org.jetbrains.kotlinx:kotlinx-datetime` |
| **`android.util.Log` / Timber** (logging) | → Kermit | `co.touchlab:kermit` |
| **JUnit 4 / JUnit 5** (test runner) | → kotlin.test | `kotlin-test` |
| **Mockito / Mockito-Kotlin / PowerMock** (Java mocking) | → MockK | `mockk` |
| **Flow/StateFlow tests** needing turbine-style collection | → Turbine | `turbine` |
| **Java assertions** (JUnit asserts / Truth / Hamcrest / AssertJ) | → AssertK | `assertk` |
| **Room** (Android-only setup) | → KMP Room | `androidx.room:room-runtime`, `androidx.room:room-compiler` (via KSP), `androidx.sqlite:sqlite-bundled` |
| **Views / Fragments** (XML UI, no Compose) | → Jetpack Compose **first**, then Compose MP | (Compose BOM / `androidx.compose` artifacts already in project) |
| **Compose UI tests / Espresso** (instrumented & E2E) | → shared Compose UI testing | (Compose `ui-test` artifacts) |
| **`buildConfigField` entries** | → BuildKonfig + convention plugin | `buildkonfig-gradle-plugin` |
| **WindowSizeClass** / adaptive layout | → CMP adaptive | `org.jetbrains.compose.material3.adaptive:adaptive`, `:adaptive-layout`, `:adaptive-navigation` |
| **Jetpack Navigation / Navigation-Compose** | → CMP navigation | `org.jetbrains.androidx.navigation:navigation-compose`, `org.jetbrains.compose.ui:ui-backhandler` |
| **Runtime permission requests** (`ActivityCompat.requestPermissions`, Accompanist permissions) | → Moko permissions | `dev.icerock.moko:permissions`, `:permissions-compose`, `:permissions-notifications` |
| **Groovy Gradle** (`build.gradle`, `settings.gradle`) | → Gradle Kotlin DSL (`.kts`) — **do this first, before any other Phase-A work** | n/a (DSL conversion) |

Notes that matter for the report:
- **Ktor engines are platform-specific**: `okhttp` for Android, `darwin` for iOS. Mention this so
  the reader sets up the engine per platform (an expect/actual-style split in DI, not in source).
- **Coil 3** networking goes through Ktor (`coil-network-ktor3`) — note the version alignment.
- **Views → Compose is itself a Phase-A sub-project.** If a module mixes Views and Compose, only the
  View parts need converting; if a screen is pure Views, the whole screen converts. This can be the
  largest single piece of Phase-A work — call it out explicitly and let it form its own batch(es).
- **Room** is already KMP-capable, so it's a *config* migration (KSP + `sqlite-bundled`), not a
  library swap. The DAOs/entities/queries stay the same.

## Category 2 — Keep on Android + add iOS via expect/actual

These have **no** common-code replacement. The Android implementation **stays as-is**; the report
notes that an iOS `actual` must be authored (behavior parity is the user's responsibility, not a
mechanical swap).

| Detected (Android) | What to report |
|---|---|
| Generic Android-specific SDK with no KMP equivalent (e.g. a vendor SDK, `WindowManager`, platform-only APIs) | Keep Android impl; expose via an `expect` declaration in common, add iOS `actual`. |
| **Notifications** (`NotificationManager`, `NotificationCompat`, WorkManager-driven notifications) | Known equivalent: **KMPNotifier** (`dev.icerock`). Report it as the cross-platform target. |
| **Android Splash Screen API** (`androidx.core:core-splashscreen`, `installSplashScreen()`) | Keep the Android `MainActivity` splash code as-is; **add an iOS storyboard** for the iOS launch screen. No common-code change. |
| **Jetpack dependencies KMP already supports** (Compose, Lifecycle, ViewModel, Navigation-Compose, DataStore, Room, etc.) | **Stay as-is — no action.** These are already multiplatform. Do not flag them as blockers. |

> KMPNotifier coordinate: verify the exact `group:artifact` on Maven Central during analysis rather
> than hardcoding, since the user named the library by intent ("KMPNotifier") not by coordinate.

## Category 3 — Always clarify

Do not guess these. Gather the facts, then handle per `clarify-cases.md` (blocking ones → batched
`AskUserQuestion`; the rest → "Decisions to Resolve"):

- **NDK** (`jni/`, `cpp/`, `externalNativeBuild`, `.so` files, `System.loadLibrary`) → how should
  native code be migrated? No default.
- **Alpha versions** in the version catalog → research whether that alpha's features are supported
  in KMP. If not fully, surface it before committing to an order.
- **Libraries usable in KMP common but with no obvious/direct equivalent** → confirm strategy.
- **System APIs whose iOS behavior differs or is non-obvious** (AlarmManager scheduling, sensors,
  GPS/location, biometrics, background execution) → typically expect/actual, but the iOS mechanism
  must be explored before it's safe to plan.

---

## Detection signals (how to find each)

Search both **dependencies** (version catalog + `build.gradle(.kts)`) and **imports/usages** in
source — a library can be present transitively or used without a direct catalog entry.

| Target | Dependency signal | Source signal (imports / symbols) |
|---|---|---|
| Retrofit | `com.squareup.retrofit2` | `retrofit2.`, `@GET`, `@POST`, `Retrofit.Builder` |
| OkHttp (as HTTP) | `com.squareup.okhttp3` | `okhttp3.`, `OkHttpClient` |
| Moshi / Gson | `com.squareup.moshi`, `com.google.code.gson` | `com.squareup.moshi.`, `com.google.gson.`, `@Json`, `Gson()` |
| RxJava | `io.reactivex.rxjava2/3`, `io.reactivex.rxjava2:rxandroid` | `io.reactivex.`, `Observable<`, `Single<`, `.subscribeOn(` |
| Glide / Picasso / Fresco | `com.github.bumptech.glide`, `com.squareup.picasso`, `com.facebook.fresco` | `Glide.with(`, `Picasso.get(` |
| Dagger / Hilt | `com.google.dagger`, `dagger.hilt` | `@Inject`, `@Module`, `@HiltAndroidApp`, `@AndroidEntryPoint` |
| Java DateTime | (JDK) | `java.time.` (`LocalDate`, `Instant`, `ZonedDateTime`, `Duration`) |
| Logging | (JDK / Timber) | `android.util.Log`, `timber.log.Timber` |
| SharedPreferences | (Android SDK) | `getSharedPreferences(`, `SharedPreferences`, `PreferenceManager` |
| JUnit | `junit:junit`, `org.junit.jupiter` | `org.junit.`, `@Test` (JUnit) |
| Mockito | `org.mockito`, `org.mockito.kotlin` | `org.mockito.`, `mock(`, `whenever(`, `@Mock` |
| Truth/Hamcrest/AssertJ | `com.google.truth`, `org.hamcrest`, `org.assertj` | `assertThat(` from those packages |
| Views/Fragments | `androidx.fragment`, `androidx.appcompat`, layout XML in `res/layout/` | `setContentView(`, `Fragment`, `findViewById`, `ViewBinding`, `DataBinding` |
| BuildConfig fields | `buildConfigField(` in `build.gradle(.kts)` | `BuildConfig.` usages in source |
| WindowSizeClass | `androidx.compose.material3:material3-window-size-class` | `calculateWindowSizeClass(`, `WindowSizeClass` |
| Permissions | `com.google.accompanist:accompanist-permissions` | `requestPermissions(`, `ActivityResultContracts.RequestPermission` |
| Notifications | (Android SDK) | `NotificationManager`, `NotificationCompat`, `createNotificationChannel(` |
| Splash Screen | `androidx.core:core-splashscreen` | `installSplashScreen(`, `@style/Theme.App.Starting` |
| NDK | `externalNativeBuild`, `ndkVersion`, `jni/`, `cpp/`, `CMakeLists.txt` | `System.loadLibrary(`, `external fun` |
| Groovy Gradle | files named `build.gradle` / `settings.gradle` (no `.kts`) | Groovy syntax (`apply plugin:`, no `()` on DSL) |

## Version lookup on Maven Central

For each target coordinate, resolve the latest **KMP-compatible** version (don't assume the Android
version applies):

1. Query the Maven Central search API for the artifact, e.g.
   `https://search.maven.org/solrsearch/select?q=g:"io.ktor"+AND+a:"ktor-client-core"&core=gav&rows=5&wt=json`
   (substitute group `g` and artifact `a`). This returns recent versions newest-first.
2. Prefer the latest **stable** version unless the user is intentionally on a pre-release line.
3. Confirm the artifact actually publishes KMP targets when in doubt — a KMP artifact has a
   `*-kotlin-multiplatform` or per-target (`*-jvm`, `*-iosarm64`, `*-iossimulatorarm64`) modules.
   If only `*-android` exists, it is **not** common-code ready → treat as Category 3 (clarify).
4. If the library is **not** in this map at all, search Maven Central / the web to decide its
   category; if KMP support is ambiguous, raise it as a Decision instead of guessing.

Report the resolved version next to each coordinate so the user can drop it straight into their
version catalog.
