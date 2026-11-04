---
name: kmp-unit-testing
description: |
  Unit testing for Kotlin Multiplatform (Android + iOS) - an adversarial "how would I break this?" methodology first, then kotlin.test in commonTest, AssertK, Turbine, fakes instead of mocks, UnconfinedTestDispatcher, SavedStateHandle, dispatcher injection, and an optional kotlin-mutation-testing pass (run only when explicitly requested). Every suite starts by enumerating break vectors - unicode and emoji input, numeric overflow, boundary conditions, ordering and state-machine races - and keeps only distinct, non-overlapping test angles. A unit test runs entirely in-process, in memory, with NO I/O - no disk, no network, no database, no real clock, no real concurrency. It can wire many real classes together as long as none of them cross those boundaries. Use this skill whenever writing or reviewing tests for ViewModels, validators, mappers, use cases, formatters, reducers, or any pure-logic unit. Trigger on phrases like "unit test", "test the ViewModel", "test this logic", "fake repository", "Turbine", "UnconfinedTestDispatcher", "runTest", "kotlin.test", "commonTest", "test the validator", "test the mapper", or "test the use case".
---

# KMP Unit Testing

## Core methodology — test as someone who wants to break the code

**Read this before anything else in this skill. It applies to every test you write, for every class and every function, and it comes before any question of setup, libraries, or syntax.**

Before writing a single test for a unit, switch roles. You are not the author demonstrating that the code works. You are an adversary who has been handed this code and paid to make it produce a wrong answer, crash, hang, or corrupt its state. Assume a bug is in there. Your job is to find the input, ordering, or collaborator response that exposes it.

Three rules govern everything below:

1. **Adversary first.** Enumerate break vectors *in writing* before you write any test code. The happy path is not a starting point — it is one line item in the list.
2. **Creative exhaustion.** The obvious edge cases are the ones the author already handled. The bugs live in the cases nobody imagined: emoji in a name field, an `Int` that wraps, a clock that goes backwards, a response arriving after the screen moved on. Hunt those deliberately.
3. **One angle per test.** Every test must attack the unit from an angle no other test covers. A suite of twenty tests that all fail for the same reason is one test with nineteen copies.

### Step 1 — Map the attack surface

List, explicitly:

- Every public `fun` and every parameter it takes.
- Every observable state field and every emitted event.
- Every branch of every return value (`Result.Success` / each error variant).
- Every collaborator, and every outcome that collaborator can produce.
- Every implicit input: `SavedStateHandle` contents, injected `Clock`, locale, default parameter values.

### Step 2 — For each item, ask: "How would I break this?"

Write the break vectors down as a plain list first — prose, not code. Keep asking until the list stops growing. Only then start writing `@Test` methods, one per surviving vector.

Useful adversary prompts to run over each item:

- What input makes this method's assumption about its argument false?
- What value is legal for the type but illegal for the domain?
- What happens at exactly the boundary, and one step past it?
- What if this arrives twice? Out of order? Never?
- What if the collaborator succeeds but returns nothing useful?
- What would a malicious or careless user paste into this field?

### Step 3 — The break-vector catalogue

Walk this every time you test a unit. Not every category applies to every unit — but you must *consider* each one and consciously skip it, not forget it.

**Text and string input**

- Empty string; whitespace-only; only newlines or tabs; leading/trailing whitespace.
- **Emoji**, including multi-codepoint ones: in Kotlin `"👍🏽".length == 4` (thumbs-up + skin-tone modifier) and `"👨‍👩‍👧‍👦".length == 11` (ZWJ family). Any `length` check, `substring`, truncation, initials-extraction, or character counter is a break vector — assert that a ZWJ sequence is never sliced in half and that a name field of `"😀😀😀"` is not reported as 6 characters.
- Non-Latin scripts: Arabic/Hebrew (RTL), CJK, Cyrillic, Devanagari.
- Combining characters: `"é"` (U+00E9) vs `"é"` (`e` + U+0301) — unequal strings that render identically. Any equality, dedup, or search logic must be tested with both.
- Case folding: `"ß".uppercase() == "SS"` changes the string length. Common `lowercase()` / `uppercase()` are locale-invariant, so Turkish dotless `ı` only breaks code that goes through a platform formatter or locale-aware API in an `actual` (`NSLocale`, `java.util.Locale`) — test those paths on both platforms.
- Very long input (10k chars) and input exactly at the max-length boundary, one below, one above.
- Control characters (U+0000), zero-width space (U+200B), bidi override characters (U+202E).
- Strings that look like other types: `"007"`, `"1e5"`, `"0x10"`, `"NaN"`, `"Infinity"`, `"+49"`, `"  12  "`, `"1,5"` vs `"1.5"`.
- Format-string and path shapes for anything interpolated or formatted: `"%s"`, `"{0}"`, `"../.."`, HTML/Markdown, quotes and backslashes.
- Homoglyphs (Cyrillic `а` U+0430 vs Latin `a` U+0061) wherever uniqueness or dedup matters.

