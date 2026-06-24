---
name: kotlin-flows
description: |
  Kotlin Flows for Android/KMP — Flow types (StateFlow, SharedFlow, callbackFlow, Channel), stateIn/shareIn, operators, flowOn, backpressure, lifecycle-aware collection, and offline-first patterns. Use this skill whenever writing or reviewing Flows, reactive chains, flow operators, or converting callbacks to flows. Trigger on phrases like "Flow", "StateFlow", "SharedFlow", "MutableStateFlow", "MutableSharedFlow", "Channel", "callbackFlow", "stateIn", "shareIn", "flowOn", "collectLatest", "flatMapLatest", "flatMapConcat", "combine", "zip", "merge", "debounce", "distinctUntilChanged", "conflate", "buffer", "backpressure", "receiveAsFlow", "awaitClose", "reactive", "offline-first flow", "onStart", "onCompletion", "collectAsStateWithLifecycle", or "repeatOnLifecycle".
---

# Kotlin Flows (Android / KMP)

> For cancellation safety, parallel execution, synchronization, scopes, and blocking code patterns, see **kotlin-coroutines**.

## Flow Type Selection

| Need | Flow Type |
|---|---|
| Value held at all times (UI state) | `MutableStateFlow` / `StateFlow` |
| Multi-subscriber events (Bluetooth, WebSocket) | `MutableSharedFlow` / `SharedFlow` |
| Convert system callback (sensor, location, BLE) | `callbackFlow` — must include `awaitClose` |
| Single-subscriber one-time events (navigation, snackbar) | `Channel` + `receiveAsFlow()` |
| Reactive stream from library (Room, DataStore) | Return the library's built-in `Flow` directly |
| Truly reactive custom stream | `flow { }` builder — ONLY if no better option |

### StateFlow for held state

```kotlin
private val _state = MutableStateFlow(ProfileState())
val state = _state.asStateFlow()

// Always update with .update { } — never replace the flow
_state.update { it.copy(isLoading = true) }
```

### SharedFlow for multi-subscriber events

```kotlin
private val _bluetoothMessages = MutableSharedFlow<BluetoothMessage>(
    replay = 0,
    extraBufferCapacity = 64,
    onBufferOverflow = BufferOverflow.DROP_OLDEST
)
val bluetoothMessages = _bluetoothMessages.asSharedFlow()
```

- `replay = 0` — new subscribers don't get old events
- `extraBufferCapacity` — buffer emissions when collectors are slow
- `onBufferOverflow` — what to do when buffer is full

### callbackFlow for callback conversion

```kotlin
fun observeLocationUpdates(
    locationClient: FusedLocationProviderClient,
    request: LocationRequest
): Flow<Location> = callbackFlow {
    val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let { trySend(it) }
        }
    }
    locationClient.requestLocationUpdates(request, callback, Looper.getMainLooper())

    awaitClose {                              // ← MANDATORY
        locationClient.removeLocationUpdates(callback)
    }
}
```

**`awaitClose` is mandatory in every `callbackFlow`.** Without it, the flow completes immediately.

### Channel for single-subscriber events

```kotlin
private val _events = Channel<ProfileEvent>()
val events = _events.receiveAsFlow()
```

### Anti-pattern: one-shot fetch in a flow builder

```kotlin
// WRONG — this is just a suspend function pretending to be a flow
fun getNotes(): Flow<List<Note>> = flow {
    val notes = repository.fetchNotes()
    emit(notes)
}

// CORRECT — just make it a suspend function
suspend fun getNotes(): List<Note> = repository.fetchNotes()
```

### Offline-first pattern

Return Room's reactive `Flow` as the single source of truth. Trigger updates via `insert()` elsewhere — never wrap fetch-and-insert in a `flow { }` builder:

```kotlin
// Repository
fun observeNotes(): Flow<List<Note>> = noteDao.observeAll()  // Room's reactive Flow

suspend fun refreshNotes() {
    val remote = api.fetchNotes()
    noteDao.upsertAll(remote.map { it.toEntity() })
    // Room's Flow automatically emits the new data
}
```

---

## stateIn and shareIn

### ViewModel layer — always WhileSubscribed

```kotlin
val state: StateFlow<ProfileState> = combine(
    userRepository.observeUser(userId),
    settingsRepository.observeSettings()
) { user, settings ->
    ProfileState(user = user.toUi(), settings = settings.toUi())
}
    .stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000L),
        initialValue = ProfileState()
    )
```

`WhileSubscribed(5_000L)` stops the upstream flow 5 seconds after the last subscriber disappears. This survives configuration changes (screen rotation) without restarting the flow, but cleans up when the screen is truly gone.

### Outside ViewModel — prefer Lazily

```kotlin
class BluetoothRepository(
    private val applicationScope: CoroutineScope,
    private val bluetoothAdapter: BluetoothAdapter
) {
    val connectionState: StateFlow<ConnectionState> = observeConnectionState()
        .stateIn(
            scope = applicationScope,
            started = SharingStarted.Lazily,      // starts on first collector, stays hot
            initialValue = ConnectionState.Disconnected
        )
}
```

Use `Lazily` outside ViewModels — starts on first collection, stays hot for the scope's lifetime. Only use `Eagerly` if the flow **must** start immediately regardless of collectors (rare).

### Single subscriber? Don't use shareIn

If you know there will be only one subscriber, use `Channel` + `receiveAsFlow()` instead of `shareIn`:

```kotlin
// WRONG — shareIn with a single subscriber wastes resources
val events = eventFlow.shareIn(scope, SharingStarted.Lazily)

// CORRECT — Channel for single subscriber
private val _events = Channel<Event>()
val events = _events.receiveAsFlow()
```

### SharedFlow configuration

