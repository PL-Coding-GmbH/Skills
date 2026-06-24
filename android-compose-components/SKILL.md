---
name: android-compose-components
description: |
  Building individual Compose UI components for Android/KMP — IconButton wrapping, project icon objects, previews per state, parameter design, sizing with relative modifiers, theme colors, design system reuse, Material 3 as the base for design-system components, component decomposition, string resources, animations in graphicsLayer, slot composables, and modifier extensions. Use this skill whenever writing or modifying a composable function that is NOT a Root/Screen-level composable: buttons, cards, list items, toolbars, input fields, bottom sheets, dialogs, or any extracted sub-composable. This skill applies every time you write raw Compose UI code for a component — even small ones. For Root/Screen composables, use android-presentation-mvi instead. Trigger on phrases like "create a component", "composable function", "IconButton", "Icon composable", "preview", "modifier extension", "slot API", "design system component", "shared button", "custom icon button", "design-system icon button", "wrap Material 3", "FilledTonalIconButton", "top app bar component", "text field component", "tab layout component", "dropdown menu component", "confirmation dialog component", "contentDescription", "fillMaxWidth", "MaterialTheme.colorScheme", "extract composable", "reusable composable", "string resource in composable", "component", or "Compose UI".
---

# Android / KMP Compose Component Patterns

## Scope

This skill applies to every composable that is **not** a Root or Screen composable. If you are creating or modifying `<Feature>Root` or `<Feature>Screen`, use **android-presentation-mvi** (structure) and **android-compose-architecture** (recomposition, state ownership, side effects) instead.

Adaptive layout (window size classes, scaffold layout) is a screen-level concern — individual components should be flexible enough to fill whatever space they're given without being aware of the device form factor. For structurally different layouts across device configurations, see **compose-adaptive-layouts**.

---

## Parameter Design

Composables receive only the parameters they actually need — never the entire screen state data class. This keeps components reusable and testable, and limits the blast radius of recompositions to only what changed.

Actions bubble up via properly named lambdas that describe what happened, not what the caller should do:

```kotlin
// Good — accepts only what it needs, descriptive lambdas
@Composable
fun NoteItem(
    title: String,
    formattedDate: String,
    onNoteClick: () -> Unit,
    onDeleteClick: () -> Unit,
    modifier: Modifier = Modifier
)

// Bad — takes the whole screen state, generic lambda
@Composable
fun NoteItem(
    state: NoteListState,
    onAction: (NoteListAction) -> Unit,
    modifier: Modifier = Modifier
)
```

The `modifier` parameter should always be included and default to `Modifier`. Place it after required parameters.

---

## No Local State

Never hold local state in composables unless it is purely Compose-internal — things like focus state, scroll position, or animation state that have no meaning outside the composable. Domain or screen-specific state always comes in as a parameter, and user interactions always bubble up via lambdas.

```kotlin
// Bad — holding domain state locally
@Composable
fun NoteItem(note: NoteUi) {
    var isExpanded by remember { mutableStateOf(false) } // belongs in ViewModel
    // ...
}

// Good — state comes in, action goes out
@Composable
fun NoteItem(
    note: NoteUi,
    isExpanded: Boolean,
    onExpandToggle: () -> Unit,
    modifier: Modifier = Modifier
)

// Acceptable — purely Compose-internal state
@Composable
fun SearchField(
    query: String,
    onQueryChange: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    var isFocused by remember { mutableStateOf(false) }
    // isFocused only drives visual styling, not business logic
}
```

---

## IconButton Wrapping

Every clickable icon must be wrapped in an `IconButton`. Bare `Icon` with a `Modifier.clickable` misses the minimum touch target (48dp) and the ripple indication that users expect. Always provide a `contentDescription` via string resources. Use the default `IconButton` size — no hardcoded modifier size unless the requirements explicitly demand a specific dimension.

When the icon's purpose can change (e.g., a toggle), the `contentDescription` should reflect the current state:

```kotlin
// Good — IconButton with conditional contentDescription
IconButton(onClick = onToggleVisibility) {
    Icon(
        painter = if (isVisible) AppIcons.EyeOpen else AppIcons.EyeClosed,
        contentDescription = stringResource(
            if (isVisible) Res.string.cd_hide_password
            else Res.string.cd_show_password
        )
    )
}

// Bad — bare icon with clickable, no touch target, no ripple
Icon(
    painter = AppIcons.EyeOpen,
    contentDescription = null,
    modifier = Modifier.clickable { onToggleVisibility() }
)

// Bad — hardcoded size on IconButton (use the 48dp default)
IconButton(
    onClick = onDelete,
    modifier = Modifier.size(32.dp)  // don't do this
) {
    Icon(
        painter = AppIcons.Bin,
        contentDescription = stringResource(Res.string.cd_delete)
    )
}
```

