---
name: android-ui-verify
description: |
  Verify Android UI against Figma designs or HTML mockups by structural comparison.
  Compares layout hierarchy, text content, sizing (dp with ±4dp tolerance), and
  dynamic states using the device's UI Automator tree — never pixel-perfect.
  Use after finishing UI implementation to validate the result matches the reference.
  Trigger on: "verify UI", "check the UI", "compare against Figma",
  "does this match the design", "UI verification", "check layout matches",
  or when finishing UI implementation work that has a design reference.
---

# Android UI Verification

Structurally verify a running Android app's UI against a reference design (Figma or HTML).
This skill is invoked by the calling agent after UI implementation is complete.

**Philosophy**: Android UIs are never pixel-perfect across densities and aspect ratios. This skill compares *structure*, *text*, and *dp-converted sizing* — not colors, shadows, or pixel rendering.

---

## Prerequisites

The calling agent MUST provide:
1. **What was built** — screen names, expected elements, navigation flow
2. **Reference source** — one of:
   - A Figma URL (the skill will call `get_design_context` via MCP)
   - An HTML file path (the skill will read and parse the DOM)

The skill MUST NOT operate on raw screenshots alone — it needs structured component and text data.

---

## Step 1: Device Setup

Run these commands to detect and configure the target device:

```bash
# List connected devices
adb devices

# Get screen density (for px → dp conversion)
adb shell wm density
# Example output: "Physical density: 420"

# Get screen resolution
adb shell wm size
# Example output: "Physical size: 1080x2400"
```

### Device selection rules
- **No device connected**: Stop and report error — "No Android device detected. Connect a device or start an emulator."
- **One device**: Use it automatically.
- **Multiple devices**: Warn the user and list the device serial numbers. Ask which to use. All subsequent `adb` commands must include `-s <serial>`.

### Density calculation

```
density_factor = physical_density / 160
```

Store `density_factor` for all subsequent px → dp conversions.

---

## Step 2: Resolve Reference Design

### Figma URL

Call the Figma MCP `get_design_context` tool with the `fileKey` and `nodeId` extracted from the URL. From the response, extract:
- Component names and hierarchy (parent-child nesting)
- Text content of all text nodes
- Frame/component dimensions (width, height) in Figma's logical px (these ARE dp-equivalent)
- Layout direction (horizontal/vertical) and spacing between children
- Whether elements are marked as scrollable or have overflow

### HTML file

Read the HTML file. Parse the DOM to extract:
- Element types (div, button, input, span, img, etc.)
- Text content
- CSS width/height values (convert px to dp-equivalent if needed)
- Flex/grid layout direction and gap values
- Visibility and display properties

### Build the Reference Model

Regardless of source, normalize into a mental model of:
- **Tree structure**: Parent → children nesting
- **Per element**: type, text content, expected width/height in dp, content description
- **Layout**: direction (row/column), spacing between siblings in dp
- **Scrollable regions**: which containers scroll and what content they hold

---

## Step 3: Capture UI Tree from Device

```bash
adb exec-out uiautomator dump /dev/tty
```

This returns XML. Parse each `node` element and extract:

| XML Attribute | Use |
|---------------|-----|
| `class` | Element type (e.g., `android.widget.TextView`, `android.widget.Button`) |
| `text` | Visible text content |
| `resource-id` | Android resource ID (best identifier) |
| `content-desc` | Accessibility description |
| `bounds` | Pixel bounds as `[left,top][right,bottom]` |
| `scrollable` | Whether the element scrolls |
| `clickable` | Whether the element is tappable |
| `enabled` | Whether the element is interactive |
| `focused` | Whether the element has input focus |

### Convert bounds to dp

From `bounds="[left,top][right,bottom]"`:
```
width_dp  = (right - left) / density_factor
height_dp = (bottom - top) / density_factor
x_dp      = left / density_factor
y_dp      = top / density_factor
```

### Element identification (best-effort)

Match elements between reference and device using this priority:
1. `resource-id` (most reliable)
2. `text` content (exact match)
3. `content-desc` (accessibility label)
4. Element type + position in hierarchy (least reliable)

**If an element cannot be reliably identified** (no resource-id, no text, no content-desc, and ambiguous position), log a warning:
> "Element at [bounds] has no resource-id, text, or content-desc — consider adding a `testTag` or semantics modifier for reliable identification."

Continue verification anyway — do not stop.

