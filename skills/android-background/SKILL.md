---
name: android-background
description: |
  Background work patterns for Android/KMP - WorkManager (one-time, periodic, expedited, foreground promotion), foreground services, work observation, Koin WorkerFactory, and the SyncScheduler abstraction. Use this skill whenever implementing background sync, scheduling periodic work, creating a foreground service, observing work progress, setting up WorkManager with Koin, or deciding between WorkManager and foreground services. Trigger on phrases like "WorkManager", "background work", "sync worker", "periodic sync", "foreground service", "schedule sync", "SyncScheduler", "CoroutineWorker", "work observation", "expedited work", or "background sync".
---

# Android / KMP Background Work

## Choosing the Right Approach

Only consult this decision tree when the choice is not already obvious from context.

| Question | Yes | No |
|---|---|---|
| Must survive process death? | Continue below | Use `viewModelScope` — not this skill |
| Needs to run immediately and continuously? | **Foreground Service** | **WorkManager** |
| Deferrable / can wait for constraints? | **WorkManager** (one-time or periodic) | **Foreground Service** |

**WorkManager** — deferrable persistent work: syncing data, uploading logs, periodic cleanup. Survives process death, respects battery/network constraints.

**Foreground Service** — long-running user-visible work: music playback, navigation, active location tracking. Requires ongoing notification.

---

## WorkManager Architecture

Three components with clear separation of responsibilities:

- **Worker** (`CoroutineWorker`) — thin (~15 lines). Calls the **repository** to do the actual work, maps the result to `WorkerResult`. No business logic here.
- **SyncScheduler** (domain interface + data implementation) — scheduling only. Enqueues/cancels WorkManager requests. Knows nothing about sync logic.
- **Repository** — owns the actual sync/business logic (fetch remote, write to Room, etc.) per **android-data-layer** patterns.

### Module placement

| Component | Module |
|---|---|
| Worker | `feature:data` |
| SyncScheduler interface | `feature:domain` |
| SyncScheduler implementation | `feature:data` |
| Repository (sync logic) | `feature:data` (interface in `feature:domain`) |

---

## WorkerResult Typealias

Avoid confusion between your domain `Result<D, E>` and WorkManager's `ListenableWorker.Result`:

```kotlin
// core:data
typealias WorkerResult = androidx.work.ListenableWorker.Result
```

Always use `WorkerResult` inside Workers. Never import `ListenableWorker.Result` directly.

---

## Worker Pattern

Workers are thin — delegate to the repository, map the result:

```kotlin
class NoteSyncWorker(
    context: Context,
    workerParams: WorkerParameters,
    private val noteRepository: NoteRepository,
) : CoroutineWorker(context, workerParams) {

    override suspend fun doWork(): WorkerResult {
        if (runAttemptCount >= 3) {
            return WorkerResult.failure()
        }
        noteRepository.syncNotes()
            .onError { error ->
                if (error == DataError.Network.UNAUTHORIZED) {
                    return WorkerResult.failure()
                }
                return WorkerResult.retry()
            }
            .onSuccess {
                return WorkerResult.success()
            }
        return WorkerResult.failure()
    }
}
```

Key rules:
- Guard with `runAttemptCount` — fail after a reasonable number of retries.
- Map domain errors to `WorkerResult` per-Worker. Each Worker decides its own retry/failure strategy.
- Non-retryable errors (e.g., UNAUTHORIZED) return `failure()` immediately.

---

## SyncScheduler Pattern

Domain interface — scheduling only, no sync logic:

```kotlin
interface NoteSyncScheduler {
    fun scheduleSync()
    fun cancelSync()
}
```

Data implementation — handles all WorkManager details:

```kotlin
class WorkManagerNoteSyncScheduler(
    private val context: Context,
) : NoteSyncScheduler {

    override fun scheduleSync() {
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            "sync_notes",
            ExistingPeriodicWorkPolicy.REPLACE,
            PeriodicWorkRequestBuilder<NoteSyncWorker>(30L, TimeUnit.MINUTES)
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1000L, TimeUnit.MILLISECONDS)
                .setInitialDelay(30L, TimeUnit.MINUTES)
                .build()
        )
    }

    override fun cancelSync() {
        WorkManager.getInstance(context).cancelUniqueWork("sync_notes")
    }
}
```

---

## One-Time Work

For work that should run once (e.g., upload a file after creation):