---

## Icons — Project Icon Object First

Icons should come from the project's icon object in `:core:design-system`, not from Material `Icons`. Material Icons are only acceptable as a fallback when no project icon exists, or when the requirements explicitly say to use them. The icon object centralizes all imported vectors (typically from Figma via the **figma-to-android-vector** skill) and exposes them as `Painter` via `@Composable get()`:

```kotlin
// In :core:design-system — the icon object pattern
object AppIcons {
    val Edit: Painter @Composable get() = painterResource(Res.drawable.ic_edit)
    val Bin: Painter @Composable get() = painterResource(Res.drawable.ic_bin)
    val ChevronLeft: Painter @Composable get() = painterResource(Res.drawable.ic_chevron_left)
}

// Usage — always prefer the project icon object
Icon(
    painter = AppIcons.Edit,
    contentDescription = stringResource(Res.string.cd_edit_note)
)

// Fallback only — when no project icon exists
Icon(
    imageVector = Icons.Default.Search,
    contentDescription = stringResource(Res.string.cd_search)
)
```

Before using a Material Icon, check whether the project's icon object already has an equivalent. When adding a new icon, import the vector from Figma using the **figma-to-android-vector** skill and add it to the icon object.

---

## Sizing

Prefer relative modifiers over hardcoded dimensions. Hardcoded sizes break on different screen densities and font scale settings, and make components rigid when they should be flexible. Only use `Modifier.height()`, `Modifier.width()`, or `Modifier.size()` when the dimension is a true design constant that never changes.

**Prefer:**
- `fillMaxWidth()`, `fillMaxHeight()`, `fillMaxSize()` — fill available space
- `weight()` inside `Row`/`Column` — proportional distribution
- `aspectRatio()` — maintain proportions
- `widthIn(min, max)`, `heightIn(min, max)` — constrained ranges
- `wrapContentWidth()`, `wrapContentHeight()` — size to content

```kotlin
// Good — relative sizing
Row(modifier = Modifier.fillMaxWidth()) {
    Text(
        text = title,
        modifier = Modifier.weight(1f)
    )
    IconButton(onClick = onDeleteClick) {
        Icon(
            painter = AppIcons.Bin,
            contentDescription = stringResource(Res.string.cd_delete)
        )
    }
}

// Bad — hardcoded width that breaks on different screens
Row(modifier = Modifier.width(360.dp)) {
    Text(
        text = title,
        modifier = Modifier.width(280.dp)
    )
}
```

---

## Colors from Theme

