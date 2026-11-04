---
name: kmp-ui-testing
description: |
  Compose Multiplatform UI testing for Kotlin Multiplatform (Android + iOS) - shared tests in commonTest via runComposeUiTest, executed on the iOS simulator and as Android device tests (no Robolectric, no host-JVM Compose runtime). Covers UI+real ViewModel integration tests, full feature E2E tests, the Robot pattern for E2E suites, and the Compose 1.11.0 dispatcher change from UnconfinedTestDispatcher to StandardTestDispatcher (which requires explicit advanceUntilIdle / mainClock advancement when coroutines run inside LaunchedEffect, produceState, or rememberCoroutineScope). Use this skill whenever writing or reviewing tests that exercise Compose UI on a real device, emulator, or iOS simulator. Trigger on phrases like "UI test", "Compose test", "runComposeUiTest", "ComposeUiTest", "test the screen", "E2E test", "feature test", "Robot pattern", "test the navigation flow", "instrumented UI test", "device test", or "test the LaunchedEffect".
---

# KMP UI Testing

## What is a UI test (sharp definition)

A UI test:

- Exercises Compose Multiplatform UI on a **real device, emulator, or iOS simulator** via `runComposeUiTest { }`, written once in `commonTest`.
- Tests **behavior**, not the existence of components.
- Comes in two flavors:
  - **UI + real ViewModel** — UI-layer integration. The screen is wired to its real ViewModel, the ViewModel's I/O collaborators are faked or doubled at the device boundary.
  - **Feature E2E** — the full feature graph is wired (real VM, real domain, real data layer) with `MockEngine` / fake `Clock` only at the device boundary. Drives a complete user flow end-to-end.

### When to switch to a different skill

- Pure logic test with no Compose UI involved → use **kmp-unit-testing**.
- Multi-layer test that doesn't render UI (e.g., repository + Room + MockEngine) → use **kmp-integration-testing**.

---

## Stack

| Concern | Library |
|---|---|
| Test framework | `kotlin.test` (`@Test`, `@BeforeTest`, `@AfterTest`) — no JUnit4 rules in shared tests |
| Compose UI test | `org.jetbrains.compose.ui:ui-test` in `commonTest` |
| Test entry point | `runComposeUiTest { }` (`@OptIn(ExperimentalTestApi::class)`) — replaces `createAndroidComposeRule` |
| Assertions | AssertK |
| Network boundary | Ktor `MockEngine` (only when wiring real data layer for E2E) |
| Storage boundary | In-memory Room with `BundledSQLiteDriver` (only for E2E) |
| Runner | iOS simulator (`iosSimulatorArm64Test`) + Android device test (`connectedAndroidDeviceTest`, `AndroidJUnitRunner`) |

Android device-test setup (once per module, in the convention plugin — see **kmp-module-structure**): enable device tests with `withDeviceTestBuilder { sourceSetTreeName = "test" }` so `commonTest` is compiled into them, set `instrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"`, and add `androidx.compose.ui:ui-test-junit4-android` + `androidx.compose.ui:ui-test-manifest` to the `androidDeviceTest` dependencies. iOS needs no extra setup.

---

## Device and simulator only — no Robolectric, no host-JVM Compose

All UI tests live in `commonTest` and run **on a real Android device/emulator and on the iOS simulator**. Two things are explicitly off the table:

- **Robolectric** — simulates the framework just well enough to mislead. Off-device behavior diverges from on-device behavior in subtle ways that matter for UI.
- **Running UI tests on the host JVM** (`testAndroidHostTest`, or a desktop JVM target) — runs the Compose runtime with no real Android or iOS. Skips real layout, real input dispatch, and real lifecycle. Don't use it.

Always:

```kotlin
@OptIn(ExperimentalTestApi::class)
class LoginScreenUiTest {

    @Test
    fun someBehavior() = runComposeUiTest {
        setContent { /* screen under test */ }
        // onNodeWithText(...), mainClock, waitForIdle() are available on `this`
    }
}
```

`createAndroidComposeRule` / `createComposeRule` and `@get:Rule` are JUnit4/Android-only and do not exist in `commonTest`.

### Keeping UI tests off the host JVM

`commonTest` is also compiled into the Android host test run. To stop UI tests from executing there:

- **Name every UI test class `*UiTest`.** The convention plugin excludes that pattern from host test tasks:
  ```kotlin
  tasks.withType<Test>().configureEach {
      filter {
          excludeTestsMatching("*UiTest")
          isFailOnNoMatchingTests = false
      }
  }
  ```
  `Test` tasks are only the JVM host tests — Android device tests and iOS tests are unaffected.
- **Test method names must not contain spaces.** Backticked names fail on Android devices; use `screen_behavior_condition`.

