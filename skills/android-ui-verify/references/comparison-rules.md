# Structural Comparison Rules

## dp Conversion Formula

```
dp = px_on_device / density_factor
density_factor = physical_density / 160
```

Example: A device with density 420 has `density_factor = 2.625`.
An element with pixel bounds `[0,0][283,126]` has dimensions `108dp x 48dp`.

---

## Figma → Android Type Mapping

Figma designs use component types that don't map 1:1 to Android widget classes. Use semantic matching:

| Figma Type | Android Class(es) | Notes |
|------------|-------------------|-------|
| Text | `android.widget.TextView`, `android.widget.EditText` | EditText if inside a text field component |
| Frame (vertical) | `android.view.View`, `android.widget.LinearLayout` | Compose Column renders as View |
| Frame (horizontal) | `android.view.View`, `android.widget.LinearLayout` | Compose Row renders as View |
| Frame (clickable) | `android.widget.Button`, `android.view.View` (clickable=true) | Check `clickable` attribute |
| Rectangle | `android.view.View` | Decorative or container |
| Image / Vector | `android.widget.ImageView` | Check content-desc for icon identity |
| Instance (component) | Varies | Map to the component's root type |
| Boolean (toggle) | `android.widget.Switch`, `android.widget.CheckBox` | Check `checkable` interaction |
| Input field | `android.widget.EditText` | Check `focusable` + may have hint text |
| Scroll container | Any with `scrollable="true"` | Figma frames with overflow scroll |

### Compose-specific notes

Jetpack Compose renders most elements as generic `android.view.View` in UI Automator. Rely on:
- `resource-id` (maps to `Modifier.testTag()`)
- `text` content
- `content-desc` (maps to `Modifier.semantics { contentDescription = ... }`)
- Hierarchy position

Do NOT rely on `class` names for Compose UIs — they are often just `android.view.View`.

---

## Hierarchy Normalization

Android's view hierarchy often has wrapper nodes that don't exist in the Figma design. Ignore these when comparing:

### Always ignore (transparent wrappers)
- `android.widget.FrameLayout` with a single child (unless it has meaningful resource-id)
- `android.view.ViewGroup` with a single child
- `android.widget.LinearLayout` with a single child
- `androidx.compose.ui.platform.ComposeView`
- `android.view.View` with no text, no resource-id, no content-desc, and a single child

