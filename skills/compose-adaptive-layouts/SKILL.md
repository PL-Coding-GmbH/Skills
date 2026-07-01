---
name: compose-adaptive-layouts
description: |
  Adaptive Compose Multiplatform layouts for structurally different UIs across device configurations — DeviceConfiguration enum, when(configuration) branching, slot-based adaptive layout composables, cross-screen pattern analysis, and Figma mockup interpretation. Works for Android, KMP, and Compose Desktop. Use this skill whenever the composable tree structure itself must change across device configurations — elements rearranged (Column to Row), elements appearing or disappearing entirely, or container wrapping changes (full-screen to centered card). Do NOT use this skill for responsive sizing achievable with fillMaxWidth(), widthIn(max = ...), Modifier.weight(), or responsive padding. Trigger on phrases like "adaptive layout", "tablet layout", "desktop layout", "landscape layout", "different layout per screen size", "window size class", "DeviceConfiguration", "side-by-side on tablet", "rearrange for landscape", "responsive screen structure", "multi-form-factor", "centered card on tablet", "structural UI difference", "adaptive composable", "screen looks different on tablet", or "compose multiplatform responsive".
---

# Compose Adaptive Layouts

## Scope — When This Skill Applies

This skill applies **only** when the composable tree structure is fundamentally different across device configurations. It does **not** apply when the same composable hierarchy works across all sizes with only dimension, spacing, or padding changes.

**Three trigger conditions — at least one must be true:**

1. **Elements rearranged** — layout direction changes (vertical stack → horizontal row, or vice versa)
2. **Elements appear or disappear** — a component exists on one configuration but not another (e.g., sidebar only on desktop, logo hidden in landscape)
3. **Container wrapping changes** — the same content lives in fundamentally different containers (full-bleed surface on mobile → centered card on tablet)

**If none of these are true, do NOT create an adaptive layout.** Use dynamic modifiers instead.

For component-level rules (parameter design, previews, sizing), see **android-compose-components**. For screen-level architecture (state ownership, recomposition, side effects), see **android-compose-architecture**.

### Does This Screen Need an Adaptive Layout?

```kotlin
// ✗ Does NOT need an adaptive layout — same hierarchy, just constrained width
// Use dynamic modifiers instead
@Composable
fun SettingsScreen(state: SettingsState) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .widthIn(max = 600.dp)  // centers naturally on wide screens
            .padding(horizontal = 16.dp)
    ) {
        SettingsHeader(state.userName)
        SettingsList(state.items)
    }
}
```

```kotlin
// ✓ DOES need an adaptive layout — structure changes fundamentally
// Mobile: full-bleed vertical form
// Landscape: logo left, form right in a Row
// Tablet/Desktop: centered card with max width
@Composable
fun LoginScreen(state: LoginState, onAction: (LoginAction) -> Unit) {
    AdaptiveFormLayout(
        logo = { AppLogo() },
        formContent = {
            EmailField(state.email, onAction)
            PasswordField(state.password, onAction)
            LoginButton(state.isLoading, onAction)
        }
    )
}
```

---

## DeviceConfiguration Utility

Every adaptive layout depends on a `DeviceConfiguration` enum that classifies the current window into one of five categories. This utility lives in the `core/presentation` module (or equivalent `commonMain` source set).

**Before creating it, search the project:**

```
grep -r "DeviceConfiguration" --include="*.kt"
grep -r "currentDeviceConfiguration" --include="*.kt"
```

If it does not exist, create it. If it exists, use the existing one.

### Reference Implementation

