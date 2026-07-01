---
name: android-ui-testing
description: |
  Compose UI testing for Android/KMP - instrumented only via createAndroidComposeRule (no Robolectric, no JVM-only Compose runtime). Covers UI+real ViewModel integration tests, full feature E2E tests, the Robot pattern for E2E suites, and the Compose 1.11.0 dispatcher change from UnconfinedTestDispatcher to StandardTestDispatcher (which requires explicit advanceUntilIdle / mainClock advancement when coroutines run inside LaunchedEffect, produceState, or rememberCoroutineScope). Use this skill whenever writing or reviewing tests that exercise Compose UI on a real device or emulator. Trigger on phrases like "UI test", "Compose test", "ComposeTestRule", "createAndroidComposeRule", "test the screen", "E2E test", "feature test", "Robot pattern", "test the navigation flow", "instrumented UI test", "androidTest", or "test the LaunchedEffect".
---

# Android / KMP UI Testing

## What is a UI test (sharp definition)

A UI test:

- Exercises Compose UI on a **real device or emulator** via `createAndroidComposeRule<ComponentActivity>()`.
- Tests **behavior**, not the existence of components.
- Comes in two flavors:
  - **UI + real ViewModel** — UI-layer integration. The screen is wired to its real ViewModel, the ViewModel's I/O collaborators are faked or doubled at the device boundary.
  - **Feature E2E** — the full feature graph is wired (real VM, real domain, real data layer) with `MockEngine` / fake `Clock` only at the device boundary. Drives a complete user flow end-to-end.

### When to switch to a different skill

- Pure logic test with no Compose UI involved → use **android-unit-testing**.
- Multi-layer test that doesn't render UI (e.g., repository + Room + MockEngine) → use **android-integration-testing**.

---

## Stack

| Concern | Library |
|---|---|
| Test framework | JUnit4 (Compose UI testing requires the JUnit4 rules even when JUnit5 is used elsewhere) |
| Compose UI test | `androidx.compose.ui:ui-test-junit4` |
| Compose test rule | `createAndroidComposeRule<ComponentActivity>()` |
| Assertions | AssertK |
| Network boundary | Ktor `MockEngine` (only when wiring real data layer for E2E) |
| Storage boundary | In-memory Room (only for E2E) |
| Runner | Android instrumented (`AndroidJUnitRunner`) |

---

## Instrumented only — no Robolectric, no JVM Compose

All UI tests in this project run **on a real device or emulator** under `androidTest/`. Two tools are explicitly off the table:

- **Robolectric** — simulates the framework just well enough to mislead. Off-device behavior diverges from on-device behavior in subtle ways that matter for UI.
- **`createComposeRule()` (JVM headless variant)** — runs the Compose runtime on the JVM with no real Android. Skips real layout, real input dispatch, and real lifecycle. Don't use it.

Always:

```kotlin
@get:Rule
val composeTestRule = createAndroidComposeRule<ComponentActivity>()
```

---

## Compose version dispatcher rules — the trap

This is the single most common reason a UI test silently hangs or false-passes after upgrading Compose. Read this section before writing any test that touches `LaunchedEffect`, `produceState`, or `rememberCoroutineScope`.

### Step 1 — detect the project's Compose version

Look at `libs.versions.toml` (or `build.gradle.kts`) for `compose-bom` or the `androidx.compose.ui:ui` version. The behavior pivots at **Compose UI 1.11.0**.

### Compose 1.11.0+ — `StandardTestDispatcher` is the default

The Compose UI test rule's internal dispatcher changed from `UnconfinedTestDispatcher` to `StandardTestDispatcher`. **Coroutines launched inside composition do not auto-run.** Tests must explicitly advance the clock or wait for idle:

```kotlin
@Test
fun loginScreen_showsError_afterFailedLogin_compose1_11() {
    composeTestRule.setContent {
        LoginScreen(viewModel = viewModel)
    }

    composeTestRule.onNodeWithText("Sign in").performClick()

    // The LaunchedEffect that observes ViewModel events does NOT advance on its own.
    composeTestRule.mainClock.advanceTimeBy(1_000)
    // or:
    composeTestRule.waitForIdle()
    // or, for the whole test:
    // composeTestRule.mainClock.autoAdvance = true

    composeTestRule.onNodeWithText("Wrong password").assertIsDisplayed()
}
```

If you skip the advance, the test either hangs in `waitUntil`, or worse, passes because the assertion runs before the side effect fires.

### Compose < 1.11.0 — `UnconfinedTestDispatcher` is the default

Coroutines run eagerly. `waitForIdle()` is usually enough; explicit clock advances are rarely needed:

```kotlin
@Test
fun loginScreen_showsError_afterFailedLogin_pre1_11() {
    composeTestRule.setContent { LoginScreen(viewModel = viewModel) }
    composeTestRule.onNodeWithText("Sign in").performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithText("Wrong password").assertIsDisplayed()
}
```

### Rule of thumb

If the project is on Compose UI 1.11.0 or newer **and** the screen under test launches coroutines from composition (`LaunchedEffect`, `produceState`, `rememberCoroutineScope`), assume the test needs `mainClock.advanceTimeBy(...)` or `mainClock.autoAdvance = true`.

---

## What to test (and what NOT to test)

**Don't:**

- Write a UI test for every stateless component in isolation. If the component takes state and emits actions, snapshot-testing every visual variant adds noise without catching regressions. Stateless components belong to previews, not tests.
- Re-test logic that lives in the ViewModel (state transitions, error mapping). That's `android-unit-testing` territory.

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
- Configuration change (rotation) preserves state.
- Process death restoration via `SavedStateHandle`.
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

If the displayed text comes from `stringResource(R.string.…)` in production, the **test must read the same resource**, not duplicate the literal:

```kotlin
// ❌ Bad — string drifts on translation/copy edits.
composeTestRule.onNodeWithText("Sign in").performClick()

// ✅ Good — single source of truth.
val signIn = composeTestRule.activity.getString(R.string.login_sign_in)
composeTestRule.onNodeWithText(signIn).performClick()
```

`composeTestRule.activity` is the host `ComponentActivity` from `createAndroidComposeRule<ComponentActivity>()`; `.getString(...)` resolves against the test runtime's locale.

The same rule applies to `onNodeWithContentDescription(...)` — read the resource, don't hardcode.

### Decision flow

| Production code shows… | Use |
|---|---|
| Visible text from a string resource | `onNodeWithText(activity.getString(R.string.x))` |
| Visible text hardcoded inline | `onNodeWithText("…")` (and consider extracting to a string resource) |
| No text, but a `contentDescription` | `onNodeWithContentDescription(activity.getString(R.string.x))` |
| Neither, and the node is genuinely unidentifiable | Add `Modifier.testTag("login_email_field")` in production, select with `onNodeWithTag(...)` |

---

## UI + real ViewModel

```kotlin
class LoginScreenTest {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<ComponentActivity>()

    private lateinit var fakeAuthRepository: FakeAuthRepository
    private lateinit var viewModel: LoginViewModel

    @Before
    fun setUp() {
        fakeAuthRepository = FakeAuthRepository()
        viewModel = LoginViewModel(
            authRepository = fakeAuthRepository,
            savedStateHandle = SavedStateHandle()
        )
    }

    private fun string(@StringRes id: Int) = composeTestRule.activity.getString(id)

    @Test
    fun submittingValidCredentials_navigatesToHome() {
        composeTestRule.setContent {
            LoginScreen(viewModel = viewModel, onLoggedIn = { /* assert via flag */ })
        }

        // Email field uses Modifier.semantics { contentDescription = … } in production.
        composeTestRule.onNodeWithContentDescription(string(R.string.login_email_label))
            .performTextInput("user@pl.com")
        composeTestRule.onNodeWithContentDescription(string(R.string.login_password_label))
            .performTextInput("correctHorseBatteryStaple")
        composeTestRule.onNodeWithText(string(R.string.login_sign_in)).performClick()

        composeTestRule.mainClock.advanceTimeBy(2_000)
        composeTestRule.onNodeWithText(string(R.string.home_welcome_title)).assertIsDisplayed()
    }

    @Test
    fun submittingWrongPassword_showsErrorMessage() {
        fakeAuthRepository.shouldReturnError = true

        composeTestRule.setContent { LoginScreen(viewModel = viewModel, onLoggedIn = {}) }

        composeTestRule.onNodeWithText(string(R.string.login_sign_in)).performClick()
        composeTestRule.mainClock.advanceTimeBy(2_000)

        composeTestRule.onNodeWithText(string(R.string.login_error_wrong_password))
            .assertIsDisplayed()
    }
}
```

The ViewModel is real, the repository is faked at the device boundary, and the screen is exercised through real input dispatch.

---

## Feature E2E

For a full feature flow, wire the entire feature graph and only fake at the device boundary:

```kotlin
@Test
fun loginThenSeeNotes_withMockedNetwork() {
    val mockEngine = MockEngine { request ->
        when (request.url.encodedPath) {
            "/login" -> respond("""{"token":"abc"}""", HttpStatusCode.OK)
            "/notes" -> respond("""[{"id":"1","title":"Hello"}]""", HttpStatusCode.OK)
            else -> respond("", HttpStatusCode.NotFound)
        }
    }
    val featureGraph = LoginFeatureTestGraph(
        mockEngine = mockEngine,
        database = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java).build()
    )

    composeTestRule.setContent {
        LoginFeatureRoot(graph = featureGraph)
    }

    val activity = composeTestRule.activity
    composeTestRule.onNodeWithContentDescription(activity.getString(R.string.login_email_label))
        .performTextInput("user@pl.com")
    composeTestRule.onNodeWithContentDescription(activity.getString(R.string.login_password_label))
        .performTextInput("hunter2")
    composeTestRule.onNodeWithText(activity.getString(R.string.login_sign_in)).performClick()
    composeTestRule.mainClock.advanceTimeBy(3_000)

    composeTestRule.onNodeWithText("Hello").assertIsDisplayed()
}
```

Keep one happy path per feature plus the realistic failure paths. E2E tests are slow — don't redo unit-level coverage at this level.

---

## Robot pattern (E2E only)

When an E2E flow has 3+ test cases, or when multiple tests share the same multi-step setup/assertions, use the Robot pattern to encapsulate UI interactions. Don't reach for it on a single-screen UI+VM integration test — the boilerplate isn't worth it there.

```kotlin
class LoginRobot(private val composeTestRule: ComposeContentTestRule) {

    private val activity get() = composeTestRule.activity
    private fun string(@StringRes id: Int) = activity.getString(id)

    fun setContent(graph: LoginFeatureTestGraph) = apply {
        composeTestRule.setContent { LoginFeatureRoot(graph = graph) }
    }

    fun enterCredentials(email: String, password: String) = apply {
        composeTestRule.onNodeWithContentDescription(string(R.string.login_email_label))
            .performTextInput(email)
        composeTestRule.onNodeWithContentDescription(string(R.string.login_password_label))
            .performTextInput(password)
    }

    fun submit() = apply {
        composeTestRule.onNodeWithText(string(R.string.login_sign_in)).performClick()
        composeTestRule.mainClock.advanceTimeBy(2_000)
    }

    fun assertOnNotesScreen() = apply {
        composeTestRule.onNodeWithText(string(R.string.notes_screen_title)).assertIsDisplayed()
    }

    fun assertWrongPasswordErrorVisible() = apply {
        composeTestRule.onNodeWithText(string(R.string.login_error_wrong_password))
            .assertIsDisplayed()
    }
}
```

Each method returns `apply { … }` so calls can be chained:

```kotlin
@Test
fun loginThenNotes_happyPath() {
    LoginRobot(composeTestRule)
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
| `composeTestRule.waitForIdle()` | Synchronous recompositions / animations need to settle. Cheap. |
| `composeTestRule.mainClock.advanceTimeBy(ms)` | Compose 1.11.0+ with launched coroutines / animations. Most common helper post-1.11. |
| `composeTestRule.mainClock.autoAdvance = true` | Whole test is timing-driven and you don't care about exact ticks. |
| `composeTestRule.waitUntil(timeoutMillis = …) { … }` | Waiting for a condition driven by a real async source (rare, prefer fakes that you control). |

Never reach for `Thread.sleep` or `Espresso.onIdle()` — they don't integrate with the Compose clock.

---

## Mutation testing here is opt-in

`kotlin-mutation-testing` works on UI tests in principle, but each run costs a device boot and a full instrumented test cycle. Don't auto-apply.

Reach for it only when an E2E suite covers a high-value flow (auth, payments) and you want a sanity check that the assertions actually exercise the contract.

---

## Anti-patterns

| Anti-pattern | What to do instead |
|---|---|
| Forgetting `mainClock.advanceTimeBy(...)` on Compose 1.11.0+ | Always check the Compose version; advance the clock when coroutines run inside composition. |
| `Thread.sleep(...)` | `mainClock.advanceTimeBy(...)` or `waitForIdle()`. |
| Reaching for `onNodeWithTag(...)` first | Use `onNodeWithText(...)` or `onNodeWithContentDescription(...)` first. Test tags are the last resort. |
| Hardcoded literals when the production text comes from `stringResource(R.string.x)` | Read the same resource via `composeTestRule.activity.getString(R.string.x)`. One source of truth. |
| Adding `Modifier.testTag(...)` to production "just in case" tests need it later | Only add a tag when text/contentDescription genuinely cannot identify the node. |
| Snapshot-testing every visual variant of a stateless component | Move to previews; UI tests are for behavior. |
| Single mega-test that drives the whole feature | One test per behavior; E2E covers happy path + realistic failures. |
| Robolectric / `createComposeRule()` JVM | Always instrumented via `createAndroidComposeRule<ComponentActivity>()`. |
| Asserting on intermediate UI states without clock advance | Synchronize first, assert second. |
| Re-testing ViewModel logic through UI | Move to `android-unit-testing`. UI tests verify the UI reflects the state. |
