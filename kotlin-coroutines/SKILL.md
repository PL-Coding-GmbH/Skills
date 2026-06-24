---
name: kotlin-coroutines
description: |
  Kotlin coroutines for Android/KMP — suspend functions, cancellation safety, structured concurrency, parallel execution, synchronization, scopes, blocking code wrapping, and cooperative cancellation. Use this skill whenever writing or reviewing coroutines, suspend functions, coroutine scopes, or any asynchronous Kotlin code that is NOT primarily about Flows. Trigger on phrases like "coroutine", "suspend", "async", "launch", "withContext", "Dispatchers", "ensureActive", "NonCancellable", "Mutex", "limitedParallelism", "coroutineScope", "supervisorScope", "viewModelScope", "application scope", "parallel execution", "blocking code", "runBlocking", "cancellation", or "yield".
---

# Kotlin Coroutines (Android / KMP)

> For Flow types, operators, stateIn/shareIn, backpressure, and lifecycle-aware collection, see **kotlin-flows**.

## Cancellation Safety: ensureActive()

When catching `Exception` or `Throwable` in a suspend context that contains multiple sequential suspend calls, **always** call `coroutineContext.ensureActive()` as the **first line** of the catch block. This prevents silently swallowing `CancellationException`, which would leave the coroutine running after cancellation and cause inconsistent state.

**Correct:**
```kotlin
suspend fun syncData() {
    try {
        val data = remoteDataSource.fetch()   // suspend call 1
        localDataSource.insert(data)          // suspend call 2
    } catch (e: Exception) {
        coroutineContext.ensureActive()        // ← FIRST LINE — rethrows if cancelled
        // Handle the actual error (network, DB, etc.)
        logger.error("Sync failed", e)
    }
}
```

**Wrong — swallows CancellationException:**
```kotlin
suspend fun syncData() {
    try {
        val data = remoteDataSource.fetch()
        localDataSource.insert(data)
    } catch (e: Exception) {
        // BUG: If cancellation happened between fetch() and insert(),
        // CancellationException is caught here and silently swallowed.
        logger.error("Sync failed", e)
    }
}
```

If the catch block only contains a single suspend call or no suspend calls at all, `ensureActive()` is still good practice but less critical.

---

## NonCancellable and Atomic Operations

| Scenario | Approach |
|---|---|
| Cleanup work (close resource, flush log) | `withContext(NonCancellable) { ... }` |
| Multi-step suspend calls that must all complete | Inject `applicationScope`, launch in it |
| Multiple database writes that must be atomic | Room `withTransaction { }` |

**Cleanup — NonCancellable:**
```kotlin
suspend fun disconnect() {
    withContext(NonCancellable) {
        socket.sendCloseFrame()
        socket.awaitClose()
    }
}
```

**Multi-step atomic — application scope:**
```kotlin
class SyncRepository(
    private val applicationScope: CoroutineScope,
    private val remoteDataSource: RemoteDataSource,
    private val localDataSource: LocalDataSource
) {
    suspend fun syncAndNotify() {
        // Runs independently of the caller's lifecycle.
        // If the ViewModel is cleared mid-sync, this still completes.
        applicationScope.launch {
            val data = remoteDataSource.fetch()
            localDataSource.insert(data)
            notificationService.notifyComplete()
        }.join() // optional: suspend until done
    }
}
```

**Database transaction — preferred over application scope for DB:**
```kotlin
suspend fun moveNote(noteId: String, targetFolderId: String) {
    db.withTransaction {
        noteDao.removeFromCurrentFolder(noteId)
        noteDao.insertIntoFolder(noteId, targetFolderId)
    }
}
```

**Never** use `withContext(NonCancellable)` for business logic or multi-step operations — it prevents the coroutine from being cancelled during that block, which is only appropriate for short cleanup work.

---

## Blocking Code and Main Safety

**Rule:** Never call blocking code directly in a suspend function or coroutine. Always wrap it in a dedicated class that exposes a suspend function with the correct dispatcher.

| Work type | Dispatcher |
|---|---|
| File I/O, network, database, stream reads/writes | `Dispatchers.IO` |
| CPU-heavy (image compression, JSON parsing, sorting large lists) | `Dispatchers.Default` |