```kotlin
package <project>.core.presentation.util

import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.runtime.Composable
import androidx.window.core.layout.WindowSizeClass
import androidx.window.core.layout.WindowSizeClass.Companion.HEIGHT_DP_EXPANDED_LOWER_BOUND
import androidx.window.core.layout.WindowSizeClass.Companion.HEIGHT_DP_MEDIUM_LOWER_BOUND
import androidx.window.core.layout.WindowSizeClass.Companion.WIDTH_DP_EXPANDED_LOWER_BOUND
import androidx.window.core.layout.WindowSizeClass.Companion.WIDTH_DP_MEDIUM_LOWER_BOUND

@Composable
fun currentDeviceConfiguration(): DeviceConfiguration {
    val windowSizeClass = currentWindowAdaptiveInfo().windowSizeClass
    return DeviceConfiguration.fromWindowSizeClass(windowSizeClass)
}

enum class DeviceConfiguration {
    MOBILE_PORTRAIT,
    MOBILE_LANDSCAPE,
    TABLET_PORTRAIT,
    TABLET_LANDSCAPE,
    DESKTOP;

    val isMobile: Boolean
        get() = this in listOf(MOBILE_PORTRAIT, MOBILE_LANDSCAPE)

    val isWideScreen: Boolean
        get() = this in listOf(TABLET_LANDSCAPE, DESKTOP)

    companion object {
        fun fromWindowSizeClass(windowSizeClass: WindowSizeClass): DeviceConfiguration {
            return with(windowSizeClass) {
                when {
                    minWidthDp < WIDTH_DP_MEDIUM_LOWER_BOUND &&
                            minHeightDp >= HEIGHT_DP_MEDIUM_LOWER_BOUND -> MOBILE_PORTRAIT
                    minWidthDp >= WIDTH_DP_EXPANDED_LOWER_BOUND &&
                            minHeightDp < HEIGHT_DP_MEDIUM_LOWER_BOUND -> MOBILE_LANDSCAPE
                    minWidthDp in WIDTH_DP_MEDIUM_LOWER_BOUND..WIDTH_DP_EXPANDED_LOWER_BOUND &&
                            minHeightDp >= HEIGHT_DP_EXPANDED_LOWER_BOUND -> TABLET_PORTRAIT
                    minWidthDp >= WIDTH_DP_EXPANDED_LOWER_BOUND &&
                            minHeightDp in HEIGHT_DP_MEDIUM_LOWER_BOUND..HEIGHT_DP_EXPANDED_LOWER_BOUND -> TABLET_LANDSCAPE
                    else -> DESKTOP
                }
            }
        }
    }
}
```

### Required Dependencies

Add these via the **android-version-catalog** skill:

- `androidx.compose.material3:material3-adaptive` — provides `currentWindowAdaptiveInfo()`
- `androidx.window:window-core` — provides `WindowSizeClass`

These go in the `core:presentation` module's `commonMain` dependencies. If `core:designsystem` depends on `core:presentation`, the types are already accessible.

---

## Pre-Creation: Cross-Screen Pattern Analysis

**Before creating any new adaptive layout, always search the project for existing ones.**

```
grep -r "currentDeviceConfiguration" --include="*.kt" -l
grep -r "DeviceConfiguration" --include="*.kt" -l
```

Check each result and compare its structural pattern against what you need:

| Pattern element | What to compare |
|----------------|----------------|
| **Container type** | Full-bleed surface vs centered card vs split pane |
| **Rearrangement** | Vertical-to-horizontal vs stacked-to-side-by-side |
| **Slot structure** | Header + content vs sidebar + main vs form + actions |
| **Variant grouping** | Which DeviceConfiguration values share branches |

**Decision:**
- If an existing layout matches → **reuse it**
- If an existing layout is close but needs one more slot → **extend it** with an optional parameter
- If no match exists → **create a new layout**

When Figma mockups are provided, compare variant structure across **all screens in the project**, not just the current one. If three screens all use "full-bleed on mobile, centered card on tablet", extract one shared layout.

---

## Placement and Naming

Adaptive layout composables always live in:

```
core/designsystem/src/commonMain/kotlin/<package>/core/designsystem/components/layouts/
```

Create this package if it does not exist.

### Naming Convention