---

## Step 4: Structural Comparison

Compare the reference model against the device UI tree. Check each of these aspects:

### Hierarchy
- Parent-child nesting should match semantically.
- **Allow** intermediate wrapper nodes that exist on Android but not in the design (e.g., `View` containers wrapping `ComposeView`, `FrameLayout` wrappers).
- **Fail** if a meaningful element is missing or nested under the wrong parent.

### Text content
- Exact case-sensitive string match for all visible text.
- For dynamic content (timestamps, counts, user-specific data): verify the text field exists and is non-empty rather than matching exact value. The calling agent should specify which fields are dynamic.

### Element types
- Map reference types to Android classes semantically. See [comparison-rules.md](references/comparison-rules.md) for the full mapping.
- Example: a Figma "Text" node matches `android.widget.TextView`; a "Frame with click handler" matches a clickable `View` or `Button`.

### Sizing
- Compare width and height in dp.
- **Tolerance: ±4dp**. Report as FAIL only if delta exceeds 4dp.
- Skip size comparison for elements that are `match_parent`/`fillMaxWidth` (full-width elements) — compare them proportionally instead (should be close to screen width).

### Spacing
- Calculate spacing between consecutive siblings: `next_element.y_dp - (current_element.y_dp + current_element.height_dp)` for vertical layouts.
- **Tolerance: ±4dp**.

### Sibling order
- Children should appear in the same order as the reference design.

### Visibility
- Every element in the reference design should exist in the device UI tree.
- Missing elements are a FAIL — **unless source code verification (Step 4b) reclassifies them**.

---

## Step 4b: Source Code Verification for Mismatches

**CRITICAL**: When Step 4 finds a mismatch, do NOT immediately report it as FAIL. First, cross-reference the relevant Compose source code to determine if the mismatch is a real bug or a data/state-dependent difference.

The calling agent already knows which composables were built. Use `Grep` to find the composable by name, then `Read` the file to understand the layout logic.

### Classification

| After reading source code... | Report as | Action |
|------------------------------|-----------|--------|
| The mismatch is a real layout bug (wrong modifier, missing element in code) | **FAIL** | Include in report |
| The mismatch is data-dependent (fewer items, empty state, conditional visibility) | **INFO** | Include in report with explanation of why it's not a bug |
| The mismatch is expected Android behavior (system wrappers, density rounding) | — | Suppress entirely |

### Specific scenarios to verify

1. **Scrollable mismatch** — Reference shows scrollable list, device shows `scrollable="false"`:
   - Read the composable. If it uses `LazyColumn`, `LazyRow`, or `verticalScroll`/`horizontalScroll`, it WILL scroll when content exceeds the viewport. The current data simply doesn't trigger scrolling.
   - **Report as INFO**: "LazyColumn in `HabitListScreen.kt:42` — not scrollable because current item count (3) fits within viewport. Will scroll with more items."

2. **Missing elements** — Reference shows N items, device shows fewer:
   - Check if the composable iterates over dynamic data (`items(list)`, `forEach`). If so, the count depends on runtime data.
   - **Report as INFO**: "List shows 3 items vs. 8 in reference — composable uses `items(habits)` at `HabitListScreen.kt:55`, count is data-dependent."

3. **Visibility mismatch** — Reference shows an element that's absent on device:
   - Check for conditional rendering: `if (state.showX)`, `AnimatedVisibility`, `state.isLoading`.
   - **Report as INFO**: "Empty state illustration not shown — guarded by `if (habits.isEmpty())` at `HabitListScreen.kt:30`, currently has data."

4. **Size mismatch beyond tolerance** — Element significantly larger/smaller than reference:
   - Check if the composable uses `wrapContentSize`, `IntrinsicSize`, or sizes derived from content/data.
   - **Report as INFO** if size depends on content: "Card height 64dp vs. expected 96dp — uses `wrapContentHeight()`, height depends on text length."

### When NOT to check source code
- Text content mismatches (wrong string) — these are always real issues.
- Sibling order mismatches — layout order is code-determined, not data-dependent.
- Element type mismatches (Button vs. Text) — always a real issue.

---

## Step 5: Scrollable Content

When a UI Automator element has `scrollable="true"`:

1. **Verify visible content first** — run structural comparison on what's currently on screen.
2. **Calculate scroll bounds** from the scrollable element's `bounds`.
3. **Scroll slowly**:
   ```bash
   # Scroll down: swipe from bottom-center to top-center of the scrollable area
   adb shell input swipe <centerX> <bottom_80%> <centerX> <top_20%> 800
   ```
4. **Wait 500ms**, then re-dump the UI tree:
   ```bash
   sleep 0.5 && adb exec-out uiautomator dump /dev/tty
   ```
5. **Verify newly visible elements** against the reference.
6. **Detect end of scroll**: If two consecutive dumps show identical element text/resource-ids, the list is fully scrolled.
7. **Repeat** up to 20 scroll iterations (safety limit).
8. **Scroll back to top** when done:
   ```bash
   # Swipe down repeatedly to return to top
   adb shell input swipe <centerX> <top_20%> <centerX> <bottom_80%> 800
   ```

---

## Step 6: Navigation & Interaction

The calling agent provides the flow to verify (e.g., "tap Login, enter email 'test@test.com', tap Submit, verify Dashboard screen").

### Interaction commands

```bash
# Tap at center of target element
adb shell input tap <x> <y>

# Type text into focused field
adb shell input text "<text>"

# Special characters / spaces: use keyevents
adb shell input keyevent 62   # space
adb shell input keyevent 66   # enter

# Back button
adb shell input keyevent 4

# Swipe
adb shell input swipe <x1> <y1> <x2> <y2> <duration_ms>
```

### Interaction rules

1. **Before typing**: Dump UI tree and confirm the target field has `focused="true"`. If not, tap the field first, wait 300ms, re-dump, and verify focus.
2. **After every action**: Wait 500ms, then re-dump the UI tree to verify the transition.
3. **If a screen doesn't change after an action**: Retry once after 1s. If still unchanged, log it and continue.
4. **Scroll slowly**: Always use duration >= 500ms for swipes to avoid flinging past content.

---

## Step 7: Dynamic State Verification

### Loading → Content transitions
After navigating to a screen that loads data:
1. Dump UI tree immediately.
2. If loading indicators are present (ProgressBar, circular indicator, "Loading..." text), poll:
   ```bash
   sleep 1 && adb exec-out uiautomator dump /dev/tty
   ```
3. Repeat up to 5 times (5 seconds total wait).
4. If content still hasn't loaded after 5s, report as WARNING (not FAIL) — the backend may be slow.

### Error states
If the calling agent specifies error scenarios:
1. Trigger the error condition (e.g., enter invalid input, the calling agent should set up mock error responses)
2. Dump UI tree
3. Verify error message text matches the reference
4. Verify error UI structure (e.g., error icon + message in correct container)

### Empty states
If the calling agent specifies empty state verification:
1. Ensure the screen has no data loaded
2. Dump UI tree
3. Verify empty state elements (illustration, message text) match the reference

---

## Step 8: Report Structural Results

After all screens are verified structurally, output this JSON report:

```json
{
  "device": {
    "density": 420,
    "resolution": "1080x2400",
    "density_factor": 2.625
  },
  "screens": [
    {
      "name": "Screen Name",
      "reference_source": "figma://file/KEY?node=X:Y or path/to/file.html",
      "status": "PASS | PARTIAL | FAIL",
      "checks": [
        {
          "element": "Element description",
          "check": "What was compared (e.g., 'height', 'text content', 'presence')",
          "status": "PASS | FAIL | INFO",
          "expected": "Expected value",
          "actual": "Actual value",
          "delta_dp": null,
          "source_verified": "LazyColumn in HabitListScreen.kt:42 — not scrollable because item count fits viewport"
        }
      ],
      "warnings": [
        "Warning messages (unidentifiable elements, slow loads, etc.)"
      ]
    }
  ],
  "summary": {
    "screens_verified": 0,
    "passed": 0,
    "partial": 0,
    "failed": 0,
    "total_checks": 0,
    "checks_passed": 0,
    "checks_failed": 0,
    "checks_info": 0,
    "warnings": 0
  }
}
```

### Status definitions
- **PASS**: All structural checks passed within tolerance.
- **PARTIAL**: Structure matches but some sizing/spacing checks exceeded ±4dp tolerance.
- **FAIL**: Missing elements, wrong text, or broken hierarchy — confirmed as real bug after source code verification.
- **INFO**: Mismatch detected but source code verification confirmed it's data-dependent or expected behavior. Not a bug.

