---
name: kmp-integration-testing
description: |
  Integration testing for Kotlin Multiplatform (Android + iOS) - wire real production classes together (real repositories, real DAOs, real data sources) and only swap test doubles at the boundaries that leave the device: Ktor MockEngine for HTTP, in-memory Room (bundled SQLite driver) for storage, fake Clock. Tests live in commonTest and run on the iOS simulator and as Android device tests (no Robolectric). An integration test crosses at least one I/O / process / external-state boundary. Use this skill whenever writing or reviewing tests that touch a database, network, file system, or system clock. Trigger on phrases like "integration test", "test the repository with Room", "in-memory Room", "Room.inMemoryDatabaseBuilder", "MockEngine", "test sync", "test offline-first", "test the data layer", "test the DAO", or "test with a real database".
---

# KMP Integration Testing

## What is an integration test (sharp definition)

An integration test:

- Crosses **at least one** I/O / process / external-state boundary.
- Wires **real** production classes together inside the device — real repositories, real DAOs, real data sources, real mappers, real domain logic.
- Swaps test doubles **only at the boundaries that leave the device**: Ktor `MockEngine` for HTTP, in-memory Room for storage (a real engine but acceptable as the persistence boundary), fake `Clock`.

Examples:

- ✅ `OfflineFirstNoteRepository` + real `RemoteNoteDataSource` + real `LocalNoteDataSource` + in-memory Room + `MockEngine` → integration.
- ✅ `UserDao` + in-memory Room → integration (real SQLite engine even if data lives in RAM).
- ✅ `LoginViewModel` + real `AuthRepository` + `MockEngine` → integration (network boundary).
- ❌ `OfflineFirstNoteRepository` + fake remote + fake local → unit (no I/O boundary crossed).

### When to switch to a different skill

- The test runs entirely in-memory with no I/O → use **kmp-unit-testing**.
- The test exercises Compose UI on a device or simulator → use **kmp-ui-testing**.

---

## Stack

| Concern | Library |
|---|---|
| Test framework | `kotlin.test` (no JUnit4/JUnit5 annotations in shared tests) |
| Assertions | AssertK |
| Flow / StateFlow | Turbine |
| Network boundary | Ktor `MockEngine` (`io.ktor:ktor-client-mock`, multiplatform) |
| Storage boundary | In-memory Room (`Room.inMemoryDatabaseBuilder`) with `BundledSQLiteDriver` |
| Time boundary | Fake `kotlin.time.Clock` injected via constructor |
| Runner | iOS simulator (`iosSimulatorArm64Test`) + Android device test (`connectedAndroidDeviceTest`) |

Background work has no shared test harness: WorkManager (`WorkManagerTestInitHelper`) and `BGTaskScheduler` are platform APIs. Test the common logic a worker delegates to here; test the Android worker wiring itself in an Android-only device test (see the **android-background** skill).

---

## What "boundary" means — the rule

Inside the device, **everything is real**. At the device boundary, **everything is faked**.

| Boundary | Replacement |
|---|---|
| Network (HTTP) | Ktor `MockEngine` configured per test, passed to `HttpClientFactory.create(engine)` |
| Storage (DB) | `createTestDatabase()` — an in-memory Room database built per platform (see below) |
| Time | Inject a fake `kotlin.time.Clock`, never read `Clock.System.now()` directly in production |
| File system | A temp directory under okio's `FileSystem.SYSTEM_TEMPORARY_DIRECTORY`, created in `@BeforeTest` and deleted in `@AfterTest` |

If you find yourself faking a *repository* in an integration test, the test is actually a unit test — move it.

---

## How to enumerate the test cases for an integration

Same discipline as unit tests, framed for collaboration:

> **"How could this collaboration break?"**

Default checklist:

- Malformed network response (missing field, wrong type, partial JSON).
- HTTP error status (4xx, 5xx) and how the cache reacts.
- Network timeout / `IOException`.
- Concurrent writer + reader on the same DAO.
- Partial DB write (e.g., parent insert succeeds, child insert fails — does rollback work?).
- Transient failure → retry succeeds (if the production code retries).
- Cache-vs-source-of-truth divergence: stale local row, fresh remote row, which wins?
- Time-driven behavior (token expiry, debounce window) using a fake `Clock`.
- Schema migration paths if the test lives at the DAO/Database level.
- Unknown enum / unknown discriminator in DTOs.

Stop when you cannot name another collaboration failure mode without changing the contract.

---

## Repository + in-memory Room

The in-memory builder is the only platform-specific part: Android needs a `Context`, iOS does not. Hide it behind one `expect` function in `commonTest`:

```kotlin
// commonTest
expect fun testDatabaseBuilder(): RoomDatabase.Builder<NoteDatabase>

fun createTestDatabase(): NoteDatabase = testDatabaseBuilder()
    .setDriver(BundledSQLiteDriver())
    .setQueryCoroutineContext(UnconfinedTestDispatcher())
    .build()

// androidDeviceTest
actual fun testDatabaseBuilder(): RoomDatabase.Builder<NoteDatabase> {
    val context = ApplicationProvider.getApplicationContext<Context>()
    return Room.inMemoryDatabaseBuilder<NoteDatabase>(context)
}

// iosTest
actual fun testDatabaseBuilder(): RoomDatabase.Builder<NoteDatabase> =
    Room.inMemoryDatabaseBuilder<NoteDatabase>()
```

`allowMainThreadQueries()` does not exist with the bundled driver and is not needed — all DAO functions are `suspend`.

```kotlin
class NoteRepositoryRoomIntegrationTest {

    private lateinit var db: NoteDatabase
    private lateinit var repository: OfflineFirstNoteRepository

    @BeforeTest
    fun setUp() {
        db = createTestDatabase()
        repository = OfflineFirstNoteRepository(
            localDataSource = RoomNoteDataSource(db.noteDao()),
            remoteDataSource = FakeRemoteDataSource(),
            applicationScope = TestScope(UnconfinedTestDispatcher())
        )
    }

    @AfterTest
    fun tearDown() {
        db.close()
    }

    @Test
    fun insertingNote_persists_andEmitsThroughFlow() = runTest {
        repository.notesFlow.test {
            assertThat(awaitItem()).isEmpty()
            repository.upsertNote(Note(id = "1", title = "Hello"))
            assertThat(awaitItem()).hasSize(1)
        }
    }
}
```

Always `db.close()` in teardown. In-memory does not mean leak-free.

---

## Repository + Ktor MockEngine

```kotlin
@Test
fun fetchingNotes_parsesResponse_andStoresLocally() = runTest {
    val mockEngine = MockEngine { request ->
        assertThat(request.url.encodedPath).isEqualTo("/notes")
        respond(
            content = """[{"id":"1","title":"Hello"}]""",
            status = HttpStatusCode.OK,
            headers = headersOf(HttpHeaders.ContentType, "application/json")
        )
    }
    val httpClient = HttpClient(mockEngine) {
        install(ContentNegotiation) { json() }
    }
    val remote = KtorNoteDataSource(httpClient)
    val repository = OfflineFirstNoteRepository(
        localDataSource = RoomNoteDataSource(db.noteDao()),
        remoteDataSource = remote,
        applicationScope = TestScope(UnconfinedTestDispatcher())
    )

    val result = repository.fetchNotes()

    assertThat(result).isEqualTo(Result.Success(Unit))
    assertThat(db.noteDao().getAll()).hasSize(1)
}
```

`MockEngine` lets you assert on the request (URL, method, headers, body) inside the lambda. Use that — it's free coverage.

---

## Multi-layer integration

Wire the full data layer to test offline-first behavior end-to-end:

```kotlin
@Test
fun offlineFirstFlow_servesLocalImmediately_thenSyncsAndEmitsRemote() = runTest {
    db.noteDao().upsertAll(listOf(NoteEntity("1", "Local Hello")))
    mockEngine.respondWith("""[{"id":"1","title":"Remote Hello"}]""")

    repository.notesFlow.test {
        assertThat(awaitItem().single().title).isEqualTo("Local Hello")
        repository.fetchNotes()
        assertThat(awaitItem().single().title).isEqualTo("Remote Hello")
    }
}
```