**Numbers and arithmetic**

- `0`, `1`, `-1`, and both sides of every domain boundary (min-1, min, max, max+1).
- **Overflow.** `Int.MAX_VALUE + 1` wraps silently to a negative number in Kotlin — no exception. Every sum, counter, accumulator, multiplication, page-offset (`page * pageSize`), byte-size total, or duration in millis is a break vector. Test with `Int.MAX_VALUE`, `Int.MIN_VALUE`, `Long.MAX_VALUE`.
- `abs(Int.MIN_VALUE)` is still `Int.MIN_VALUE` (negative).
- Integer division truncation, and negative modulo: `-7 % 3 == -1`, not `2` — breaks round-robin and index-wrapping logic.
- Division by zero: `Int` throws, `Double` yields `Infinity`.
- Floating point: `NaN != NaN` (silently breaks `equals`, `distinctUntilChanged`, sorting, and `contains`), `+Infinity`/`-Infinity`, `-0.0 == 0.0` but `(-0.0).equals(0.0)` is false, `0.1 + 0.2 != 0.3`.
- Money or precise decimals held in a `Double` at all — test the rounding boundary (`2.675`), and flag the design.
- Negative values where only non-negative is meaningful (quantity, page size, duration).
- Unit confusion: seconds vs millis, bytes vs KB, percent as `0.5` vs `50`.

**Collections**

- Empty; single element; exactly page-size; page-size + 1.
- Duplicates; all elements identical; elements differing only by case or unicode normalization.
- Unsorted input where sorted order is assumed; ties in a sort (is it stable?).
- Nulls inside a list that Kotlin's types claim is non-null (JSON deserialization does this).
- Very large collections where an O(n^2) path would hang.
- The unit returning a mutable reference the caller can corrupt.

**Time and dates**

- A fake `Clock` that returns the *same* instant on two consecutive calls.
- A clock that goes **backwards** (NTP correction) — any "elapsed" or "expires at" logic.
- DST transitions: a 23-hour day and a 25-hour day; leap day Feb 29; year rollover.
- Epoch 0, negative timestamps, far-future timestamps.
- Exactly-at-midnight, exactly-at-expiry (`expiresAt == now` — is it expired?).
- Timezone mismatch between the stored instant and the formatted output.

**State machine, ordering, and lifecycle**

- The same action dispatched twice in a row (double-tap submit) — idempotency.
- An action arriving while the unit is already loading / a request is in flight.
- A slow result arriving *after* the state has already moved on (a stale response must not overwrite).
- Cancellation mid-flight, then retry.
- Every ordering of loading -> success -> error, including error -> retry -> success.
- Restoration from `SavedStateHandle` after process death, including death *in the middle* of a flow.
- The initial state, before any action is dispatched.

**Collaborators**

- **Every** error branch of every collaborator — each `DataError` variant individually, not one representative.
- The collaborator throwing an exception instead of returning `Result.Error`.
- Success with a degenerate payload: empty list, blank strings, all-null optional fields.
- A `Flow` collaborator that completes without emitting, or emits the same value twice.

### Step 4 — Distinct angles only

> **Two tests are redundant if a single change to the production code would make both fail for the same reason.**

Before you commit to a test, name the specific behavior, branch, or line that this test — and only this test — guards. If you cannot name it, the test does not earn its place.