### After reporting structural results
- Continue to the next screen even if the current one fails — report ALL screens.
- **INFO checks do NOT count toward failure** — they are context, not problems.
- Do NOT attempt to fix code — only report findings.
- Proceed to Step 9 (Behavioral Verification) after structural checks are complete.

---

## Step 9: Behavioral Verification

After structural verification, **always** exercise the features that were built to verify they actually work. This step catches functional bugs that structural checks cannot detect.

### Deriving test flows

The calling agent knows what features were built. Based on that context, derive testable user flows. Common patterns:

| Feature type | Test flow |
|-------------|-----------|
| Create screen (form) | Fill all fields → tap save/submit → navigate to list → verify new item appears |
| List screen | Verify items display → tap an item → verify detail screen opens with correct data |
| Edit screen | Open existing item → change a field → save → verify change persists |
| Delete action | Trigger delete (swipe, long-press, button) → confirm → verify item is removed |
| Login/Auth | Enter credentials → submit → verify navigation to authenticated screen |
| Search/Filter | Enter search query → verify filtered results → clear → verify full list returns |
| Toggle/Switch | Tap toggle → verify state change → tap again → verify it reverts |

### Executing flows

For each test flow:

1. **Navigate to the starting screen** using the interaction commands from Step 6.
2. **Perform actions sequentially**:
   - Before typing: ensure field is focused (tap if needed, verify `focused="true"`)
   - Use recognizable test data: `"Test Item 12345"`, `"test@example.com"`, `"TestPassword123"`
   - After each action, wait 500ms and re-dump UI tree to verify the action took effect
3. **Verify the outcome**:
   - Re-dump the UI tree on the result screen
   - Search for the expected content (e.g., the created item's text in the list)
   - If the result requires navigation (e.g., back to list), navigate there first
4. **Handle async operations**:
   - If an action triggers a network call or database write, poll the UI tree (up to 5 attempts, 1s apart) until the expected result appears
   - If result doesn't appear after 5s, check source code — does the save logic require a backend that isn't running? Report as INFO if it's an environment issue, FAIL if the code is wrong.

### Ordering flows

If flows depend on each other, execute them in dependency order:
- Create before Edit (need an item to edit)
- Create before Delete (need an item to delete)
- If the app starts empty, Create flows run first

### Cleanup

After all flows complete:
- Attempt to delete test items if a delete mechanism exists
- If cleanup fails, that's OK — don't report cleanup failures

### Source code verification for behavioral failures

Apply the same Step 4b logic to behavioral failures:
- If "Save" doesn't navigate back → check if the ViewModel's save logic requires a backend call
- If a created item doesn't appear in the list → check if the list observes the same data source
- If a button tap does nothing → check if the click handler is wired up, or if it requires validation that wasn't met

### Behavioral report

Append to the same report JSON:

```json
{
  "behavioral": [
    {
      "flow": "Create a habit named 'Test Item 12345'",
      "steps": [
        {
          "action": "Tap 'Add Habit' FAB",
          "status": "PASS",
          "commands": ["adb shell input tap 540 2200"]
        },
        {
          "action": "Enter 'Test Item 12345' in name field",
          "status": "PASS",
          "commands": ["adb shell input tap 540 400", "adb shell input text 'Test Item 12345'"]
        },
        {
          "action": "Tap 'Save' button",
          "status": "PASS",
          "commands": ["adb shell input tap 540 1800"]
        },
        {
          "action": "Verify 'Test Item 12345' appears in habit list",
          "status": "PASS",
          "source_verified": null
        }
      ],
      "status": "PASS"
    }
  ],
  "behavioral_summary": {
    "flows_tested": 1,
    "flows_passed": 1,
    "flows_failed": 0,
    "flows_info": 0
  }
}
```

---

## Quick Reference: ADB Commands

| Action | Command |
|--------|---------|
| List devices | `adb devices` |
| Get density | `adb shell wm density` |
| Get resolution | `adb shell wm size` |
| UI dump | `adb exec-out uiautomator dump /dev/tty` |
| Tap | `adb shell input tap <x> <y>` |
| Type text | `adb shell input text "<text>"` |
| Swipe/scroll | `adb shell input swipe <x1> <y1> <x2> <y2> <ms>` |
| Back | `adb shell input keyevent 4` |
| Home | `adb shell input keyevent 3` |
| Enter | `adb shell input keyevent 66` |
| Space | `adb shell input keyevent 62` |