Real `RemoteDataSource` + real `LocalDataSource` + real `Repository`. Only `MockEngine` and the in-memory Room are stand-ins.

---

## Where integration tests live and run

Integration tests are written once in **`commonTest`** and run on both platforms:

| Test touches | Android | iOS |
|---|---|---|
| Only `MockEngine` and/or a fake `Clock` | Host JVM — `testAndroidHostTest` | `iosSimulatorArm64Test` |
| Room (in-memory) | **Device test** — `connectedAndroidDeviceTest` | `iosSimulatorArm64Test` |

Room on the Android target needs a real `Context`, so Room-touching tests cannot run on the Android host JVM (that would require Robolectric). Two conventions keep them out of the host run:

1. **Name the class `*IntegrationTest`.** The `kmp.library` convention plugin excludes that pattern from host test tasks (see **kmp-module-structure**):
   ```kotlin
   tasks.withType<Test>().configureEach {
       filter {
           excludeTestsMatching("*IntegrationTest")
           isFailOnNoMatchingTests = false
       }
   }
   ```
   `Test` tasks are only the JVM host tests — device tests and iOS tests are unaffected.
2. **If the module also has host tests enabled**, `commonTest`'s `expect fun testDatabaseBuilder()` needs an `actual` in `androidHostTest` too. Make it fail loudly instead of pretending to work:
   ```kotlin
   // androidHostTest
   actual fun testDatabaseBuilder(): RoomDatabase.Builder<NoteDatabase> =
       error("Room integration tests run on a device or the iOS simulator, not on the host JVM")
   ```
   Pure database modules (`:core:database`, `:feature:<name>:database`) usually have no unit tests — leave host tests disabled there and skip this stub.

An integration test is done when it is green on the iOS simulator **and** on an Android device/emulator.

---

## No Robolectric

Do not use Robolectric in this project. If you reach for it, the test is either:

- A unit test (move it to `kmp-unit-testing` and replace Android dependencies with fakes), or
- An integration test that must run on a real device/emulator (Android) and the simulator (iOS).

Robolectric simulates the framework just well enough to mislead — failures don't reproduce on device, and passing tests can mask real-device bugs.

---

## Mutation testing here is opt-in

`kotlin-mutation-testing` works on integration tests too, but the per-test cost is high (Room boots, MockEngine spins up). Don't auto-apply it the way the unit-testing skill does.

Reach for it when:

- An integration suite covers a high-value flow (auth, payments, sync correctness).
- You suspect specific tests are passing without exercising the contract.

Run on demand, not as a default step.

---

## Anti-patterns

| Anti-pattern | What to do instead |
|---|---|
| Real network hitting a real server | Always replace with `MockEngine`. |
| `MockWebServer`, `AndroidJUnit4`, `ApplicationProvider`, or `java.*` in `commonTest` | JVM/Android-only — they don't compile for iOS. Keep platform bits in the `actual` of `testDatabaseBuilder()`. |
| Reusing the same in-memory DB across tests without `close()` | Build and close per test in `@BeforeTest` / `@AfterTest`. |
| Asserting `MockEngine` request order when production code parallelizes | Assert on the *set* of requests, not the order. |
| Letting production code use `Dispatchers.IO` directly | Inject the dispatcher and use `UnconfinedTestDispatcher` in tests. |
| Faking the repository in an integration test | That's a unit test — move it. |
| Reading `Clock.System.now()` (or `System.currentTimeMillis()`) in production | Inject a `kotlin.time.Clock`; use a fake in tests. |
| Reaching for Robolectric to "speed things up" | Move to unit (with fakes) or run on device/simulator. |
| Only running the suite on one platform | Run both `connectedAndroidDeviceTest` and `iosSimulatorArm64Test` — the SQLite driver, HTTP engine, and threading differ. |
