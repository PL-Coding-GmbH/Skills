---
name: android-compose-architecture
description: |
  Compose screen-level architecture for Android/KMP - stability, recomposition strategy, state ownership, side effects, lazy layouts, deferred state reads, and TextField state dispatching. Use this skill whenever architecting a Compose screen's structure, optimizing recomposition at the screen level, deciding state ownership between ViewModel and composables, adding side effects, structuring lazy layouts, or making screen-level performance decisions. This skill is about HOW screens are structured, not how individual components are built — for component construction, see android-compose-components. Trigger on phrases like "recomposition", "stability", "@Stable", "LaunchedEffect", "DisposableEffect", "LazyColumn performance", "collectAsStateWithLifecycle", "derivedStateOf", "screen layout", "Compose performance", "deferred state read", or "state ownership".
---

# Android / KMP Compose Screen Architecture

## Core Principle

The UI is dumb. Composables render state and forward user actions — nothing more. All state lives in the ViewModel. All logic lives in the ViewModel, domain, or data layer. Compose code should contain zero business logic, zero data transformation, and minimal side effects.

---

## Stability & Recomposition

Strong skipping mode is enabled by default in modern Compose — no explicit opt-in needed.

Only annotate a state data class with `@Stable` when it contains fields the Compose compiler considers unstable (e.g., `List`, `Map`, `Set`, interfaces, or abstract types). If all fields are primitive types, `String`, or other stable types, no annotation is needed.

```kotlin
// Needs @Stable — contains a List (unstable by default)
@Stable
data class NoteListState(
    val notes: List<NoteUi> = emptyList(),
    val isLoading: Boolean = false
)

// No annotation needed — all fields are stable
data class NoteDetailState(
    val title: String = "",
    val body: String = "",
    val isSaving: Boolean = false
)
```

---

## State Ownership

All state lives in the ViewModel. Do not use `remember` or `rememberSaveable` for application state — that belongs in the ViewModel's `StateFlow` and is surfaced via `collectAsStateWithLifecycle()`.

The only exception is Compose-internal state that the framework requires you to hold in composition, such as `LazyListState`, `ScrollState`, or `PagerState`. For these, use `remember*` as needed:

```kotlin
// Acceptable — Compose-owned UI state
val lazyListState = rememberLazyListState()

// Reacting to Compose-owned state with derivedStateOf
val showScrollToTop by remember {
    derivedStateOf { lazyListState.firstVisibleItemIndex > 5 }
}
```

`derivedStateOf` should only be used in these rare scenarios where Compose-internal state drives a derived value. If the derivation can happen in the ViewModel, it should.

Always collect ViewModel state with lifecycle awareness:
```kotlin
val state by viewModel.state.collectAsStateWithLifecycle()
```

---

## Side Effects

Side effects should be avoided when possible. If something can be handled by the ViewModel through an Action, do that instead of using a side effect in a composable.

When a side effect is truly necessary (e.g., interacting with Android lifecycle APIs that have no ViewModel equivalent), extract it into a dedicated composable to keep the Screen composable clean:

```kotlin
// Extracted into its own composable
@Composable
fun ObserveLifecycle(onStart: () -> Unit, onStop: () -> Unit) {
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> onStart()
                Lifecycle.Event.ON_STOP -> onStop()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
}
```

`LaunchedEffect` is acceptable when genuinely needed, but question whether the work belongs in the ViewModel first. Do not use custom `CompositionLocal`s.

---

## Lazy Layouts

Add `key` to lazy list items when there is an obvious unique identifier available. Don't force it if it's unclear which property is unique:

```kotlin
LazyColumn {
    items(
        items = state.notes,
        key = { it.id }  // id is clearly unique
    ) { note ->
        NoteItem(note = note, onClick = { onAction(OnNoteClick(note.id)) })
    }
}
```

---

## Animations — Recomposition Avoidance

Avoid animations that cause recompositions. Prefer approaches that animate below the recomposition layer:

- **`graphicsLayer`** — for alpha, scale, rotation, translation
- **Offset lambda** — for position changes (`offset { ... }`)
- **`Canvas`** — for custom drawing that animates
- **`animateFloatAsState` + `graphicsLayer`** — animate a float, apply in graphicsLayer

```kotlin
// Good — animates without recomposition
val alpha by animateFloatAsState(if (state.isVisible) 1f else 0f)
Box(
    modifier = Modifier.graphicsLayer { this.alpha = alpha }
)

// Bad — causes recomposition on every frame
Box(
    modifier = Modifier.alpha(animatedAlpha)
)
```

**Deferred state reads:** When a value drives an animation, pass it as a lambda rather than reading it directly. This defers the state read to the layout/draw phase and avoids recomposition:

```kotlin
// Good — deferred read
fun Modifier.animatedOffset(offsetProvider: () -> IntOffset) =
    offset { offsetProvider() }

// Bad — immediate read causes recomposition
fun Modifier.animatedOffset(offset: IntOffset) =
    offset(x = offset.x.dp, y = offset.y.dp)
```

---

## TextField

Text input state lives in the ViewModel. Every keystroke dispatches an Action:

```kotlin
// In the Screen composable
TextField(
    value = state.title,
    onValueChange = { onAction(NoteEditorAction.OnTitleChange(it)) }
)
```

The ViewModel updates state (and optionally persists to `SavedStateHandle`) in response to the Action — see the **android-presentation-mvi** skill for the full pattern.

---

## Screen Previews

Every Screen composable should have at least one meaningful `@Preview` that shows a realistic state:

```kotlin
@Preview
@Composable
private fun NoteListScreenPreview() {
    AppTheme {
        NoteListScreen(
            state = NoteListState(
                notes = listOf(
                    NoteUi("1", "Meeting notes", "Mar 15"),
                    NoteUi("2", "Shopping list", "Mar 14")
                )
            ),
            onAction = {}
        )
    }
}
```

Wrap previews in the app theme so they reflect real appearance. Use realistic sample data, not empty states (unless previewing the empty state specifically).

For component-level preview conventions (one preview per meaningful state, separate functions), see **android-compose-components**.

---

For component construction rules (IconButton wrapping, sizing, design system reuse, icons, string resources, previews per state), see **android-compose-components**.
