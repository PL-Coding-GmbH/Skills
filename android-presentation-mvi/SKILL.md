---
name: android-presentation-mvi
description: |
  MVI presentation layer for Android/KMP - State, Action, Event, ViewModel, Root/Screen composable split, UI models, UiText error mapping, and process death with SavedStateHandle. Use this skill whenever creating or reviewing a ViewModel, defining screen state, actions, or events, structuring composables, mapping errors to UI strings, or handling process death. Trigger on phrases like "add a ViewModel", "create a screen", "MVI", "state", "action", "event", "screen composable", "UiText", "SavedStateHandle", "ObserveAsEvents", or "UI model".
---
 
# Android / KMP Presentation Layer (MVI)
 
## Overview
 
Every screen has:
1. **State** — a single data class holding all UI state fields.
2. **Action** (Intent) — a sealed interface of all user-triggered actions.
3. **ViewModel** — holds `StateFlow<State>` and processes `Action`.
4. **Event** *(optional)* — a sealed interface of one-time side effects the ViewModel needs to push to the UI. Only add this when needed (see [When to add Events](#event-one-time-side-effects-optional)).
 
---
 
## State
 
```kotlin
data class NoteListState(
    val notes: List<NoteUi> = emptyList(),
    val isLoading: Boolean = false,
    val error: UiText? = null
)
```
 
Always update state with `.update { }` — never replace the entire flow:
```kotlin
_state.update { it.copy(isLoading = true) }
```
 
---
 
## Action (Intent)
 
```kotlin
sealed interface NoteListAction {
    data object OnRefreshClick : NoteListAction
    data class OnNoteClick(val noteId: String) : NoteListAction
    data class OnDeleteNote(val noteId: String) : NoteListAction
}
```
 
---
 
## Event (one-time side effects, optional)

**Events exist only when the ViewModel needs to push a one-time side effect to the UI that only the ViewModel knows about.** If no such side effect exists for a screen, do not define an `Event` type, do not create a `Channel`, and do not expose an `events` Flow.

### When to add an Event

Add an event for a case **only the ViewModel can decide**, such as:
- Navigating after a successful async operation (e.g., navigate to home after a successful login call completes).
- Showing a snackbar because of a network error that came back from a repository call.
- Triggering a platform side effect after business logic finishes (e.g., copy to clipboard, share sheet, biometric prompt).

### When NOT to add an Event

Do not add an event for anything the UI can decide on its own from a click or from state:
- Plain navigation triggered directly by a button click that doesn't need a ViewModel result — navigate directly from the composable's `onClick`, without a roundtrip through `onAction` and an event.
- Showing a dialog or bottom sheet whose visibility can live in `State` as a boolean or nullable value.
- Any UI reaction that can be derived from observing `State` changes.

**If none of the above cases apply to the screen, drop the `Event` sealed interface, the `Channel`, and the `events` Flow entirely.** The `ObserveAsEvents` block in the Root composable is also removed.

### Example (when events ARE needed)

```kotlin
sealed interface LoginEvent {
    data object LoginSucceeded : LoginEvent
    data class ShowSnackbar(val message: UiText) : LoginEvent
}
```

Here `LoginSucceeded` can only be known after the async login call resolves, and the network error can only be turned into a snackbar message inside the ViewModel — both are legitimate events.

---

## ViewModel

### With events (only when actually needed)

```kotlin
class LoginViewModel(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _state = MutableStateFlow(LoginState())
    val state = _state.asStateFlow()

    private val _events = Channel<LoginEvent>()
    val events = _events.receiveAsFlow()

    fun onAction(action: LoginAction) {
        when (action) {
            is LoginAction.OnLoginClick -> login()
            /* ... */
        }
    }

    private fun login() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true) }
            authRepository.login(state.value.email, state.value.password)
                .onSuccess {
                    _state.update { it.copy(isLoading = false) }
                    _events.send(LoginEvent.LoginSucceeded)
                }
                .onFailure { error ->
                    _state.update { it.copy(isLoading = false) }
                    _events.send(LoginEvent.ShowSnackbar(error.toUiText()))
                }
        }
    }
}
```

### Without events (default when nothing needs to be pushed)

```kotlin
class NoteListViewModel(
    private val noteRepository: NoteRepository
) : ViewModel() {

    private val _state = MutableStateFlow(NoteListState())
    val state = _state.asStateFlow()

    fun onAction(action: NoteListAction) {
        when (action) {
            is NoteListAction.OnRefreshClick -> loadNotes()
            /* OnNoteClick is NOT handled here — the composable navigates directly on click */
        }
    }

    private fun loadNotes() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true) }
            noteRepository.getNotes()
                .onSuccess { notes ->
                    _state.update { it.copy(notes = notes.map { it.toNoteUi() }, isLoading = false) }
                }
                .onFailure { error ->
                    _state.update { it.copy(isLoading = false, error = error.toUiText()) }
                }
        }
    }
}
```

Note how the error surfaces via `State.error` instead of an event — observing state is enough because the UI just needs to render it.
 
---
 
## Coroutine Dispatchers
 
**Do not inject** unless the class is unit-tested and dispatches to a non-main dispatcher. For ViewModel tests, use `Dispatchers.setMain(UnconfinedTestDispatcher())` in test setup.
 
For blocking code that doesn't support suspension, wrap it:
```kotlin
suspend fun compressImage(bytes: ByteArray): ByteArray = withContext(Dispatchers.IO) {
    // blocking compression logic
}
```
 
Only inject `CoroutineDispatcher` when:
1. The class dispatches to a non-main dispatcher (e.g., `IO`), AND
2. That class is directly unit-tested.
 
---
 
## Mapping Errors to UI Strings

`UiText` (`core:presentation`) wraps strings that originate from — or could originate from — a string resource:

```kotlin
sealed interface UiText {
    data class DynamicString(val value: String) : UiText
    class StringResource(val id: Int, val args: Array<Any> = emptyArray()) : UiText
}
```

**When to use `UiText`:** For any string that comes from a string resource, could be localized, or might be either a resource or a dynamic value depending on context (e.g., error messages that map to `R.string.*`).

**When to use plain `String`:** For values that are always dynamic and never come from resources — e.g., a user's name, a formatted date, a currency amount. These should be exposed as `String` directly in the state or UI model.

```kotlin
// UiText — error message that maps to a string resource
data class NoteListState(
    val error: UiText? = null
)

// Plain String — always dynamic, never a resource
data class NoteUi(
    val authorName: String,
    val formattedDate: String
)
```

Define `DataError.toUiText()` extension functions in `core:presentation` (or feature `presentation`) that map error enums to `UiText.StringResource`.
 
---
 
## UI Model (Presentation Model)
 
When a domain model needs UI-specific formatting (dates, units, currency), create a dedicated UI model in the presentation layer:
 
```kotlin
data class NoteUi(
    val id: String,
    val title: String,
    val formattedDate: String  // e.g. "Mar 15, 2026"
)
 
fun Note.toNoteUi(): NoteUi = NoteUi(
    id = id,
    title = title,
    formattedDate = date.format(...)
)
```
 
UI models are always suffixed with `Ui` (e.g., `NoteUi`, `TodoItemUi`).
 
---
 
## Composable Structure

Both the Root and Screen composable live in the **same file** (e.g., `NoteListScreen.kt`).

### Root Composable (suffixed `Root`)

Receives the ViewModel (via `koinViewModel()`) and any callbacks needed for navigation. Observes events **only when the ViewModel exposes an `events` Flow**. Passes state and `onAction` down.

For plain navigation that a button click triggers directly, invoke the navigation callback from the Screen composable's `onClick` — do **not** route it through `onAction` and an event.

### Screen Composable (suffixed `Screen`)

Receives `state`, `onAction`, and any direct navigation callbacks that don't need a ViewModel roundtrip. No ViewModel reference. Can be previewed independently.

### Example — no events (navigation happens directly on click)

```kotlin
// NoteListScreen.kt — Root + Screen in a single file

@Composable
fun NoteListRoot(
    onNavigateToDetail: (String) -> Unit,
    viewModel: NoteListViewModel = koinViewModel()
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    NoteListScreen(
        state = state,
        onAction = viewModel::onAction,
        onNoteClick = onNavigateToDetail
    )
}

@Composable
fun NoteListScreen(
    state: NoteListState,
    onAction: (NoteListAction) -> Unit,
    onNoteClick: (String) -> Unit
) { /* onNoteClick fires directly from the list item's onClick */ }

@Preview
@Composable
private fun NoteListScreenPreview() {
    NoteListScreen(state = NoteListState(), onAction = {}, onNoteClick = {})
}
```

### Example — with events (one-time side effect only the ViewModel knows)

```kotlin
// LoginScreen.kt

@Composable
fun LoginRoot(
    onLoginSuccess: () -> Unit,
    viewModel: LoginViewModel = koinViewModel()
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    ObserveAsEvents(viewModel.events) { event ->
        when (event) {
            LoginEvent.LoginSucceeded -> onLoginSuccess()
            is LoginEvent.ShowSnackbar -> { /* show snackbar */ }
        }
    }

    LoginScreen(
        state = state,
        onAction = viewModel::onAction
    )
}
```
 
---
 
## Process Death
 
When a screen involves complex forms or critical user input, restore essential fields using `SavedStateHandle`:
 
```kotlin
class NoteEditorViewModel(
    private val savedStateHandle: SavedStateHandle,
    private val noteRepository: NoteRepository
) : ViewModel() {
    private val _state = MutableStateFlow(
        NoteEditorState(
            title = savedStateHandle["title"] ?: "",
            body = savedStateHandle["body"] ?: ""
        )
    )
 
    fun onAction(action: NoteEditorAction) {
        when (action) {
            is NoteEditorAction.OnTitleChange -> {
                savedStateHandle["title"] = action.title
                _state.update { it.copy(title = action.title) }
            }
        }
    }
}
```
 
Only save what truly matters after process death — not the entire state.
 
---
 
## Naming Conventions
 
| Thing | Convention | Example |
|---|---|---|
| ViewModel | `<Screen>ViewModel` | `NoteListViewModel` |
| State | `<Screen>State` | `NoteListState` |
| Action | `<Screen>Action` | `NoteListAction` |
| Event *(optional)* | `<Screen>Event` | `LoginEvent` |
| Root composable | `<Screen>Root` | `NoteListRoot` |
| Screen composable | `<Screen>Screen` | `NoteListScreen` |
| UI model | `<Model>Ui` | `NoteUi`, `TodoItemUi` |
 
---
 
## Checklist: Adding a New Screen
 
- [ ] Define `State` and `Action` in `feature:presentation`
- [ ] Decide whether an `Event` type is needed (only for one-time side effects the ViewModel alone can determine — see [When to add an Event](#when-to-add-an-event)). If not, skip the `Event` sealed interface, the `Channel`, and the `events` Flow entirely.
- [ ] Implement `ViewModel` in `feature:presentation` (expose `events` Flow only if events exist)
- [ ] Create `<Screen>Root` composable (holds ViewModel; adds `ObserveAsEvents` only when events exist)
- [ ] Create `<Screen>Screen` composable (pure state + onAction + any direct navigation callbacks, previewable)
- [ ] Route plain button-click navigation directly through composable callbacks — not through `onAction` + event
- [ ] Map any domain errors to `UiText` via extension functions
- [ ] Add `SavedStateHandle` for any form fields that must survive process death