1. **Detect the project prefix** — scan existing composables in the designsystem module for a common prefix (e.g., `Chirp`, `App`, `Note`). Use the same prefix.
2. **Follow the pattern:** `<Prefix>Adaptive<Purpose>Layout`

| Purpose | Example name |
|---------|-------------|
| Form (login, register, input) | `ChirpAdaptiveFormLayout` |
| Result (success, confirmation) | `AppAdaptiveResultLayout` |
| Detail (item detail, profile) | `NoteAdaptiveDetailLayout` |
| Split (list + detail) | `AppAdaptiveSplitLayout` |

One-off adaptive layouts (unique to a single screen) are allowed when the structure truly cannot be generalized, but they still go in the designsystem layouts package.

---

## Adaptive Layout Structure Pattern

### Core Shape

Every adaptive layout follows this structure:

```kotlin
@Composable
fun <Prefix>Adaptive<Purpose>Layout(
    // Slot parameters — flexible by context
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit  // or RowScope, BoxScope, plain () -> Unit
) {
    val configuration = currentDeviceConfiguration()

    when (configuration) {
        DeviceConfiguration.MOBILE_PORTRAIT -> { /* vertical, full-bleed */ }
        DeviceConfiguration.MOBILE_LANDSCAPE -> { /* horizontal split or compact */ }
        DeviceConfiguration.TABLET_PORTRAIT -> { /* centered card or split */ }
        DeviceConfiguration.TABLET_LANDSCAPE -> { /* wide layout, side-by-side */ }
        DeviceConfiguration.DESKTOP -> { /* max-width constrained, centered */ }
    }
}
```

### Key Rules

1. **All 5 variants handled** — the `when` must be exhaustive. Group variants that share the same structure:

```kotlin
// ✓ Good — group variants with identical structure
when (configuration) {
    DeviceConfiguration.MOBILE_PORTRAIT -> { /* full-bleed surface */ }
    DeviceConfiguration.MOBILE_LANDSCAPE -> { /* row: side content + form */ }
    DeviceConfiguration.TABLET_PORTRAIT,
    DeviceConfiguration.TABLET_LANDSCAPE,
    DeviceConfiguration.DESKTOP -> { /* centered card */ }
}
```

2. **Each branch composes a different tree** — if branches only differ in padding or width, this should not be an adaptive layout:

```kotlin
// ✗ Bad — only padding differs, use responsive modifiers instead
when (configuration) {
    DeviceConfiguration.MOBILE_PORTRAIT -> {
        Column(modifier = Modifier.padding(16.dp)) { content() }
    }
    DeviceConfiguration.TABLET_PORTRAIT,
    DeviceConfiguration.TABLET_LANDSCAPE,
    DeviceConfiguration.DESKTOP -> {
        Column(modifier = Modifier.padding(32.dp)) { content() }
    }
}
```

3. **Slot API matches layout context** — use the scope that matches what the branch does with the content:
   - `ColumnScope.() -> Unit` when content is always laid out vertically
   - `RowScope.() -> Unit` when content is always laid out horizontally
   - `BoxScope.() -> Unit` when content is stacked/overlaid
   - `@Composable () -> Unit` when different branches use different layout directions

4. **Adaptive layouts do not own state** — they are pure structural containers. State comes from the ViewModel via the Screen composable that calls the layout. See **android-compose-architecture**.

### Full Example: Adaptive Form Layout