| Redundant | Distinct |
|---|---|
| `empty email is invalid` + `blank email is invalid` when the validator treats both through one branch | `empty email is invalid` + `whitespace-only email is invalid` when the validator trims first — two different branches |
| Three tests asserting the same error state for three `DataError` variants that map to one `UiText` | One test per variant when each maps to a different message; otherwise one table-driven test |
| `loads notes` + `loads notes and shows them` | `loads notes` + `keeps previous notes when the refresh fails` |
| Two tests differing only in the value of a field the unit never reads | One test; vary the field only where the unit reads it |

Use a **table-driven test** when you have **one angle across many data points** (twelve invalid email shapes, all hitting the same rejection branch). `kotlin.test` has no `@ParameterizedTest`, so loop over the inputs and name the failing input in the assertion:

```kotlin
@Test
fun `malformed emails are rejected`() {
    listOf("", "   ", "no-at-sign", "@no-local", "a@b", "a@@b.com").forEach { email ->
        assertThat(validator.validateEmail(email), name = "email=\"$email\"")
            .isEqualTo(Result.Error(EmailError.INVALID))
    }
}
```

Do not use it to smuggle several genuinely different angles into one method — those deserve their own names, because the test name is the documentation of the break vector.

### Step 5 — Stop condition

The suite is complete when **you cannot name another way to break the unit without changing its public contract.**

If a break vector you can name is not observable through the public surface, the answer is usually that the unit needs a new observation point — not that the vector should be dropped.