```kotlin
fun enqueueUpload(noteId: String) {
    val request = OneTimeWorkRequestBuilder<NoteUploadWorker>()
        .setConstraints(
            Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
        )
        .setInputData(workDataOf("NOTE_ID" to noteId))
        .build()

    WorkManager.getInstance(context)
        .enqueueUniqueWork("upload_$noteId", ExistingWorkPolicy.KEEP, request)
}
```

Use `ExistingWorkPolicy.KEEP` to avoid re-enqueueing if work is already pending.

---

## Work Chaining

Chain sequential or parallel work:

```kotlin
WorkManager.getInstance(context)
    .beginWith(listOf(fetchNotesRequest, fetchTagsRequest))  // parallel
    .then(mergeAndCacheRequest)                               // sequential after both
    .enqueue()
```

---

## Expedited Work and Foreground Promotion

For work that needs to start immediately (e.g., user-initiated upload):

```kotlin
val request = OneTimeWorkRequestBuilder<NoteUploadWorker>()
    .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
    .build()
```

For long-running expedited work that needs a notification (API 31+), override `getForegroundInfo()` in the Worker:

```kotlin
class NoteUploadWorker(
    context: Context,
    workerParams: WorkerParameters,
    private val noteRepository: NoteRepository,
) : CoroutineWorker(context, workerParams) {

    override suspend fun getForegroundInfo(): ForegroundInfo {
        return ForegroundInfo(
            NOTIFICATION_ID,
            createUploadNotification(),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        )
    }

    override suspend fun doWork(): WorkerResult {
        setForeground(getForegroundInfo())
        // ... do work
    }
}
```

---

## Work Observation

Expose work status through the SyncScheduler interface for the presentation layer:

```kotlin
// Domain interface
interface NoteSyncScheduler {
    fun scheduleSync()
    fun cancelSync()
    fun observeSyncStatus(): Flow<SyncStatus>
}

enum class SyncStatus { IDLE, SYNCING, SUCCEEDED, FAILED }
```

```kotlin
// Data implementation
override fun observeSyncStatus(): Flow<SyncStatus> {
    return WorkManager.getInstance(context)
        .getWorkInfosForUniqueWorkFlow("sync_notes")
        .map { workInfos ->
            val info = workInfos.firstOrNull()
            when (info?.state) {
                WorkInfo.State.RUNNING -> SyncStatus.SYNCING
                WorkInfo.State.SUCCEEDED -> SyncStatus.SUCCEEDED
                WorkInfo.State.FAILED -> SyncStatus.FAILED
                WorkInfo.State.ENQUEUED, WorkInfo.State.BLOCKED -> SyncStatus.IDLE
                else -> SyncStatus.IDLE
            }
        }
}
```

Collect in the ViewModel via `collectAsStateWithLifecycle()` per **android-compose-architecture** patterns.

---

## DI with Koin

### Disable default WorkManager initializer

In `AndroidManifest.xml`:

```xml
<provider
    android:name="androidx.startup.InitializationProvider"
    android:authorities="${applicationId}.androidx-startup"
    android:exported="false"
    tools:node="merge">
    <meta-data
        android:name="androidx.work.WorkManagerInitializer"
        android:value="androidx.startup"
        tools:node="remove" />
</provider>
```

### Initialize WorkManager with KoinWorkerFactory

```kotlin
// :app Application class
class App : Application(), KoinComponent {
    override fun onCreate() {
        super.onCreate()
        startKoin {
            androidContext(this@App)
            workManagerFactory()
            modules(
                coreDataModule,
                notesDataModule,
                notesPresentationModule,
                // ...
            )
        }

        WorkManager.initialize(
            this,
            Configuration.Builder()
                .setWorkerFactory(get<WorkerFactory>())
                .build()
        )
    }
}
```

### Koin module for Workers

```kotlin
// feature:notes:data
val notesDataModule = module {
    singleOf(::WorkManagerNoteSyncScheduler) { bind<NoteSyncScheduler>() }
    worker { NoteSyncWorker(get(), get(), get()) }
}
```

Use `worker { }` (not `singleOf` or `factoryOf`) for Worker definitions — Koin's worker scope matches WorkManager's lifecycle.

---

## Foreground Services

Use a standalone foreground service when work must run immediately, continuously, and with user visibility — not suitable for WorkManager (e.g., music playback, active navigation, ongoing location tracking).

### Service lifecycle

```kotlin
class MusicPlaybackService : Service() {

    override fun onCreate() {
        super.onCreate()
        // Initialize resources (media player, location client, etc.)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = createNotification()
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            notification,
            ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
        )
        // Start work
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        // Release resources
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        private const val NOTIFICATION_ID = 1
    }
}
```

### Manifest declaration