```kotlin
class FileReader(private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO) {
    suspend fun readFile(path: Path): ByteArray = withContext(ioDispatcher) {
        path.toFile().readBytes()   // blocking call — safe inside withContext(IO)
    }
}
```

```kotlin
class ImageCompressor(private val defaultDispatcher: CoroutineDispatcher = Dispatchers.Default) {
    suspend fun compress(bitmap: Bitmap, quality: Int): ByteArray = withContext(defaultDispatcher) {
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, quality, stream)
        stream.toByteArray()
    }
}
```

**Never use `Thread.sleep()` in a coroutine.** Use `delay()` instead — it suspends without blocking the thread.

---

## Parallel Execution

**Rule:** Never execute two independent suspend functions sequentially. Use `async` or separate `launch` blocks.

### Fail-fast — `coroutineScope + async`

If one fails, all siblings are cancelled:

```kotlin
suspend fun loadDashboard(): Dashboard = coroutineScope {
    val userDeferred = async { userRepository.getUser() }
    val statsDeferred = async { statsRepository.getStats() }
    val notificationsDeferred = async { notificationRepository.getRecent() }

    Dashboard(
        user = userDeferred.await(),
        stats = statsDeferred.await(),
        notifications = notificationsDeferred.await()
    )
}
```

### Independent — `supervisorScope + async`

If one fails, the others continue:

```kotlin
suspend fun loadDashboard(): Dashboard = supervisorScope {
    val userDeferred = async { userRepository.getUser() }
    val statsDeferred = async {
        try {
            statsRepository.getStats()
        } catch (e: Exception) {
            coroutineContext.ensureActive()
            null  // stats are optional
        }
    }

    Dashboard(
        user = userDeferred.await(),
        stats = statsDeferred.await()
    )
}
```

### awaitAll for collecting results

```kotlin
suspend fun fetchAllPages(urls: List<String>): List<Page> = coroutineScope {
    urls.map { url ->
        async { api.fetchPage(url) }
    }.awaitAll()
}
```

### Separate launch blocks — when return values aren't needed

```kotlin
viewModelScope.launch {
    launch { analyticsTracker.trackScreenView("profile") }
    launch { prefetchService.prefetchRelatedData(userId) }
    // Both run in parallel, neither blocks the other
}
```

---

## Synchronization

| Need | Tool |
|---|---|
| Protect a critical section of **suspend** code | `Mutex` |
| Confine **all** execution (including non-suspend) to one thread | `limitedParallelism(1)` |

### Mutex — for suspend-only critical sections

```kotlin
class InMemoryCache<K, V> {
    private val mutex = Mutex()
    private val map = mutableMapOf<K, V>()

    suspend fun getOrPut(key: K, compute: suspend () -> V): V {
        mutex.withLock {
            map[key]?.let { return it }
            val value = compute()
            map[key] = value
            return value
        }
    }
}
```

### limitedParallelism(1) — for thread confinement

```kotlin
class TokenStorage(
    private val prefs: SharedPreferences
) {
    // Single-thread dispatcher — safe for non-suspend SharedPreferences calls
    private val dispatcher = Dispatchers.IO.limitedParallelism(1)

    suspend fun saveToken(token: String) = withContext(dispatcher) {
        prefs.edit().putString("token", token).commit()
    }

    suspend fun getToken(): String? = withContext(dispatcher) {
        prefs.getString("token", null)
    }
}
```

Use `Dispatchers.IO.limitedParallelism(1)` for I/O-bound confined work, `Dispatchers.Default.limitedParallelism(1)` for CPU-bound confined work.

---

## Custom Scopes and Application Scope

Custom coroutine scopes should use `SupervisorJob()` so one child failure doesn't cancel the entire scope:

```kotlin
val myScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
```

### Application scope — Android / KMP

Create in the `Application` class and inject via Koin:

```kotlin
class MyApp : Application() {
    val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
}
```

```kotlin
// Koin module
val appModule = module {
    single<CoroutineScope>(named("applicationScope")) {
        (androidApplication() as MyApp).applicationScope
    }
}
```

```kotlin
// Inject where needed
class SyncRepository(
    @Named("applicationScope") private val applicationScope: CoroutineScope,
    private val api: Api,
    private val dao: NoteDao
) {
    suspend fun syncNotes() {
        applicationScope.launch {
            val notes = api.fetchNotes()
            dao.upsertAll(notes)
        }.join()
    }
}
```

