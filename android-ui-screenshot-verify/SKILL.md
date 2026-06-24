---
name: android-ui-screenshot-verify
description: |
  Visually verify a single Android Compose screen against a Figma design using
  the Android CLI's annotated screenshot tools (`android screen capture --annotate`,
  `android screen resolve`). Catches overlap, clipping, truncation, color drift,
  wrong icon shape, broken contrast, and visual misalignment that the structural
  `android-ui-verify` skill cannot see. Single screen, single viewport, live
  device/emulator only. Reports a pass/fail verdict plus a lean issue list — does
  not edit code.
  Trigger on: "verify the screen visually", "screenshot verify against Figma",
  "annotated screenshot verify", "does it look right", "compare what I built to
  Figma visually", or after building a Compose screen from a Figma design when
  the calling agent wants visual (not structural) verification. For structural /
  hierarchy / dp-sizing checks, use `android-ui-verify` instead.
---

# Android UI Screenshot Verification

Verify a single running Compose screen against a Figma design using annotated
screenshots from the Android CLI. The calling agent invokes this skill after
implementing the screen and wants a *visual* sanity check — overlap, clipping,
color drift, wrong icon shape, misalignment — things that `uiautomator` XML
cannot see.

This skill **reports only**. It does not edit Compose code. The calling agent
revises the implementation based on the report and re-invokes if needed.

This skill **coexists with `android-ui-verify`**. They serve different purposes:

| | `android-ui-verify` | `android-ui-screenshot-verify` (this) |
|---|---|---|
| Mechanism | `uiautomator` XML dump | `android screen capture --annotate` + visual reasoning |
| Catches | Hierarchy, text, dp sizing, spacing | Overlap, clipping, colors, icon shape, alignment |
| Strengths | Structural, deterministic, dp tolerances | Visual, sees what XML can't |

---

## Prerequisites

The calling agent MUST provide:

1. **Figma URL with node ID** — the design to compare against.
2. **Navigation steps from current state** — natural-language list of taps,
   text entries, or key events to reach the target screen. May be empty if the
   app is already on the target screen.

The calling agent does NOT pass: a description of what was built, dynamic-content
notes, expected element list, or source files. The skill works from the Figma
design context plus what it sees on the device.

The environment MUST have:

- `android` CLI installed (`android --version` works).
- `adb` on PATH.
- Figma MCP server configured (the `mcp__plugin_figma_figma__get_design_context`
  tool must be callable).
- Exactly one device/emulator connected.
- The app launched on that device in some prior state.

The skill does NOT install, build, or launch the app.

---

## Step 1: Device check

```bash
adb devices
```

- **0 devices** — stop. Report: "No Android device connected. Connect a device
  or start an emulator and re-invoke."
- **2+ devices** — stop. Report: "Multiple devices connected: <list>. Pass a
  serial via the calling agent's input." Do NOT auto-pick.
- **1 device** — continue. All subsequent `adb` commands run against it without
  needing `-s`.

---

## Step 2: Fetch Figma design context

Parse the Figma URL to extract `fileKey` and `nodeId`:

- `figma.com/design/:fileKey/:fileName?node-id=:nodeId` → convert `-` to `:` in
  the nodeId.
- `figma.com/design/:fileKey/branch/:branchKey/:fileName` → use `branchKey` as
  the fileKey.

Call **`mcp__plugin_figma_figma__get_design_context`** with `fileKey` and
`nodeId`. Do NOT call `get_screenshot` — `get_design_context` is the source of
truth. Figma screenshots are lossy and add no information that the structured
context doesn't already carry.

From the response, build a mental checklist of what should be on the target
screen:

- Component hierarchy (parent → children nesting).
- Element types and any Code Connect mappings.
- Text content of every text node, exact strings.
- Frame dimensions (Figma logical px ≈ dp).
- Layout direction (row/column) and spacing between siblings.
- Colors / design tokens.
- Iconography (which icon, not just "an icon is here").

If the Figma MCP call fails or the URL is malformed, stop and report the error.

---

## Step 3: Navigate to target screen

Skip this step if the navigation list is empty.

For each navigation step:

### 3a. Capture the current state with annotation

```bash
android screen capture --annotate -o /tmp/uiverify-nav-<N>.png
```

Visually examine the resulting PNG. Each interactive element has a numbered
bounding box.

### 3b. Identify the target label