Always load colors from `MaterialTheme.colorScheme` (or the project's extended theme if one exists). Never reference hardcoded colors from `Color.kt` directly — those are theme definitions, not for direct use in composables. A color that looks right in light theme will be wrong in dark theme if hardcoded.

```kotlin
// Good — theme-aware
Text(
    text = title,
    color = MaterialTheme.colorScheme.onSurface
)

Surface(color = MaterialTheme.colorScheme.surfaceVariant) {
    // ...
}

// Bad — hardcoded, breaks in dark theme
Text(
    text = title,
    color = Color(0xFF1C1B1F)
)
```

If the project has an extended theme (e.g., `AppTheme.extendedColors`), check for custom color attributes before falling back to `MaterialTheme.colorScheme`. If no extended theme exists, stick to Material defaults.

---

## Design System Reuse

Before building a component from scratch, check `:core:design-system` for existing composables that can be reused or extended. The design system module is the single source of truth for shared UI primitives — buttons, cards, text fields, toolbars, and other building blocks.

If a suitable composable exists, use it. If it's close but not quite right, consider whether extending it (via parameters or slots) serves the project better than creating a new one.

---

## Design System Components — Material 3 First

A *design system component* is a fundamental, app-wide UI primitive that lives in `:core:design-system` and is consumed by every feature module — buttons, icon buttons, floating action buttons, tab layouts, top app bars, text fields, drop-down menus, confirmation dialogs. The previous section covers using them; this one covers building them.

When building one, the base **must** be a Material 3 composable. Pick the right M3 variant before customizing — a custom icon button with a background tile starts from `FilledTonalIconButton` (or `FilledIconButton` / `OutlinedIconButton`), not a plain `IconButton` wrapped in a `Box`. A custom segmented selector starts from `TabRow` + `Tab`, not a `Row` of `Box`es. A custom destructive prompt starts from `AlertDialog`, not a `Surface` built up by hand. Customize the M3 base via its own parameters — `colors`, `shape`, `border`, `contentPadding`, slot content — before reaching for anything lower-level.

Raw `Box` / `Column` / `Row` composition is the fallback, used only when no M3 component can structurally model the design. Starting from primitives means re-implementing what M3 already gives you for free: real 48dp touch targets, correct internal paddings and spacings, ripple/state-layer behavior, and tested accessibility semantics — and usually getting some of it subtly wrong.

```kotlin
// Good — custom "circular tinted icon button" wraps the right M3 variant
@Composable
fun AppIconButton(
    onClick: () -> Unit,
    icon: Painter,
    contentDescription: String?,
    modifier: Modifier = Modifier
) {
    FilledTonalIconButton(
        onClick = onClick,
        modifier = modifier,
        shape = CircleShape,
        colors = IconButtonDefaults.filledTonalIconButtonColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer,
            contentColor = MaterialTheme.colorScheme.onSecondaryContainer
        )
    ) {
        Icon(painter = icon, contentDescription = contentDescription)
    }
}

// Bad — rebuilt from primitives; no real 48dp touch target, no ripple/state layer,
// manual padding, no built-in accessibility role
@Composable
fun AppIconButton(
    onClick: () -> Unit,
    icon: Painter,
    contentDescription: String?,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .size(40.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.secondaryContainer)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        Icon(painter = icon, contentDescription = contentDescription)
    }
}
```

---

## Slot Composables

Use `@Composable` lambda parameters for content areas that need to be flexible — primarily in design system components where the same container should accept different content:

```kotlin
// Design system component — slots make sense
@Composable
fun AppCard(
    modifier: Modifier = Modifier,
    header: @Composable () -> Unit,
    content: @Composable () -> Unit
) {
    Card(modifier = modifier) {
        header()
        content()
    }
}
```

Feature-level composables should prefer typed parameters over slots. Slots add indirection — use them when the content truly varies in shape, not just in value.

---

## Component Decomposition & Visibility

Extract sub-composables when they represent a conceptually independent UI element that could be useful in a different context. Apply strict visibility rules:

| Visibility | When |
|---|---|
| `private` | Used only in the same file |
| `internal` | Scoped to the feature module |
| `public` | Only if it lives in `:core:design-system` |

When in doubt, start `private` and promote visibility only when reuse actually happens.

---

## Modifier Extensions

Prefer plain `Modifier` extension functions or `Modifier.Node`-based factories. Do not make modifier extensions `@Composable` — it couples them to composition and prevents use in non-composable contexts:

```kotlin
// Good — plain extension
fun Modifier.shimmerEffect(): Modifier = composed {
    // shimmer implementation
}

// Better — Modifier factory (no composition needed)
fun Modifier.roundedBackground(color: Color, radius: Dp) =
    background(color, RoundedCornerShape(radius))
```

---

## Previews — One Per Distinct State, Always

Every component you build **must** ship with a `@Preview` for **every distinct state it can render**. This is not optional and not "preview the happy path." A component with five visually distinct states gets five previews. Use separate `@Preview` functions — never `PreviewParameter` — so each state is independently visible and scannable in the preview panel.

A state is *distinct* whenever the component looks different on screen. Enumerate them mechanically from the component's inputs and environment, and write one preview per case:

- **Each value of every `Boolean` / `enum` parameter that affects the UI** — `isSelected` true *and* false, `isExpanded` true *and* false, each `enum` variant. If two booleans both change the look, preview the meaningful combinations, not just one.
- **Each content/data variation** — empty, single item, many items; loading, error, success; short text *and* long text that wraps or truncates.
- **Each look the component takes on different screen sizes** — when the layout can reflow, add previews with `@Preview(widthDp = 320)` (compact) and `@Preview(widthDp = 840)` (expanded/tablet) so you can see it adapt. Add `@Preview(fontScale = 2f)` when large font scale could break the layout.
- **Light *and* dark theme** — either two `@Preview` functions, or a single function annotated with both `@Preview` and `@Preview(uiMode = UI_MODE_NIGHT_YES)`.

Wrap every preview in the app theme and use realistic sample data:

```kotlin
@Preview(name = "Default")
@Preview(name = "Dark", uiMode = UI_MODE_NIGHT_YES)
@Composable
private fun NoteItemPreview() {
    AppTheme {
        NoteItem(
            title = "Meeting notes",
            formattedDate = "Mar 15, 2026",
            isExpanded = false,
            onNoteClick = {},
            onDeleteClick = {}
        )
    }
}

@Preview(name = "Expanded")
@Composable
private fun NoteItemExpandedPreview() {
    AppTheme {
        NoteItem(
            title = "Meeting notes",
            formattedDate = "Mar 15, 2026",
            isExpanded = true,
            onNoteClick = {},
            onDeleteClick = {}
        )
    }
}

// Long title that must wrap/truncate — a distinct visual state
@Preview(name = "Long title")
@Composable
private fun NoteItemLongTitlePreview() {
    AppTheme {
        NoteItem(
            title = "Quarterly planning sync with the whole product and design org",
            formattedDate = "Mar 15, 2026",
            isExpanded = false,
            onNoteClick = {},
            onDeleteClick = {}
        )
    }
}

// Layout reflow on a wide window — a distinct visual state
@Preview(name = "Expanded width", widthDp = 840)
@Composable
private fun NoteItemWidePreview() {
    AppTheme {
        NoteItem(
            title = "Meeting notes",
            formattedDate = "Mar 15, 2026",
            isExpanded = false,
            onNoteClick = {},
            onDeleteClick = {}
        )
    }
}
```

The only previews you skip are states the component cannot actually render — don't invent states just to add previews, and don't add a width/fontScale preview for a component whose layout genuinely can't reflow. But when in doubt, add the preview: an unwritten preview is the default failure here, not an over-written one.

---

## String Resources

All user-facing text must come from string resources — never hardcode strings in composables. This enables localization and keeps text centralized.

```kotlin
// Android
Text(text = stringResource(R.string.note_title_label))

// KMP (Compose Multiplatform)
Text(text = stringResource(Res.string.note_title_label))
```

Check the project to determine which approach is in use. For content descriptions, follow the same pattern — `stringResource(Res.string.cd_delete)`, not a raw string.

---

## Animations

Ensure animated values are read inside `graphicsLayer {}` or `offset {}` lambdas so the animation runs in the draw/layout phase without triggering recomposition. Reading an animated value during composition means every frame causes a recomposition — wasteful and potentially janky.

```kotlin
// Good — animation reads deferred to graphicsLayer
val scale by animateFloatAsState(if (isSelected) 1.1f else 1f)
Box(
    modifier = Modifier.graphicsLayer {
        scaleX = scale
        scaleY = scale
    }
)

// Good — offset lambda defers position reads
val offsetY by animateDpAsState(if (isExpanded) 0.dp else (-16).dp)
Box(
    modifier = Modifier.offset { IntOffset(0, offsetY.roundToPx()) }
)

// Bad — reading animated value during composition
val alpha by animateFloatAsState(if (isVisible) 1f else 0f)
Box(modifier = Modifier.alpha(alpha))  // recomposes every frame
```

---

## Effect Handlers

Avoid `LaunchedEffect`, `SideEffect`, and `DisposableEffect` in components unless truly necessary. If a component needs to react to a value change, that reaction almost always belongs in the caller or the ViewModel — not inside the component itself.

The rare exceptions are Compose-internal concerns like requesting focus on first composition or cleaning up a callback registration.

---

## Accessibility

Use meaningful `contentDescription` on all interactive or informational visual elements. Always load descriptions from string resources. For purely decorative elements that convey no information, set `contentDescription = null`:

```kotlin
// Interactive — needs description
Icon(
    painter = AppIcons.Bin,
    contentDescription = stringResource(Res.string.cd_delete_note)
)

// Decorative — no description needed
Icon(
    painter = AppIcons.Divider,
    contentDescription = null
)
```

---

## Checklist: Building a New Component

- [ ] Check `:core:design-system` for existing composables to reuse
- [ ] When building a design system component, base it on a Material 3 composable (choose the right variant — e.g. `FilledTonalIconButton` for an icon button with a background); raw `Box` / `Column` / `Row` only as a fallback
- [ ] Accept only needed parameters — not the entire screen state
- [ ] Actions bubble up via named lambdas (`onXClick`, `onXChange`)
- [ ] Include `modifier: Modifier = Modifier` parameter
- [ ] No local state unless purely Compose-internal
- [ ] Wrap clickable icons in `IconButton` with `contentDescription`
- [ ] Use project icon object before Material Icons
- [ ] Prefer relative sizing over hardcoded dimensions
- [ ] Colors from `MaterialTheme.colorScheme`, not hardcoded
- [ ] All user-facing strings via `stringResource`
- [ ] Animations read in `graphicsLayer {}` / `offset {}` lambdas
- [ ] One `@Preview` per distinct state — every UI-affecting `Boolean`/`enum` value, content/data variation, short *and* long text, light *and* dark theme, plus width/`fontScale` previews wherever the layout can reflow — all wrapped in app theme
- [ ] Set visibility: `private` / `internal` / `public` based on scope
- [ ] No effect handlers unless truly necessary