| Run on | Command |
|---|---|
| iOS simulator | `./gradlew :feature:auth:presentation:iosSimulatorArm64Test` |
| Android device/emulator | `./gradlew :feature:auth:presentation:connectedAndroidDeviceTest` |

A UI test is done when it is green on **both**.

---

## Compose version dispatcher rules — the trap

This is the single most common reason a UI test silently hangs or false-passes after upgrading Compose. Read this section before writing any test that touches `LaunchedEffect`, `produceState`, or `rememberCoroutineScope`.

### Step 1 — detect the project's Compose version

Look at `libs.versions.toml` for the `compose-multiplatform` version (the `org.jetbrains.compose` plugin). Compose Multiplatform versions track the Jetpack Compose UI version they are built on. The behavior pivots at **Compose UI 1.11.0** — i.e. Compose Multiplatform 1.11.0.

### Compose 1.11.0+ — `StandardTestDispatcher` is the default

The Compose UI test environment's internal dispatcher changed from `UnconfinedTestDispatcher` to `StandardTestDispatcher`. **Coroutines launched inside composition do not auto-run.** Tests must explicitly advance the clock or wait for idle:

```kotlin
@Test
fun loginScreen_showsError_afterFailedLogin_compose1_11() = runComposeUiTest {
    setContent {
        LoginScreen(viewModel = viewModel)
    }

    onNodeWithText("Sign in").performClick()

    // The LaunchedEffect that observes ViewModel events does NOT advance on its own.
    mainClock.advanceTimeBy(1_000)
    // or:
    waitForIdle()
    // or, for the whole test:
    // mainClock.autoAdvance = true

    onNodeWithText("Wrong password").assertIsDisplayed()
}
```

If you skip the advance, the test either hangs in `waitUntil`, or worse, passes because the assertion runs before the side effect fires.

### Compose < 1.11.0 — `UnconfinedTestDispatcher` is the default

Coroutines run eagerly. `waitForIdle()` is usually enough; explicit clock advances are rarely needed:

```kotlin
@Test
fun loginScreen_showsError_afterFailedLogin_pre1_11() = runComposeUiTest {
    setContent { LoginScreen(viewModel = viewModel) }
    onNodeWithText("Sign in").performClick()
    waitForIdle()
    onNodeWithText("Wrong password").assertIsDisplayed()
}
```

### Rule of thumb

If the project is on Compose UI 1.11.0 or newer **and** the screen under test launches coroutines from composition (`LaunchedEffect`, `produceState`, `rememberCoroutineScope`), assume the test needs `mainClock.advanceTimeBy(...)` or `mainClock.autoAdvance = true`.

---

## What to test (and what NOT to test)

**Don't:**

- Write a UI test for every stateless component in isolation. If the component takes state and emits actions, snapshot-testing every visual variant adds noise without catching regressions. Stateless components belong to previews, not tests.
- Re-test logic that lives in the ViewModel (state transitions, error mapping). That's `kmp-unit-testing` territory.

**Do:**

- Test **screen behavior** with the real ViewModel: state-driven UI changes, action dispatch, error / loading / empty states, restoration after process death.
- Test **feature E2E**: a full happy path through navigation + at least one realistic failure path (network error, validation rejection).

---

## How to enumerate UI test cases

Same discipline. For every screen or flow ask:

> **"How could this user flow break?"**

Default checklist:

- Empty state, loading state, error state, retry path.
- Network failure mid-flow.
- Rapid double-clicks (debouncing / disabled state on submit buttons).
- Back navigation mid-flow.
- Configuration change (rotation) preserves state — Android-only behavior; cover it in an Android-only test in `androidDeviceTest` when it matters.
- Process death restoration via `SavedStateHandle` — Android-only at runtime; the restoration logic itself is unit-tested in `commonTest` (**kmp-unit-testing**).
- iOS-specific: content is not hidden behind the notch / home indicator (safe area insets), and every non-root screen has a visible back button.
- Accessibility (every interactive node has `contentDescription` or visible text).
- RTL layout, but only when the screen has directional layout that matters.
- Long content (overflow, scroll, truncation).

Stop when the next failure mode you can name would re-test something already covered.

---

## Selecting nodes — text > content description > test tag

Always select UI nodes in this priority order:

1. **`onNodeWithText(...)`** — for any node that displays user-visible text (buttons, labels, error messages).
2. **`onNodeWithContentDescription(...)`** — for nodes without visible text but with an accessibility label (icon buttons, image-only nodes, fields whose label sits in `Modifier.semantics { contentDescription = ... }`).
3. **`onNodeWithTag(...)`** — **last resort**, only when neither text nor content description can target the node uniquely. Adding a `Modifier.testTag(...)` to production code purely for tests is acceptable but should be rare; if you reach for it, briefly justify why text/contentDescription wouldn't work.

