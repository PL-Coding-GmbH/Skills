---
name: kmp-data-layer
description: |
  Data layer patterns for Kotlin Multiplatform (Android + iOS) - data sources, repositories, DTOs, mappers, Room entities, Ktor HttpClient, safe call helpers, token storage, and offline-first. Use this skill whenever writing or reviewing a data source or repository, creating DTOs or Room entities, writing mappers, setting up the Ktor HttpClient, handling network errors, or implementing token refresh. Trigger on phrases like "create a repository", "create a data source", "add a DAO", "Ktor client", "write a mapper", "DTO", "Room entity", "network call", "token storage", or "offline-first".
---

# KMP Data Layer

All data layer code lives in `commonMain` unless it needs a platform API. The only platform-specific pieces are the Ktor engine, the Room database builder, and the DataStore file path — each is a few lines in `androidMain` / `iosMain`.

## Error Handling

This skill uses `Result<T, E>`, `DataError`, and the extension helpers defined in the **kmp-error-handling** skill. Refer to that skill for the full `Result` wrapper, `DataError` sealed interface, and `map`/`onSuccess`/`onFailure`/`asEmptyResult` extensions.

---

## Data Source vs Repository

- **Data source** — accesses a single data source (local DB, remote API, file system). Most classes in the data layer are data sources.
- **Repository** — combines multiple data sources (e.g., a remote API + a local DB for offline-first). Only use the term "repository" when the class genuinely coordinates multiple sources.

```kotlin
// Single source → data source
interface NoteLocalDataSource {
    suspend fun getNotes(): Result<List<Note>, DataError.Local>
    suspend fun insertNote(note: Note): EmptyResult<DataError.Local>
}

interface NoteRemoteDataSource {
    suspend fun fetchNotes(): Result<List<Note>, DataError.Network>
}

// Multiple sources → repository
interface NoteRepository {
    suspend fun getNotes(): Result<List<Note>, DataError>
    suspend fun sync(): EmptyResult<DataError>
}
```

## Domain Layer Contracts

- Pure Kotlin in `commonMain` — no Android/framework imports and no `java.*` imports (use `kotlin.time` / `kotlinx-datetime` instead of `java.time`, `kotlin.uuid.Uuid` instead of `java.util.UUID`).
- Contains: domain models, data source/repository **interfaces**, error types.
- **Every data source or repository used by a ViewModel must have an interface in `domain`** — enforces that `presentation` never depends on `data`, and enables testing.

---

## DTOs and Domain Models

- Always separate: DTOs (data layer) ↔ Domain Models (domain layer).
- Domain models never go directly into Room entities or Ktor request/response bodies.
- Mappers are simple extension functions living in the data layer alongside the DTO:

```kotlin
fun NoteDto.toNote(): Note = Note(id = id, title = title, ...)
fun Note.toNoteDto(): NoteDto = NoteDto(id = id, title = title, ...)
fun NoteEntity.toNote(): Note = ...
fun Note.toNoteEntity(): NoteEntity = ...
```

---

## Implementations

Name implementations for what makes them unique — never suffix with `Impl`.

### Data source (single source)

```kotlin
class RoomNoteDataSource(private val dao: NoteDao) : NoteLocalDataSource {
    override suspend fun getNotes(): Result<List<Note>, DataError.Local> {
        return try {
            Result.Success(dao.getAllNotes().map { it.toNote() })
        } catch (e: Exception) {
            Result.Error(DataError.Local.UNKNOWN)
        }
    }
}
```

### Repository (multiple sources)

```kotlin
class OfflineFirstNoteRepository(
    private val localDataSource: NoteLocalDataSource,
    private val remoteDataSource: NoteRemoteDataSource
) : NoteRepository {
    override suspend fun getNotes(): Result<List<Note>, DataError> {
        return remoteDataSource.fetchNotes()
            .onSuccess { notes -> localDataSource.insertAll(notes) }
            .onFailure { localDataSource.getNotes() }
    }
}
```

Use names like `RoomNoteDataSource`, `KtorNoteDataSource`, `OfflineFirstNoteRepository`. The name should tell you what the class wraps or how it behaves.

---

## Ktor — HttpClient Factory (`core:data`)

Configure the client once. Accept the engine externally so tests can swap in a mock engine:

```kotlin
object HttpClientFactory {
    fun create(engine: HttpClientEngine): HttpClient = HttpClient(engine) {
        install(ContentNegotiation) { json() }
        install(Auth) {
            bearer {
                loadTokens { /* load from DataStore */ }
                refreshTokens { /* call refresh endpoint, save new tokens */ }
            }
        }
        install(Logging) { logger = Logger.DEFAULT; level = LogLevel.ALL }
        defaultRequest { contentType(ContentType.Application.Json) }
    }
}
```

Inject `HttpClient` via Koin. The engine is the only platform-specific part — it is provided by the platform Koin module (see **kmp-di-koin**):

| Source set | Artifacts | Engine |
|---|---|---|
| `commonMain` | `io.ktor:ktor-client-core`, `ktor-client-content-negotiation`, `ktor-serialization-kotlinx-json`, `ktor-client-auth`, `ktor-client-logging` | — |
| `androidMain` | `io.ktor:ktor-client-okhttp` | `OkHttp.create()` |
| `iosMain` | `io.ktor:ktor-client-darwin` | `Darwin.create()` |

```kotlin
// androidMain
actual val coreDataPlatformModule = module {
    single<HttpClientEngine> { OkHttp.create() }
}

// iosMain
actual val coreDataPlatformModule = module {
    single<HttpClientEngine> { Darwin.create() }
}
```

---

## Ktor — Safe Call Helpers (`core:data`)