Read the step (e.g., "tap the Sign In button", "enter test@example.com in the
email field") and find which numbered label corresponds to it. Use the visible
text, position, and shape to disambiguate.

### 3c. Execute the interaction

- **Tap**:
  ```bash
  adb shell input $(android screen resolve --screen /tmp/uiverify-nav-<N>.png --string "tap #X")
  ```
  Replace `X` with the identified label number.

- **Text input**: tap the field first (as above). Then verify the field has
  `focused="true"` by running `android layout --pretty | grep -A2 focused` or by
  re-capturing and checking. Then:
  ```bash
  adb shell input text "<value>"
  ```
  For spaces use `adb shell input keyevent 62`. For enter use `keyevent 66`.

- **Back**: `adb shell input keyevent 4`.
- **Home**: `adb shell input keyevent 3`.
- **Swipe / scroll** (if explicitly part of the navigation steps):
  `adb shell input swipe <x1> <y1> <x2> <y2> 800`.

### 3d. Wait for UI to settle

```bash
sleep 0.5
```

before the next step.

### Failure handling

If a step cannot be executed — the target label is not on screen, the tap does
not change the screen after one settle, or the app crashes — **stop**. Capture
the current state:

```bash
android screen capture --annotate -o /tmp/uiverify-nav-failed.png
```

Return immediately with `Verdict: NAV_FAILED` (see Step 6). Do NOT auto-retry.
Do NOT continue to subsequent navigation steps.

---

## Step 4: Capture the target screen

```bash
android screen capture --annotate -o /tmp/uiverify-target.png
```

Visually examine the PNG.

### Annotate-failure fallback

Use the fallback if any of these is true:

- The command fails or produces an empty/0-byte file.
- The PNG opens but no numbered boxes are visible (e.g., the screen is a
  WebView, a custom Canvas-only view, or an animation in progress where
  `uiautomator` cannot resolve elements).
- The labels are so dense or overlapping that elements cannot be reliably
  identified.

Fallback commands:

```bash
android screen capture -o /tmp/uiverify-target-plain.png
android layout --pretty -o /tmp/uiverify-target-layout.json
```

Verification then reasons over the plain screenshot + the layout JSON together.
Element references in the report use either `text` content or `resourceId` from
the layout JSON instead of label numbers.

Do NOT auto-retry the annotated capture.

---

## Step 5: Compare against the Figma design context

Walk every element in the design context as a checklist. For each, look at the
annotated screenshot and decide whether it is present and correct. Check four
dimensions:

### 5a. Element presence + text content

- Every Figma element exists somewhere on the target screen.
- Every visible text string matches exactly (case-sensitive).
- Missing elements and wrong text are always real issues.

### 5b. Layout / arrangement / ordering

- Rows vs columns match the design's layout direction.
- Sibling order matches.
- Alignment within each parent matches (start / center / end / baseline).

### 5c. Visual sizing & spacing — proportional only

- Padding, margins, gaps, and element sizes look proportionally right.
- This is **not** pixel-perfect and **not** dp-tolerance comparison — that is
  what `android-ui-verify` is for.
- The bar is "obviously wrong to a human glancing at this". A button that looks
  ~20% too tall does not get reported. A button that takes up half the screen
  when it should be a chip does.

### 5d. Visual-only issues

These are the issues unique to this skill — XML cannot see them:

- Overlap between elements.
- Clipping (an element cut off by its parent's bounds).
- Text truncation / unintended ellipsis.
- Elements off-screen that should be visible.
- Broken / missing images.
- Wrong colors (background, text, button, border, icon tint).
- Wrong icon shape (chevron vs caret, filled vs outlined, wrong glyph).
- Broken contrast (text the same color as its background, etc.).

### Identification rule

When reporting an issue, reference the element by its label number from the
annotated screenshot, e.g. `"#7 (the Sign In button)"`. If the fallback was
used, reference by `text` or `resourceId` from the layout JSON instead.

### Precision over recall

When uncertain — annotation is ambiguous, element identity unclear, or the
mismatch could plausibly be intended — **stay silent**. The output must be
high-precision so the calling agent can trust every reported issue. False
positives waste a revision cycle and erode trust in the skill.

Note: data-dependent differences (a list shows 3 items vs. 8 in the design
because the test data has 3) are NOT issues. The calling agent already knows
what's data-dependent. Do not report list-count mismatches, dynamic timestamp
text, or counter values unless they reveal a structural bug (wrong template,
wrong format, etc.).

---

## Step 6: Report

Output exactly this format. Lean. No "all the things that passed" enumeration.

```
Verdict: PASS | ISSUES_FOUND | NAV_FAILED

Issues:
  - <issue 1, with element reference>
  - <issue 2, ...>

Evidence:
  - Annotated screenshot: /tmp/uiverify-target.png
  - (if fallback used) Plain screenshot: /tmp/uiverify-target-plain.png
  - (if fallback used) Layout JSON: /tmp/uiverify-target-layout.json
  - (if NAV_FAILED) Failure-state screenshot: /tmp/uiverify-nav-failed.png
  - Figma reference: <original URL>
```

### Verdict definitions

- **PASS** — checklist walked, no issues found. `Issues:` is empty.
- **ISSUES_FOUND** — one or more confirmed issues. List each one.
- **NAV_FAILED** — could not reach the target screen. `Issues:` describes which
  step failed (verbatim) and what was on screen instead.

### Issue writing style

- Reference the labeled element: `"#7 overlaps #9 (the Save button is on top of the Cancel button)"`.
- Be specific about what is wrong, not just that something is wrong:
  ✅ `"#3 (Continue button) text is white on a white background — invisible"`
  ❌ `"button has wrong color"`
- One issue per bullet. Group related issues only if they share a single root
  cause (e.g., "all four #4–#7 list items have their leading icon clipped").

---

## Quick reference

| Step | Command |
|---|---|
| Check devices | `adb devices` |
| Get Figma context | Figma MCP `get_design_context(fileKey, nodeId)` |
| Annotated screenshot | `android screen capture --annotate -o <path>` |
| Resolve label to coords | `android screen resolve --screen <path> --string "tap #N"` |
| Tap | `adb shell input tap <x> <y>` (or piped from `screen resolve`) |
| Type text | `adb shell input text "<value>"` |
| Back / Home / Enter / Space | `adb shell input keyevent 4 / 3 / 66 / 62` |
| Plain screenshot fallback | `android screen capture -o <path>` |
| Layout JSON fallback | `android layout --pretty -o <path>` |
| Settle | `sleep 0.5` |

## What this skill is not

- Not a screenshot-testing framework. No baselines, no PNG-diffing, no
  Paparazzi/Roborazzi. The "test" is the live Figma design.
- Not pixel-perfect. The bar is "obviously wrong to a human".
- Not a code fixer. Reports only.
- Not preview-capable. Live device only.
- Not multi-screen. One screen per invocation.
- Not a navigator. Navigation steps come from the calling agent verbatim.