```kotlin
val messages: SharedFlow<Message> = messageFlow.shareIn(
    scope = applicationScope,
    started = SharingStarted.Lazily,
    replay = 1                                   // new subscribers get the last emission
)
```

- `replay = 0` — no replay, only future emissions (default)
- `replay = 1` — new subscribers immediately get the most recent value
- Think carefully about whether `replay > 0` makes sense for your use case

---

## Flow Operators

| Need | Operator |
|---|---|
| Combine latest values from N flows | `combine` |
| Pair emissions 1:1 from two flows | `zip` |
| Merge all emissions into one stream | `merge` |
| Switch to new flow on each emission (search) | `flatMapLatest` |
| Process each emission's flow sequentially | `flatMapConcat` |
| Debounce rapid emissions (typing) | `debounce` |
| Skip duplicate consecutive emissions | `distinctUntilChanged` |

### Search pipeline example

```kotlin
val searchResults: StateFlow<List<Result>> = searchQuery
    .debounce(300L)                               // wait for typing to pause
    .distinctUntilChanged()                        // skip if query didn't change
    .flatMapLatest { query ->                      // cancel previous search on new query
        if (query.isBlank()) flowOf(emptyList())
        else searchRepository.search(query)
    }
    .stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000L),
        initialValue = emptyList()
    )
```

### combine — merge latest from multiple flows

```kotlin
val dashboardState: StateFlow<DashboardState> = combine(
    userRepository.observeUser(),
    notificationRepository.observeUnreadCount(),
    settingsRepository.observeTheme()
) { user, unreadCount, theme ->
    DashboardState(user = user, unreadCount = unreadCount, theme = theme)
}
    .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000L), DashboardState())
```

### onStart / onCompletion — for side effects

```kotlin
repository.observeNotes()
    .onStart { _state.update { it.copy(isLoading = true) } }
    .onCompletion { _state.update { it.copy(isLoading = false) } }
    .collect { notes -> _state.update { it.copy(notes = notes) } }
```

---

## flowOn Placement

**`flowOn` affects UPSTREAM operators only.** Place it immediately after the operators that need the dispatcher change.

```kotlin
// CORRECT — map runs on IO, collect runs on the caller's dispatcher
flow { emit(readFromDisk()) }
    .map { parse(it) }
    .flowOn(Dispatchers.IO)       // ← affects flow{} and map{} above
    .collect { updateUi(it) }     // runs on caller's dispatcher (Main)

// WRONG — flowOn at the end does NOT affect collect
flow { emit(readFromDisk()) }
    .collect { updateUi(it) }
    .flowOn(Dispatchers.IO)       // ← does nothing useful here
```

---

## Backpressure

| Strategy | Use Case | Behavior |
|---|---|---|
| `collectLatest` | Search / UI updates | Cancels previous collection when new value arrives |
| `conflate` | Sensor data, frequent updates | Drops intermediate values, keeps latest |
| `buffer()` | Producer-consumer pipelines | Decouples emission and collection speeds |

```kotlin
// Search — cancel stale processing
searchResults.collectLatest { results ->
    // If a new emission arrives while this is running, this block is cancelled
    renderResults(results)
}

// Sensor — only care about latest reading
sensorFlow
    .conflate()
    .collect { reading -> updateDisplay(reading) }

// Producer-consumer — don't slow down the producer
dataStream
    .buffer(capacity = 64)
    .collect { item -> slowProcess(item) }
```

---

## Lifecycle-Aware Collection

### Activity / Fragment — repeatOnLifecycle

```kotlin
lifecycleScope.launch {
    repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.state.collect { state ->
            // Only collects when lifecycle is at least STARTED.
            // Automatically cancels collection in onStop, restarts in onStart.
            updateUi(state)
        }
    }
}
```

### Compose — collectAsStateWithLifecycle

```kotlin
@Composable
fun ProfileScreen(viewModel: ProfileViewModel = koinViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    // Automatically lifecycle-aware — stops collecting when the composable leaves composition
    ProfileContent(state = state)
}
```

---

## Testing

See **android-testing** skill for full Flow test patterns including Turbine (`.test { awaitItem() }`), `runTest`, and `UnconfinedTestDispatcher`.

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| `flow { emit(oneShot()) }` | Just use a `suspend fun` |
| Missing `awaitClose` in `callbackFlow` | Always add `awaitClose { cleanup() }` |
| `flowOn` at end of chain | Move upstream of the operators it should affect |
| `shareIn` with single subscriber | `Channel` + `receiveAsFlow()` |
| `stateIn(SharingStarted.Eagerly)` in ViewModel | `WhileSubscribed(5_000L)` |
| Collecting flow on wrong lifecycle | Use `repeatOnLifecycle` or `collectAsStateWithLifecycle` |

---

## Checklist: Writing Flow Code

- [ ] Flow type matches use case (StateFlow for state, Channel for single-sub events, callbackFlow for callbacks)
- [ ] `awaitClose` present in every `callbackFlow`
- [ ] `stateIn` uses `WhileSubscribed(5_000L)` in ViewModels
- [ ] `stateIn` / `shareIn` outside ViewModel uses `Lazily` unless there's a strong reason for `Eagerly`
- [ ] `flowOn` placed upstream of the operators it should affect
- [ ] Single-subscriber flows use `Channel` + `receiveAsFlow()`, not `shareIn`
- [ ] No one-shot `flow { emit(singleCall()) }` — use a `suspend fun` instead
- [ ] Backpressure strategy chosen when producer is faster than consumer
- [ ] Lifecycle-aware collection used in UI (`repeatOnLifecycle` or `collectAsStateWithLifecycle`)
- [ ] SharedFlow `replay` and `extraBufferCapacity` configured intentionally