Why this order: text and content description are real product attributes — they ship to users and accessibility services. Tests using them double as accessibility checks and stay correct as long as the UX stays correct. Test tags are private to the test, easy to forget to update, and offer no user-facing benefit.

### Use string resources, never hardcoded text

If the displayed text comes from `stringResource(Res.string.…)` in production, the **test must read the same resource**, not duplicate the literal. There is no `activity.getString(...)` in shared tests — resolve Compose Multiplatform resources with the suspending `getString`:

```kotlin
// commonTest helper — import org.jetbrains.compose.resources.getString
fun string(resource: StringResource, vararg args: Any): String =
    runBlocking { getString(resource, *args) }
```

```kotlin
// ❌ Bad — string drifts on translation/copy edits.
onNodeWithText("Sign in").performClick()

// ✅ Good — single source of truth.
onNodeWithText(string(Res.string.login_sign_in)).performClick()
```

`Res` is the module's generated resource class; it is `internal`, so the test must live in the same module as the screen. `getString` resolves against the test device's locale.

The same rule applies to `onNodeWithContentDescription(...)` — read the resource, don't hardcode.

### Decision flow

| Production code shows… | Use |
|---|---|
| Visible text from a string resource | `onNodeWithText(string(Res.string.x))` |
| Visible text hardcoded inline | `onNodeWithText("…")` (and consider extracting to a string resource) |
| No text, but a `contentDescription` | `onNodeWithContentDescription(string(Res.string.x))` |
| Neither, and the node is genuinely unidentifiable | Add `Modifier.testTag("login_email_field")` in production, select with `onNodeWithTag(...)` |

---

## UI + real ViewModel

```kotlin
@OptIn(ExperimentalTestApi::class)
class LoginScreenUiTest {

    private lateinit var fakeAuthRepository: FakeAuthRepository
    private lateinit var viewModel: LoginViewModel

    @BeforeTest
    fun setUp() {
        fakeAuthRepository = FakeAuthRepository()
        viewModel = LoginViewModel(
            authRepository = fakeAuthRepository,
            savedStateHandle = SavedStateHandle()
        )
    }

    @Test
    fun submittingValidCredentials_navigatesToHome() = runComposeUiTest {
        setContent {
            LoginScreen(viewModel = viewModel, onLoggedIn = { /* assert via flag */ })
        }

        // Email field uses Modifier.semantics { contentDescription = … } in production.
        onNodeWithContentDescription(string(Res.string.login_email_label))
            .performTextInput("user@pl.com")
        onNodeWithContentDescription(string(Res.string.login_password_label))
            .performTextInput("correctHorseBatteryStaple")
        onNodeWithText(string(Res.string.login_sign_in)).performClick()

        mainClock.advanceTimeBy(2_000)
        onNodeWithText(string(Res.string.home_welcome_title)).assertIsDisplayed()
    }

    @Test
    fun submittingWrongPassword_showsErrorMessage() = runComposeUiTest {
        fakeAuthRepository.shouldReturnError = true

        setContent { LoginScreen(viewModel = viewModel, onLoggedIn = {}) }

        onNodeWithText(string(Res.string.login_sign_in)).performClick()
        mainClock.advanceTimeBy(2_000)

        onNodeWithText(string(Res.string.login_error_wrong_password))
            .assertIsDisplayed()
    }
}
```

The ViewModel is real, the repository is faked at the device boundary, and the screen is exercised through real input dispatch — the identical test runs on an Android device and on the iOS simulator.

---

## Feature E2E

For a full feature flow, wire the entire feature graph and only fake at the device boundary:

```kotlin
@Test
fun loginThenSeeNotes_withMockedNetwork() = runComposeUiTest {
    val mockEngine = MockEngine { request ->
        when (request.url.encodedPath) {
            "/login" -> respond("""{"token":"abc"}""", HttpStatusCode.OK)
            "/notes" -> respond("""[{"id":"1","title":"Hello"}]""", HttpStatusCode.OK)
            else -> respond("", HttpStatusCode.NotFound)
        }
    }
    val featureGraph = LoginFeatureTestGraph(
        mockEngine = mockEngine,
        database = createTestDatabase()   // expect/actual in-memory Room — see kmp-integration-testing
    )

    setContent {
        LoginFeatureRoot(graph = featureGraph)
    }

    onNodeWithContentDescription(string(Res.string.login_email_label))
        .performTextInput("user@pl.com")
    onNodeWithContentDescription(string(Res.string.login_password_label))
        .performTextInput("hunter2")
    onNodeWithText(string(Res.string.login_sign_in)).performClick()
    mainClock.advanceTimeBy(3_000)

    onNodeWithText("Hello").assertIsDisplayed()
}
```