```xml
<service
    android:name=".MusicPlaybackService"
    android:foregroundServiceType="mediaPlayback"
    android:exported="false" />
```

### Foreground service types (Android 14+)

Every foreground service must declare a type. Each type has specific permission requirements:

| Type | Use case | Key permissions |
|---|---|---|
| `camera` | Camera access while in background | `FOREGROUND_SERVICE_CAMERA`, `CAMERA` |
| `connectedDevice` | Bluetooth, USB, companion devices | `FOREGROUND_SERVICE_CONNECTED_DEVICE` |
| `dataSync` | Data transfer (sync, upload, download) | `FOREGROUND_SERVICE_DATA_SYNC` |
| `health` | Fitness/health tracking | `FOREGROUND_SERVICE_HEALTH` |
| `location` | Continuous location access | `FOREGROUND_SERVICE_LOCATION`, `ACCESS_FINE/COARSE_LOCATION` |
| `mediaPlayback` | Audio/video playback | `FOREGROUND_SERVICE_MEDIA_PLAYBACK` |
| `mediaProjection` | Screen capture/sharing | `FOREGROUND_SERVICE_MEDIA_PROJECTION` |
| `microphone` | Recording audio | `FOREGROUND_SERVICE_MICROPHONE`, `RECORD_AUDIO` |
| `phoneCall` | Ongoing call | `FOREGROUND_SERVICE_PHONE_CALL`, `MANAGE_OWN_CALLS` |
| `remoteMessaging` | Messaging for companion/wearable devices | `FOREGROUND_SERVICE_REMOTE_MESSAGING` |
| `shortService` | Quick tasks that finish fast | None extra (limited to ~3 minutes) |
| `specialUse` | Doesn't fit other categories | `FOREGROUND_SERVICE_SPECIAL_USE` + Play Store justification |

**Android 15+ restrictions**: `dataSync` foreground services have a 6-hour time limit. Prefer WorkManager with foreground promotion for data sync instead of standalone foreground services.

### When to use foreground service vs. WorkManager foreground promotion

| Scenario | Approach |
|---|---|
| Continuous user-facing work (music, navigation) | Standalone foreground service |
| User-initiated data transfer (upload/download) | WorkManager + `setExpedited()` + `setForeground()` |
| Background periodic sync | WorkManager with constraints |
| Quick one-off background task | WorkManager one-time |

---

## Testing

Workers are thin — test the **repository** logic directly using fakes per **android-testing** patterns. No need for `TestListenableWorkerBuilder`.

For ViewModels that trigger sync, use a fake `SyncScheduler`:

```kotlin
class FakeNoteSyncScheduler : NoteSyncScheduler {
    var scheduleSyncCalled = false
        private set
    var cancelSyncCalled = false
        private set

    override fun scheduleSync() { scheduleSyncCalled = true }
    override fun cancelSync() { cancelSyncCalled = true }
    override fun observeSyncStatus(): Flow<SyncStatus> = flowOf(SyncStatus.IDLE)
}
```

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Worker | `<Feature>SyncWorker` | `NoteSyncWorker` |
| SyncScheduler interface | `<Feature>SyncScheduler` | `NoteSyncScheduler` |
| SyncScheduler impl | `WorkManager<Feature>SyncScheduler` | `WorkManagerNoteSyncScheduler` |
| Koin module | `<feature>DataModule` (Workers go here) | `notesDataModule` |
| Unique work name | `snake_case` string | `"sync_notes"` |
| WorkerResult typealias | `WorkerResult` in `core:data` | `typealias WorkerResult = ListenableWorker.Result` |
| Sync status enum | `SyncStatus` | `SyncStatus.SYNCING` |

---

## Checklist: Adding Background Work for a Feature

- [ ] Define `WorkerResult` typealias in `core:data` (if not yet present)
- [ ] Define `<Feature>SyncScheduler` interface in `feature:domain`
- [ ] Define sync method in repository interface in `feature:domain` (e.g., `suspend fun syncNotes()`)
- [ ] Implement sync logic in repository in `feature:data` — see **android-data-layer**
- [ ] Implement `CoroutineWorker` in `feature:data` — thin, calls repository, maps to `WorkerResult`
- [ ] Implement `WorkManager<Feature>SyncScheduler` in `feature:data`
- [ ] Register Worker and SyncScheduler in feature's Koin data module
- [ ] Disable default WorkManager initializer in AndroidManifest
- [ ] Initialize WorkManager with `KoinWorkerFactory` in `:app`
- [ ] Add work observation if UI needs sync status