Use `safeCall` / `responseToResult` helpers and typed extension functions (`HttpClient.get`, `HttpClient.post`, `HttpClient.delete`) to keep data source call sites clean and uniform. See the **kmp-error-handling** skill for the full implementation of these helpers.

```kotlin
suspend fun getNotes(): Result<List<NoteDto>, DataError.Network> {
    return httpClient.get(route = "/notes")
}
```

---

## Token Storage

Store tokens in DataStore (in `core:data` or a dedicated `:core:auth` / `:feature:auth:data` module). The Ktor `Auth` plugin reads/writes tokens and handles 401 refresh automatically.

DataStore is multiplatform: `androidx.datastore:datastore-preferences-core` goes into `commonMain`. Only the file path differs per platform:

```kotlin
// commonMain
internal const val DATA_STORE_FILE_NAME = "prefs.preferences_pb"

fun createDataStore(producePath: () -> String): DataStore<Preferences> =
    PreferenceDataStoreFactory.createWithPath(
        produceFile = { producePath().toPath() }   // okio.Path.Companion.toPath
    )

// androidMain
fun createDataStore(context: Context): DataStore<Preferences> = createDataStore {
    context.filesDir.resolve(DATA_STORE_FILE_NAME).absolutePath
}

// iosMain
@OptIn(ExperimentalForeignApi::class)
fun createDataStore(): DataStore<Preferences> = createDataStore {
    val directory = NSFileManager.defaultManager.URLForDirectory(
        directory = NSDocumentDirectory,
        inDomain = NSUserDomainMask,
        appropriateForURL = null,
        create = false,
        error = null
    )
    requireNotNull(directory).path + "/$DATA_STORE_FILE_NAME"
}
```

Create exactly one `DataStore` instance per file (Koin `single`).

---

## Room (KMP setup)

Room is multiplatform. Entities, DAOs, and the `@Database` class live in `commonMain` of a database module (`:core:database` or `:feature:<name>:database`) that applies the `room` convention plugin — it adds `room-runtime`, `sqlite-bundled`, the Room Gradle plugin, and the per-target KSP configurations (`kspAndroid`, `kspIosArm64`, `kspIosSimulatorArm64`, `kspIosX64`).

```kotlin
// commonMain
@Database(entities = [NoteEntity::class], version = 1)
@ConstructedBy(AppDatabaseConstructor::class)
abstract class AppDatabase : RoomDatabase() {
    abstract fun noteDao(): NoteDao
}

// Room's KSP processor generates the actual implementations
@Suppress("NO_ACTUAL_FOR_EXPECT")
expect object AppDatabaseConstructor : RoomDatabaseConstructor<AppDatabase> {
    override fun initialize(): AppDatabase
}

fun createDatabase(builder: RoomDatabase.Builder<AppDatabase>): AppDatabase = builder
    .setDriver(BundledSQLiteDriver())
    .setQueryCoroutineContext(Dispatchers.IO)   // import kotlinx.coroutines.IO
    .build()

// androidMain
fun databaseBuilder(context: Context): RoomDatabase.Builder<AppDatabase> {
    val dbFile = context.applicationContext.getDatabasePath("app.db")
    return Room.databaseBuilder<AppDatabase>(context.applicationContext, dbFile.absolutePath)
}

// iosMain
fun databaseBuilder(): RoomDatabase.Builder<AppDatabase> {
    val dbFile = documentDirectory() + "/app.db"   // NSDocumentDirectory, same lookup as DataStore
    return Room.databaseBuilder<AppDatabase>(name = dbFile)
}
```

KMP-specific rules:
- **Every DAO function must be `suspend` or return `Flow`** — blocking DAO functions don't compile for iOS.
- No `LiveData`, `Cursor`, `SupportSQLiteDatabase`, or `SupportSQLiteQuery`. Use the `SQLiteConnection` / `SQLiteDriver` APIs.
- No `allowMainThreadQueries()` — it does not exist for the bundled driver.

---

## Room Migrations

Prefer `@Database(autoMigrations = [AutoMigration(from = 1, to = 2)])`. Use manual `Migration` objects when the schema change is too complex for auto-migration. In KMP, override `migrate(connection: SQLiteConnection)` (not the `SupportSQLiteDatabase` overload) and run statements with `connection.execSQL(...)`.

---

## Offline-First (when applicable)

Follow **Room as single source of truth**: fetch from network → persist to Room → expose DB `Flow` to the ViewModel. The ViewModel never observes network responses directly.

This pattern is optional — apply it when the project requires offline support.

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Data source interface | `<Entity><Local/Remote>DataSource` | `NoteLocalDataSource`, `NoteRemoteDataSource` |
| Data source impl | describe what makes it unique | `RoomNoteDataSource`, `KtorNoteDataSource` |
| Repository interface | `<Entity>Repository` (multi-source only) | `NoteRepository` |
| Repository impl | describe what makes it unique | `OfflineFirstNoteRepository` |
| DTO | `<Model>Dto` | `NoteDto` |
| Room entity | `<Model>Entity` | `NoteEntity` |
| Mapper | extension fun on source type | `fun NoteDto.toNote()` |

---

## Checklist: Adding a New Data Source or Repository

- [ ] Define domain model(s) in `feature:domain`
- [ ] Define data source or repository interface in `feature:domain`
- [ ] Define feature-specific error type(s) in `feature:domain` (implement `Error`) — see **kmp-error-handling** skill
- [ ] Define DTOs and Room entities in `feature:data`
- [ ] Write mappers as extension functions in `feature:data`
- [ ] Implement data source (single source) or repository (multi-source) in `feature:data` (`commonMain`), named for what makes it unique
- [ ] Keep anything that needs a platform API behind an interface or `expect`/`actual`, with implementations in `androidMain` **and** `iosMain`