To *prove* you stopped at the right point, an optional mutation-testing pass (see [Optional verification](#optional-verification--mutation-testing)) is the strongest available check — run it when the user explicitly asks.

---

## What is a unit test (sharp definition)

A unit test:

- Runs entirely in-process, in memory.
- Does **no I/O** — no disk, no network, no database, no real system clock (use a fake `Clock`), no real concurrency primitives.
- Is independent of every other test, runs in milliseconds.
- May wire as many real classes together as is convenient, **as long as none of them cross those boundaries**.

Examples:

- ✅ `LoginViewModel` + real `LoginValidator` + real `EmailNormalizer` + fake `AuthRepository` → unit.
- ❌ `LoginViewModel` + real `AuthRepository` over Ktor `MockEngine` → integration (network boundary).
- ❌ `UserDao` + in-memory Room → integration (real SQLite engine).

### When to switch to a different skill

- The test crosses an I/O / process / external-state boundary (Room, `MockEngine`, real `Clock`, file system) → use **kmp-integration-testing**.
- The test exercises Compose UI on a device or simulator → use **kmp-ui-testing**.

---

## Stack

| Concern | Library |
|---|---|
| Test framework | `kotlin.test` (`org.jetbrains.kotlin:kotlin-test`, added to `commonTest` by `kmp.library`) |
| Assertions | AssertK (`com.willowtreeapps.assertk:assertk`) |
| Flow / StateFlow | Turbine (`app.cash.turbine:turbine`) |
| Coroutines | `kotlinx-coroutines-test` + `UnconfinedTestDispatcher` |
| Time | `kotlin.time.Clock` injected, faked in tests |

All four libraries are multiplatform and go into `commonTest`. JUnit5 is JVM-only and is not used anywhere: no `org.junit.*` imports, no `@BeforeEach` / `@AfterEach` / `@Nested` / `@ParameterizedTest` / `@DisplayName`.

## Where unit tests live and how they run

Unit tests live in **`commonTest`** of the module under test and run on both platforms from the same source:

| Run on | Command |
|---|---|
| Android (host JVM, no device) | `./gradlew :feature:notes:presentation:testAndroidHostTest` |
| iOS simulator | `./gradlew :feature:notes:presentation:iosSimulatorArm64Test` |
| Every target | `./gradlew :feature:notes:presentation:allTests` |

A unit test is done when it is green on **both** Android and iOS. The Android host test compilation must be enabled for the module (`withHostTestBuilder` in the `kmp.library` convention plugin — see **kmp-module-structure**).

Backticked test names with spaces are fine on the Android host JVM and on iOS.

---

## ViewModel test setup

```kotlin
class NoteListViewModelTest {
    private val testDispatcher = UnconfinedTestDispatcher()

    @BeforeTest
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
    }

    @AfterTest
    fun tearDown() {
        Dispatchers.resetMain()
    }
}
```

`UnconfinedTestDispatcher` runs coroutines eagerly inline — no need to call `advanceUntilIdle()` after every action. `@Test`, `@BeforeTest`, and `@AfterTest` come from `kotlin.test`; `Dispatchers.setMain` works on iOS too.

---

## Testing state with Turbine

```kotlin
@Test
fun `loading notes emits loading then notes`() = runTest {
    val repo = FakeNoteRepository().apply {
        notes = listOf(Note("1", "Hello"))
    }
    val viewModel = NoteListViewModel(repo)

    viewModel.state.test {
        assertThat(awaitItem().notes).isEmpty()
        viewModel.onAction(NoteListAction.OnRefreshClick)
        assertThat(awaitItem().isLoading).isTrue()
        val loaded = awaitItem()
        assertThat(loaded.isLoading).isFalse()
        assertThat(loaded.notes).hasSize(1)
    }
}
```

---

## Testing events (one-time side effects)

```kotlin
@Test
fun `clicking note emits NavigateToDetail`() = runTest {
    val viewModel = NoteListViewModel(FakeNoteRepository())

    viewModel.events.test {
        viewModel.onAction(NoteListAction.OnNoteClick("123"))
        assertThat(awaitItem()).isEqualTo(NoteListEvent.NavigateToDetail("123"))
    }
}
```

---

## Fakes, not mocks

Use **fakes** for every repository, data-source, and service collaborator. In `commonTest` fakes are the only test double: MockK and Mockito rely on JVM bytecode manipulation and do not run on Kotlin/Native, so a test that uses them cannot run on iOS.

A fake is a working in-memory implementation of the real interface:

```kotlin
class FakeNoteRepository : NoteRepository {

    var notes = listOf<Note>()
    var shouldReturnError = false

    override suspend fun getNotes(): Result<List<Note>, DataError.Local> {
        return if (shouldReturnError) Result.Error(DataError.Local.UNKNOWN)
        else Result.Success(notes)
    }

    override suspend fun insertNote(note: Note): EmptyResult<DataError.Local> {
        notes = notes + note
        return Result.Success(Unit)
    }
}
```

Why fakes win:

- Tests assert **behavior** (final state, emitted values), not call patterns.
- Refactoring the production interface doesn't silently break tests because the fake refuses to compile.
- One fake serves dozens of tests; mocks usually duplicate setup per test.

If a collaborator cannot be faked because you don't own its type, wrap it in an interface you do own and fake that.

MockK is acceptable only in **Android-only tests** (`androidHostTest`) and only when:

- The collaborator is a final Android framework class you cannot subclass and don't own, used from `androidMain` code.
- You're verifying a side effect that has no observable result (rare — push back on this).

Fakes reused by several modules live in a shared KMP test-fixtures module (e.g. `:core:testing`), not in `androidHostTest`.

---

## A unit is not a single class

The "unit" is a **unit of logical behavior**, not a single file. A unit test of `LoginViewModel` may instantiate the real `LoginValidator`, real `EmailNormalizer`, and real `PasswordRulesProvider` — all of them are pure logic and stay within the unit-test boundaries. Don't extract a fake just to satisfy an imaginary "one class per test" purity rule.

Rule of thumb: if a collaborator is pure logic and cheap to construct, **use the real thing**. Only fake collaborators that would cross an I/O boundary.

---

## Platform-specific unit tests are still unit tests

If a class lives in `androidMain` or `iosMain` and needs platform types but does **no I/O** (e.g., a pure helper around `Uri` / `NSURL` parsing), its test lives in the matching platform test source set and is still a unit test by this skill's definition:

| Code under test | Test source set | Runs via |
|---|---|---|
| `commonMain` | `commonTest` | Android host JVM + iOS simulator |
| `androidMain`, needs Android framework | `androidDeviceTest` | `connectedAndroidDeviceTest` (device/emulator) |
| `androidMain`, plain JVM types only | `androidHostTest` | `testAndroidHostTest` |
| `iosMain` | `iosTest` | `iosSimulatorArm64Test` |

Don't force Android-framework code onto the JVM by adding shadows or Robolectric — run it on a device.

This is rare. Most genuine units are `commonMain` code tested from `commonTest`. When an `expect`/`actual` pair has logic in both actuals, test the shared contract once in `commonTest` so the same assertions run against both implementations.

---

## SavedStateHandle in tests

Instantiate it directly with a map — no mocking. This works in `commonTest` (`org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-savedstate`):

```kotlin
val savedStateHandle = SavedStateHandle(mapOf("noteId" to "123"))
val viewModel = NoteEditorViewModel(savedStateHandle, FakeNoteRepository())
```

To verify state restoration after process death, set values on the handle, build the ViewModel, and assert the recovered state. The test runs on iOS as well, even though only Android restores the handle automatically at runtime.

---

## When to inject dispatchers

Only inject `CoroutineDispatcher` into a class when **both** are true:

1. The class dispatches to a non-Main dispatcher (e.g., `withContext(Dispatchers.IO) { … }`).
2. The class is directly unit-tested.

ViewModels that only use `viewModelScope` do **not** need an injected dispatcher — `Dispatchers.setMain()` covers them.

If a non-ViewModel class uses `withContext(Dispatchers.IO)` and is unit-tested, inject:

```kotlin
// import kotlinx.coroutines.IO  ← required for Dispatchers.IO in common code
class ImageEncoder(private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO) {
    suspend fun encode(bytes: ByteArray): String = withContext(ioDispatcher) { … }
}

// In test:
val encoder = ImageEncoder(ioDispatcher = UnconfinedTestDispatcher())
```

---

## Optional verification — mutation testing

Once a class's `@Test` methods are written and green, a mutation-testing pass is the strongest way to prove the suite from [Core methodology](#core-methodology--test-as-someone-who-wants-to-break-the-code) is actually complete — it breaks the production code and checks the suite catches the break. It is **not run automatically**: invoke the `kotlin-mutation-testing` skill on the test class only when the user explicitly asks for a mutation test (or you want a deeper confidence check and the user is on board). Writing ordinary unit tests does not require it.

When you do run it:

1. Confirm the production files the test exercises are clean in git (`kotlin-mutation-testing` requires this for safe restore).
2. Run `kotlin-mutation-testing` end-to-end on the test class.
3. For every **survived** mutation in the report:
   - Read the "why the test missed it" line.
   - Either revise the offending test so the mutation would now be killed, or add a new test that catches that break vector.
4. Re-run `kotlin-mutation-testing` on just the revised tests until every mutation is killed (or correctly skipped per that skill's rules).
5. Report to the user: which tests were healthy on first pass, which needed revision, and what the revisions covered.

If a mutation survives because the production behavior it changes is not observable through the public API, the answer is usually that the unit needs a new public observation point — not that the test should be loosened.

---

## Anti-patterns

| Anti-pattern | What to do instead |
|---|---|
| Asserting on mock `verify { … }` call patterns | Use a fake and assert on the resulting state or emission. |
| MockK / Mockito / JUnit5 / `java.*` in `commonTest` | They don't compile or run for iOS. Use fakes, `kotlin.test`, and Kotlin/kotlinx types. |
| Running the suite only on Android | Run `iosSimulatorArm64Test` too — string, number-formatting, and concurrency behavior can differ on Kotlin/Native. |
| `delay()` or `Thread.sleep()` in tests | Use `UnconfinedTestDispatcher` and Turbine. |
| Two `@Test` methods sharing mutable state on the test class | Make state local to each test or reset in `@BeforeTest`. |
| Real `Dispatchers.IO` / `Default` reaching production code under test | Inject a test dispatcher per [When to inject dispatchers](#when-to-inject-dispatchers). |
| Fake silently swallows exceptions and returns success | Fakes should mirror real failure modes; expose a `shouldReturnError` toggle. |
| Testing private fields via reflection | Test through the public surface; if a behavior isn't observable, it shouldn't have a test. |
| Stopping the test suite at the happy path | Walk the [break-vector catalogue](#step-3--the-break-vector-catalogue) before declaring done; a mutation pass is an optional deeper check when requested. |
| Several tests that would all fail for the same one-line production change | Keep one; spend the others on angles from [Step 4 — Distinct angles only](#step-4--distinct-angles-only). |
| Only ASCII, only positive numbers, only mid-range values | Every text input gets a unicode/emoji case; every number gets its boundary and overflow case. |
| Writing tests straight from the implementation you just read | Enumerate break vectors from the *contract* first — reading the implementation makes you test what it does, not what it should do. |
