---
name: android-integration-testing
description: |
  Integration testing for Android - wire real production classes together (real repositories, real DAOs, real data sources) and only swap test doubles at the boundaries that leave the device: Ktor MockEngine for HTTP, in-memory Room for storage, fake Clock, WorkManagerTestInitHelper for background work. Instrumented tests preferred (no Robolectric). An integration test crosses at least one I/O / process / external-state boundary. Use this skill whenever writing or reviewing tests that touch a database, network, file system, system clock, or background work scheduler. Trigger on phrases like "integration test", "test the repository with Room", "in-memory Room", "Room.inMemoryDatabaseBuilder", "MockEngine", "MockWebServer", "test sync", "test offline-first", "test the data layer", "test the DAO", or "test with a real database".
---

# Android Integration Testing

## What is an integration test (sharp definition)

An integration test:

- Crosses **at least one** I/O / process / external-state boundary.
- Wires **real** production classes together inside the device — real repositories, real DAOs, real data sources, real mappers, real domain logic.
- Swaps test doubles **only at the boundaries that leave the device**: Ktor `MockEngine` for HTTP, in-memory Room for storage (a real engine but acceptable as the persistence boundary), fake `Clock`, `WorkManagerTestInitHelper` for background scheduling.

Examples:

- ✅ `OfflineFirstNoteRepository` + real `RemoteNoteDataSource` + real `LocalNoteDataSource` + in-memory Room + `MockEngine` → integration.
- ✅ `UserDao` + in-memory Room → integration (real SQLite engine even if data lives in RAM).
- ✅ `LoginViewModel` + real `AuthRepository` + `MockEngine` → integration (network boundary).
- ❌ `OfflineFirstNoteRepository` + fake remote + fake local → unit (no I/O boundary crossed).

### When to switch to a different skill

- The test runs entirely in-memory with no I/O → use **android-unit-testing**.
- The test exercises Compose UI on a device → use **android-ui-testing**.

---

## Stack

| Concern | Library |
|---|---|
| Test framework | JUnit5 (or JUnit4 if the runner forces it) |
| Assertions | AssertK |
| Flow / StateFlow | Turbine |
| Network boundary | Ktor `MockEngine` (or `MockWebServer` for OkHttp) |
| Storage boundary | In-memory Room (`Room.inMemoryDatabaseBuilder`) |
| Time boundary | Fake `Clock` injected via constructor |
| Background work | `WorkManagerTestInitHelper` + `SynchronousExecutor` |
| Runner | Android instrumented (`AndroidJUnitRunner`) |

---

## What "boundary" means — the rule

Inside the device, **everything is real**. At the device boundary, **everything is faked**.

| Boundary | Replacement |
|---|---|
| Network (HTTP) | Ktor `MockEngine` configured per test, or `MockWebServer` for OkHttp |
| Storage (DB) | `Room.inMemoryDatabaseBuilder(context, MyDatabase::class.java).allowMainThreadQueries().build()` |
| Time | Inject a fake `Clock` / `TimeProvider`, never read `System.currentTimeMillis()` directly in production |
| Background work | `WorkManagerTestInitHelper.initializeTestWorkManager(context, config)` with a `SynchronousExecutor` |
| File system | A temp directory created in `@BeforeEach` and deleted in `@AfterEach` |

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

```kotlin
@RunWith(AndroidJUnit4::class)
class NoteRepositoryRoomTest {

    private lateinit var db: NoteDatabase
    private lateinit var repository: OfflineFirstNoteRepository

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(context, NoteDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        repository = OfflineFirstNoteRepository(
            localDataSource = RoomNoteDataSource(db.noteDao()),
            remoteDataSource = FakeRemoteDataSource(),
            applicationScope = TestScope(UnconfinedTestDispatcher())
        )
    }

    @After
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

## Instrumented vs JVM

Most integration tests live under `androidTest/` — Room and the Android runtime require it. Pure-JVM integration is acceptable in two cases:

- Pure-KMP modules where the only boundary is HTTP (use `MockEngine`, no Room).
- A class behind a `Clock`-only boundary that doesn't touch Android.

For everything that touches Room → instrumented.

---

## No Robolectric

Do not use Robolectric in this project. If you reach for it, the test is either:

- A unit test (move it to `android-unit-testing` and replace Android dependencies with fakes), or
- An integration test that must run instrumented on a real device/emulator.

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
| Real network hitting a real server | Always replace with `MockEngine` / `MockWebServer`. |
| Reusing the same in-memory DB across tests without `close()` | Build and close per test in `@Before` / `@After`. |
| Asserting `MockEngine` request order when production code parallelizes | Assert on the *set* of requests, not the order. |
| Letting production code use `Dispatchers.IO` directly | Inject the dispatcher and use `UnconfinedTestDispatcher` in tests. |
| Faking the repository in an integration test | That's a unit test — move it. |
| Reading `System.currentTimeMillis()` in production | Inject a `Clock`; use a fake in tests. |
| Reaching for Robolectric to "speed things up" | Move to unit (with fakes) or run instrumented. |