### Never ignore (meaningful containers)
- Any element with `resource-id`
- Any element with `text` or `content-desc`
- Any element with `scrollable="true"`
- Any element with multiple children (it's a layout container)

### Matching strategy
1. Flatten both trees by removing transparent wrappers.
2. Match top-down: start from the root meaningful element.
3. For each reference element, find the best match in the device tree by:
   - resource-id match (exact)
   - text match (exact)
   - content-desc match (exact)
   - type + child count + sibling position (fuzzy)

---

## Sizing Comparison Rules

### Tolerance
- **±4dp** for width, height, and spacing.
- Report the delta in the check result.

### Full-width elements
Elements that span the full screen width in the reference (width equals the design's frame width) should span the full screen width on device. Compare as:
```
abs(element_width_dp - screen_width_dp) <= 4dp
```

### Fixed-size elements
Compare directly against the reference dimension in dp:
```
abs(actual_dp - expected_dp) <= 4dp
```

### Proportional elements
If the reference design uses percentage-based sizing (e.g., "50% of parent width"), compare the ratio:
```
actual_ratio = element_width_dp / parent_width_dp
expected_ratio = reference_width / reference_parent_width
abs(actual_ratio - expected_ratio) <= 0.05  (5% tolerance)
```

---

## Spacing Calculation

### Vertical spacing between siblings
```
spacing_dp = (next_sibling.top_dp - current_sibling.bottom_dp)
where:
  top_dp = bounds_top_px / density_factor
  bottom_dp = bounds_bottom_px / density_factor
```

### Horizontal spacing between siblings
```
spacing_dp = (next_sibling.left_dp - current_sibling.right_dp)
```

### Padding (element to parent)
```
padding_top_dp    = (child.top_dp - parent.top_dp)
padding_left_dp   = (child.left_dp - parent.left_dp)
padding_bottom_dp = (parent.bottom_dp - child.bottom_dp)
padding_right_dp  = (parent.right_dp - child.right_dp)
```

---

## Scroll Detection Heuristic

To determine if a scrollable container has been fully scrolled:

1. Before scrolling, record the `text` and `resource-id` of all visible children.
2. After each scroll, record the same.
3. **End of scroll** if ANY of:
   - The set of visible elements is identical to the previous dump (no new content appeared).
   - A "footer" or "end of list" indicator is visible.
   - The scroll action didn't change any element positions (bounds unchanged).
4. **Safety limit**: Stop after 20 scroll iterations regardless.

---

## Text Matching Rules

### Static text
- Exact case-sensitive match.
- Trim leading/trailing whitespace before comparing.
- Example: Reference says "Submit" → device must show "Submit" (not "submit" or "SUBMIT").

### Dynamic text
The calling agent should flag which text fields contain dynamic content. For these:
- Verify the element exists and contains non-empty text.
- Do NOT match the exact value.
- Examples of dynamic content: timestamps, user names, counts, prices, IDs.

### Placeholder / hint text
- Figma designs often show placeholder text in input fields.
- On Android, this may appear as `text` (if unfocused) or be absent (if the field is empty and focused).
- Match placeholder text against the element's `text` attribute. If empty, check if the element is an `EditText` — placeholders may not appear in UI Automator dumps.
- Report as WARNING (not FAIL) if placeholder text can't be verified.

---

## Common False Positive Scenarios

Avoid reporting these as failures:

1. **System UI overlap**: Status bar and navigation bar elements appear in the UI dump but aren't part of the app. Filter out elements with `resource-id` starting with `com.android.systemui`.
2. **Keyboard visible**: When a text field is focused, the soft keyboard may push content up. Account for this by checking if an `InputMethod` element is present.
3. **Compose recomposition artifacts**: Immediately after navigation, the UI tree may contain stale nodes. Always wait 500ms and re-dump before comparing.
4. **Toolbar/ActionBar**: The app's toolbar may have extra system-injected elements (overflow menu, navigation icon). Compare only the title and explicitly designed toolbar content.
5. **RecyclerView/LazyColumn item recycling**: Off-screen items may not exist in the tree. This is expected — verify them via scrolling (Step 5 of SKILL.md).
6. **LazyColumn/LazyRow not scrollable**: A lazy list with fewer items than needed to fill the viewport reports `scrollable="false"` in UI Automator. This is correct Android behavior — the list WILL scroll once more items are added. **Always verify in source code**: if the composable uses `LazyColumn`/`LazyRow`, report as INFO, not FAIL.
7. **Dynamic item count mismatch**: Figma mockups show placeholder items (e.g., 8 list items) but the device shows fewer (e.g., 3). If the composable uses `items(data)` or `forEach`, the count is data-dependent. Report as INFO.
8. **Conditional visibility**: Elements wrapped in `if (condition)`, `AnimatedVisibility`, or `Crossfade` may not appear depending on the current state. Verify the condition in source code before reporting as FAIL.
9. **Data-dependent sizing**: Elements using `wrapContentSize`, `IntrinsicSize`, or height derived from text content may differ from the reference when the actual data differs from the mockup data. Verify in source code.

---

## Source Code Cross-Reference Rules

When a structural comparison produces a mismatch, **always cross-reference the source code before classifying it as FAIL**. This prevents false positives that could lead to unnecessary code changes and potential bugs.

### When to read source code

Read source code for ANY mismatch that could be data-dependent or state-dependent:
- Scrollable attribute doesn't match
- Element count doesn't match
- Element is missing from the tree
- Element size is significantly different from reference
- A container's layout direction seems wrong

Do NOT read source code for:
- Wrong text content (always a real issue)
- Wrong sibling order (code-determined, not data-dependent)
- Wrong element type (always a real issue)

### What to look for in source code

| Mismatch type | Look for in source | If found → classify as |
|---------------|-------------------|----------------------|
| `scrollable="false"` but should scroll | `LazyColumn`, `LazyRow`, `verticalScroll()`, `horizontalScroll()` | **INFO** — will scroll with more content |
| Fewer items than reference | `items(list)`, `itemsIndexed(list)`, `forEach { }` | **INFO** — count depends on data |
| Missing element | `if (state.x)`, `AnimatedVisibility`, `when (state)` | **INFO** — conditionally rendered |
| Wrong size | `wrapContentSize()`, `IntrinsicSize`, `height(IntrinsicSize.Min)` | **INFO** — size depends on content |
| Missing element | No conditional logic found — element should always be present | **FAIL** — real bug |
| Wrong size | Fixed size modifier (`height(48.dp)`) that doesn't match reference | **FAIL** — real bug |

### How to find the source code

1. The calling agent provides the composable names as a prerequisite.
2. Use `Grep` to find the composable function: `@Composable.*fun ScreenName`.
3. Read the file to understand the layout logic.
4. If the composable delegates to sub-composables, follow the chain.

### Classification output

For each source-code-verified finding, include in the report:
```json
{
  "status": "INFO",
  "source_verified": "LazyColumn in HabitListScreen.kt:42 — scrollable='false' because 3 items fit within viewport. Will scroll when more habits are added."
}
```

---

## Behavioral Verification Rules

After structural checks, the skill exercises features to verify they work functionally.

### Deriving testable flows

From the calling agent's context about what was built, identify:
1. **CRUD flows**: Any screen that creates, reads, updates, or deletes data
2. **Navigation flows**: Tapping an item opens a detail screen, back returns to list
3. **State change flows**: Toggles, checkboxes, selections that persist
4. **Validation flows**: Form submissions with invalid data should show errors

### Input generation

Use recognizable test strings that are easy to find in UI dumps:
- Text fields: `"Test Item 12345"`, `"Test Habit ABC"`
- Email fields: `"test@example.com"`
- Number fields: `"42"`, `"100"`
- Avoid special characters that `adb shell input text` can't handle (spaces need `keyevent 62`)

### Outcome verification

After performing an action, verify the result by:
1. Navigating to the screen where the result should appear
2. Dumping the UI tree
3. Searching for the test data in `text` attributes of elements
4. If not found, try scrolling (the item may be off-screen)

### Timing for async operations

Same as dynamic state verification:
- Poll up to 5 times, 1 second apart
- If the result doesn't appear after 5s, check source code for backend dependencies

### When a behavioral failure is NOT a code bug

Source-code-verify all behavioral failures:
- **Backend required**: Save logic calls a remote API that isn't running → INFO
- **Auth required**: Action needs authentication that isn't set up in test → INFO
- **Missing dependency**: Feature depends on another feature that wasn't built yet → INFO
- **Code is actually broken**: Click handler not wired, wrong navigation route → FAIL