Keep one happy path per feature plus the realistic failure paths. E2E tests are slow — don't redo unit-level coverage at this level.

---

## Robot pattern (E2E only)

When an E2E flow has 3+ test cases, or when multiple tests share the same multi-step setup/assertions, use the Robot pattern to encapsulate UI interactions. Don't reach for it on a single-screen UI+VM integration test — the boilerplate isn't worth it there.

```kotlin
@OptIn(ExperimentalTestApi::class)
class LoginRobot(private val composeUiTest: ComposeUiTest) {

    fun setContent(graph: LoginFeatureTestGraph) = apply {
        composeUiTest.setContent { LoginFeatureRoot(graph = graph) }
    }

    fun enterCredentials(email: String, password: String) = apply {
        composeUiTest.onNodeWithContentDescription(string(Res.string.login_email_label))
            .performTextInput(email)
        composeUiTest.onNodeWithContentDescription(string(Res.string.login_password_label))
            .performTextInput(password)
    }

    fun submit() = apply {
        composeUiTest.onNodeWithText(string(Res.string.login_sign_in)).performClick()
        composeUiTest.mainClock.advanceTimeBy(2_000)
    }

    fun assertOnNotesScreen() = apply {
        composeUiTest.onNodeWithText(string(Res.string.notes_screen_title)).assertIsDisplayed()
    }

    fun assertWrongPasswordErrorVisible() = apply {
        composeUiTest.onNodeWithText(string(Res.string.login_error_wrong_password))
            .assertIsDisplayed()
    }
}
```

Each method returns `apply { … }` so calls can be chained:

```kotlin
@Test
fun loginThenNotes_happyPath() = runComposeUiTest {
    LoginRobot(this)
        .setContent(graph)
        .enterCredentials("user@pl.com", "hunter2")
        .submit()
        .assertOnNotesScreen()
}
```

---

## Synchronization helpers — when to use which

| Helper | Use when |
|---|---|
| `waitForIdle()` | Synchronous recompositions / animations need to settle. Cheap. |
| `mainClock.advanceTimeBy(ms)` | Compose 1.11.0+ with launched coroutines / animations. Most common helper post-1.11. |
| `mainClock.autoAdvance = true` | Whole test is timing-driven and you don't care about exact ticks. |
| `waitUntil(timeoutMillis = …) { … }` | Waiting for a condition driven by a real async source (rare, prefer fakes that you control). |

All of these are members of `ComposeUiTest` (the receiver of `runComposeUiTest`). Never reach for `Thread.sleep` or `Espresso.onIdle()` — they don't integrate with the Compose clock and don't exist on iOS.

---

## Mutation testing here is opt-in

`kotlin-mutation-testing` works on UI tests in principle, but each run costs a device/simulator boot and a full UI test cycle. Don't auto-apply.

Reach for it only when an E2E suite covers a high-value flow (auth, payments) and you want a sanity check that the assertions actually exercise the contract.

---

## Anti-patterns

| Anti-pattern | What to do instead |
|---|---|
| Forgetting `mainClock.advanceTimeBy(...)` on Compose 1.11.0+ | Always check the Compose version; advance the clock when coroutines run inside composition. |
| `Thread.sleep(...)` | `mainClock.advanceTimeBy(...)` or `waitForIdle()`. |
| Reaching for `onNodeWithTag(...)` first | Use `onNodeWithText(...)` or `onNodeWithContentDescription(...)` first. Test tags are the last resort. |
| Hardcoded literals when the production text comes from `stringResource(Res.string.x)` | Read the same resource via `string(Res.string.x)`. One source of truth. |
| Adding `Modifier.testTag(...)` to production "just in case" tests need it later | Only add a tag when text/contentDescription genuinely cannot identify the node. |
| Snapshot-testing every visual variant of a stateless component | Move to previews; UI tests are for behavior. |
| Single mega-test that drives the whole feature | One test per behavior; E2E covers happy path + realistic failures. |
| Robolectric / running UI tests on the host JVM | Always `runComposeUiTest` on an Android device and the iOS simulator; name classes `*UiTest` so the host run skips them. |
| `createAndroidComposeRule`, `@get:Rule`, `ComponentActivity`, `R.string` in `commonTest` | Android/JUnit4-only — use `runComposeUiTest`, `kotlin.test`, and `Res.string`. |
| Only running UI tests on Android | Run `iosSimulatorArm64Test` too — text input, insets, and back navigation behave differently on iOS. |
| Asserting on intermediate UI states without clock advance | Synchronize first, assert second. |
| Re-testing ViewModel logic through UI | Move to `kmp-unit-testing`. UI tests verify the UI reflects the state. |