**When to use application scope:** Multi-step operations that must outlive the ViewModel or screen lifecycle (e.g., sync that started from a screen but must finish even if the user navigates away). If the multi-step work is purely database operations, prefer a Room transaction instead.

---

## Cooperative Cancellation

### ensureActive() — cheap check in loops

```kotlin
suspend fun processItems(items: List<Item>) {
    for (item in items) {
        ensureActive()  // throws CancellationException if cancelled — cheap, no thread yield
        processItem(item)
    }
}
```

### yield() — when converting blocking code to suspend

```kotlin
suspend fun processLargeFile(file: File) = withContext(Dispatchers.IO) {
    file.bufferedReader().useLines { lines ->
        lines.forEach { line ->
            yield()  // checks cancellation AND yields the thread to other coroutines
            parseLine(line)
        }
    }
}
```

**Pick `ensureActive()` for loops** (cheaper — just checks a flag). **Pick `yield()` when wrapping blocking code** (yields the thread so other coroutines on the same dispatcher can run).

---

## runBlocking

`runBlocking` is allowed **only** in:

1. **Tests** — `runTest` is preferred, but `runBlocking` works for simple cases
2. **Plain Kotlin `main()` function** — entry point that bridges to suspend world
3. **Contexts where coroutines can't be launched AND you're certain it's a background thread** — e.g., a Retrofit `Interceptor` (OkHttp guarantees this runs on its own thread pool)

```kotlin
// Retrofit interceptor — OK because OkHttp runs interceptors on background threads
class AuthInterceptor(private val tokenProvider: TokenProvider) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = runBlocking { tokenProvider.getToken() }
        val request = chain.request().newBuilder()
            .addHeader("Authorization", "Bearer $token")
            .build()
        return chain.proceed(request)
    }
}
```

**NEVER** use `runBlocking`:
- On the Android main thread — it blocks the UI
- Inside an existing coroutine — it blocks the thread and can cause deadlocks
- In any Android production code where a coroutine scope is available

---

## Testing

See **android-testing** skill for full coroutine test patterns including `runTest`, Turbine, `UnconfinedTestDispatcher`, and `Dispatchers.setMain()`.

**Testability rule:** Inject `CoroutineDispatcher` in any class that dispatches to a non-Main dispatcher **and** is unit-tested. This lets tests replace `Dispatchers.IO` / `Dispatchers.Default` with a test dispatcher:

```kotlin
class NoteRepository(
    private val api: NoteApi,
    private val dao: NoteDao,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO
) {
    suspend fun refreshNotes() = withContext(ioDispatcher) {
        val notes = api.fetchNotes()
        dao.upsertAll(notes)
    }
}
```

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Catching `Exception` without `ensureActive()` | Add `coroutineContext.ensureActive()` as first catch line |
| Sequential independent suspend calls | `async` + `awaitAll` or parallel `launch` |
| `Thread.sleep()` in coroutine | `delay()` |
| `withContext(NonCancellable)` for business logic | Use application scope or DB transaction |
| `runBlocking` on main thread | `viewModelScope.launch` or proper scope |
| `GlobalScope.launch` | Inject application scope via DI |

---

## Checklist: Writing Coroutine Code

- [ ] `ensureActive()` is the first line in every `catch(e: Exception)` / `catch(e: Throwable)` in suspend context with sequential suspend calls
- [ ] No blocking calls without `withContext(Dispatchers.IO)` or `withContext(Dispatchers.Default)`
- [ ] Independent suspend calls run in parallel (`async` / `launch`), never sequential
- [ ] `NonCancellable` used only for cleanup — not business logic
- [ ] Multi-step DB operations use transactions, not application scope
- [ ] No `runBlocking` on main thread or inside coroutines
- [ ] `delay()` used instead of `Thread.sleep()` in all coroutine contexts
- [ ] Synchronization uses the correct tool (Mutex for suspend-only, `limitedParallelism(1)` for thread confinement)
- [ ] Custom scopes use `SupervisorJob()` + appropriate dispatcher
- [ ] No `GlobalScope` — use injected application scope
- [ ] Loops call `ensureActive()` for cooperative cancellation
- [ ] Blocking-to-suspend conversions use `yield()` for cooperative cancellation