```kotlin
@Composable
fun AppAdaptiveFormLayout(
    headerText: String,
    errorText: String? = null,
    logo: @Composable () -> Unit,
    modifier: Modifier = Modifier,
    formContent: @Composable ColumnScope.() -> Unit
) {
    val configuration = currentDeviceConfiguration()

    when (configuration) {
        DeviceConfiguration.MOBILE_PORTRAIT -> {
            // Full-bleed: logo on background, form in rounded surface
            Surface(color = MaterialTheme.colorScheme.background) {
                Column(
                    modifier = modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Spacer(modifier = Modifier.height(32.dp))
                    logo()
                    Spacer(modifier = Modifier.height(32.dp))
                    Surface(
                        color = MaterialTheme.colorScheme.surface,
                        shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp),
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier
                                .padding(horizontal = 16.dp)
                                .verticalScroll(rememberScrollState())
                        ) {
                            Spacer(modifier = Modifier.height(24.dp))
                            HeaderSection(headerText, errorText)
                            Spacer(modifier = Modifier.height(24.dp))
                            formContent()
                        }
                    }
                }
            }
        }
        DeviceConfiguration.MOBILE_LANDSCAPE -> {
            // Side-by-side: logo + header left, form right
            Row(
                modifier = modifier
                    .fillMaxSize()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(24.dp)
                ) {
                    logo()
                    HeaderSection(headerText, errorText, textAlign = TextAlign.Start)
                }
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    shape = RoundedCornerShape(20.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    Column(
                        modifier = Modifier
                            .padding(16.dp)
                            .verticalScroll(rememberScrollState())
                    ) {
                        formContent()
                    }
                }
            }
        }
        DeviceConfiguration.TABLET_PORTRAIT,
        DeviceConfiguration.TABLET_LANDSCAPE,
        DeviceConfiguration.DESKTOP -> {
            // Centered card: logo above, form in constrained card
            Column(
                modifier = modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.background)
                    .padding(top = 32.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(32.dp)
            ) {
                logo()
                Column(
                    modifier = Modifier
                        .widthIn(max = 480.dp)
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(32.dp))
                        .background(MaterialTheme.colorScheme.surface)
                        .padding(horizontal = 24.dp, vertical = 32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    HeaderSection(headerText, errorText)
                    formContent()
                }
            }
        }
    }
}
```

### Simpler Example: Adaptive Result Layout

```kotlin
@Composable
fun AppAdaptiveResultLayout(
    logo: @Composable () -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit
) {
    val configuration = currentDeviceConfiguration()

    when (configuration) {
        DeviceConfiguration.MOBILE_PORTRAIT -> {
            // Full-bleed surface with logo header
            Surface(color = MaterialTheme.colorScheme.background, modifier = modifier) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Spacer(modifier = Modifier.height(32.dp))
                    logo()
                    Spacer(modifier = Modifier.height(32.dp))
                    Surface(
                        color = MaterialTheme.colorScheme.surface,
                        shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp),
                        modifier = Modifier.weight(1f).fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier
                                .padding(horizontal = 16.dp)
                                .verticalScroll(rememberScrollState())
                        ) {
                            content()
                        }
                    }
                }
            }
        }
        DeviceConfiguration.MOBILE_LANDSCAPE -> {
            // Centered card, no logo (save vertical space)
            Column(
                modifier = modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.background),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Column(
                    modifier = Modifier
                        .widthIn(max = 480.dp)
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(32.dp))
                        .background(MaterialTheme.colorScheme.surface)
                        .padding(24.dp)
                        .verticalScroll(rememberScrollState()),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    content()
                }
            }
        }
        DeviceConfiguration.TABLET_PORTRAIT,
        DeviceConfiguration.TABLET_LANDSCAPE,
        DeviceConfiguration.DESKTOP -> {
            // Centered card with logo above
            Column(
                modifier = modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.background)
                    .padding(top = 32.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(32.dp)
            ) {
                logo()
                Column(
                    modifier = Modifier
                        .widthIn(max = 480.dp)
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(32.dp))
                        .background(MaterialTheme.colorScheme.surface)
                        .padding(24.dp)
                        .verticalScroll(rememberScrollState()),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    content()
                }
            }
        }
    }
}
```

---

## Window Insets

Handle window insets in the adaptive layout **only** when both conditions are true:

1. The layout is **scaffold-like** — it wraps the entire screen content (not a sub-component)
2. The root-level composable **does not already handle insets** (no `Scaffold` with `contentWindowInsets`, no `consumeWindowInsets` higher up)

**Before adding inset handling, check:**
- Does the Activity call `enableEdgeToEdge()`?
- Does a parent `Scaffold` or composable already consume insets?

If the layout needs to handle insets:

```kotlin
// Handle insets when the adaptive layout is the outermost container
DeviceConfiguration.MOBILE_PORTRAIT -> {
    Surface(
        modifier = modifier
            .consumeWindowInsets(WindowInsets.navigationBars)
            .consumeWindowInsets(WindowInsets.displayCutout)
    ) {
        // ...
    }
}
```

If a parent already handles insets, do **not** double-consume them in the adaptive layout.

---

## Working with Figma Mockups

When Figma mockups are provided via MCP, examine **all device variant frames** for the same screen before deciding.

### Structural Differences (→ create adaptive layout)

- Elements appear in a **different order** across variants
- A component **exists on one variant but not another** (e.g., sidebar only on desktop)
- **Layout direction changes** (Column on mobile → Row on tablet)
- Content lives in **different containers** (full-bleed surface on mobile → elevated card on tablet)

### Responsive Differences (→ use dynamic modifiers, NOT this skill)

- Same elements in the same order, just wider or narrower
- Only padding, margins, or spacing values change
- Text size or icon size differs
- A list shows more columns on wider screens but the item composable is the same

### Analysis Walkthrough

When reviewing Figma mockups:

1. **List all variant frames** for the screen (mobile, tablet, desktop)
2. For each variant, **trace the composable hierarchy** top-to-bottom
3. **Compare hierarchies** — if the tree shape differs, an adaptive layout is needed
4. **Check other screens** — do any share the same structural pattern? If so, design one layout for all of them
5. If the hierarchies are identical and only sizes/spacing change → use `widthIn(max = ...)`, `fillMaxWidth()`, responsive padding

---

## Dependencies Setup

Required in `libs.versions.toml` (use the **android-version-catalog** skill to look up latest versions and add them):

```toml
[versions]
material3Adaptive = "<latest>"
windowCore = "<latest>"

[libraries]
androidx-compose-material3-adaptive = { group = "androidx.compose.material3", name = "material3-adaptive", version.ref = "material3Adaptive" }
androidx-window-core = { group = "androidx.window", name = "window-core", version.ref = "windowCore" }
```

Add to `core:presentation` module's `build.gradle.kts`:

```kotlin
commonMain.dependencies {
    api(libs.androidx.compose.material3.adaptive)
    api(libs.androidx.window.core)
}
```

Use `api` so that modules depending on `core:presentation` (like `core:designsystem`) can access `DeviceConfiguration` and `currentDeviceConfiguration()` without adding the dependencies themselves.

---

## Checklist: Creating an Adaptive Layout

- [ ] Confirm the UI structure is **truly different** across configurations — not just sizing or spacing
- [ ] Search project for existing adaptive layouts that match the pattern
- [ ] If Figma mockups are provided, compare **all screens** for shared structural patterns
- [ ] Verify `DeviceConfiguration` exists in `core:presentation` — create if missing
- [ ] Verify `material3-adaptive` and `window-core` dependencies are present
- [ ] Detect the project's naming prefix from the designsystem module
- [ ] Create the layout in `core/designsystem/components/layouts/`
- [ ] `when(configuration)` handles **all 5 variants** (exhaustive)
- [ ] Group variants that share the same structural pattern on the same branch
- [ ] Slot API matches context — `ColumnScope`, `RowScope`, `BoxScope`, or plain `@Composable () -> Unit`
- [ ] Handle window insets only if layout is scaffold-like **and** root does not already handle them
- [ ] Add previews for at least mobile portrait and one wide-screen variant
- [ ] The layout owns **zero state** — it is a pure structural container
