---
name: android-preview-figma-verify
description: |
  Compare a single rendered Compose @Preview against a single Figma frame and
  report the visual/structural differences back to the calling agent as a
  severity-graded issue list. NO device or emulator needed — it renders the
  preview straight from Android Studio via the android CLI's
  `render-compose-preview`, so it works on any @Preview, including landscape,
  tablet, and per-state previews. The calling agent supplies BOTH the exact
  preview (file + composable name) AND the exact Figma frame (URL with node-id);
  this skill never guesses the pairing. Treats Figma as the single source of
  truth. Reports only — it never edits code.
  Use this skill whenever the caller wants to check a Compose preview against a
  design WITHOUT running the app: "compare this preview to Figma", "verify
  <SomethingPreview> against node-id ...", "does this preview match the design",
  "render the preview and diff it against Figma", "check my Compose preview
  against the mockup", or after building/changing a screen when there's a Figma
  frame to validate against and no device is connected. For a check against a
  LIVE running screen on a device/emulator, use android-ui-screenshot-verify
  (visual) or android-ui-verify (structural/uiautomator) instead.
---

# Compose Preview ↔ Figma Frame Verification

Render one Compose `@Preview` to an image, fetch one Figma frame, and report the
differences as a severity-graded list. The calling agent fixes the code and
re-invokes if needed. **This skill reports only — it never edits Compose code.**

The whole point is to catch design drift *before* the app is even built or
deployed. Because it renders previews directly from Android Studio, it can check
states that are awkward to reach on a device (error callouts, empty states,
specific multi-select selections, landscape, tablet) — each gets its own
`@Preview`, and the caller points this skill at the exact one.

## How this differs from the sibling skills

| | This skill | `android-ui-screenshot-verify` | `android-ui-verify` |
|---|---|---|---|
| Source | Rendered `@Preview` image | Live device screenshot | Live device uiautomator XML |
| Needs a device | **No** | Yes | Yes |
| Catches | Text, color, icon, spacing, radius, structure | Overlap, clipping, color, icon | Hierarchy, text, dp sizing |

Pick this skill when there is no running app — just source code, a preview, and a
Figma frame.

## The hallucination risk this skill is built to avoid

If you compare the *wrong* preview against the *wrong* frame, or compare a
preview whose state doesn't match the frame's state, every "difference" you
report is noise that sends the calling agent chasing phantom bugs. Two
safeguards exist for this:

1. **The caller chooses the pairing.** This skill does not search the codebase
   for a matching preview or browse Figma for a matching frame. It takes exactly
   what it's given. If the inputs are wrong, that's the caller's call to fix.
2. **The state-match gate (below).** Before reporting a single finding, confirm
   the preview actually renders the *same state* the frame depicts. A frame
   showing "3 of 6 items selected" must be compared against a preview that
   selects those same 3 items — otherwise the selection differences are state
   noise, not defects.

## Inputs (required from the calling agent)

The caller MUST provide both halves of the pairing:

1. **Compose preview** — the file path **and** the `@Preview` composable function
   name, e.g.
   `feature/auth/.../signin/SignInScreen.kt` + `SignInScreenWrongCredentialsCalloutPreview`.
2. **Figma frame** — a Figma URL containing a `node-id`, e.g.
   `https://www.figma.com/design/<fileKey>/Foldio?node-id=1-857`. Extract
   `fileKey` and `nodeId` from it (`node-id=1-857` → nodeId `1:857`).

If either half is missing, stop and ask the caller for it. Do not guess.

## Step 0 — Prerequisite gate

Confirm the environment can do the job before doing anything else. If a check
fails, stop and report exactly what's missing — don't limp forward.

1. **android CLI with preview rendering.** Run `android studio check`. If the
   `android` command is missing, tell the user: *"This skill needs the
   `android-cli` skill (the `android` command-line tool). Install it, then
   re-invoke."* The specific capability used is
   `android studio render-compose-preview` — if `android --help` / `android
   studio --help` doesn't list it, the CLI is too old: tell the user to run
   `android update`.
2. **Android Studio is running with the project open.** `android studio check`
   lists open projects and their status. The target project must appear and be
   `READY`. If no Studio instance is running or the project isn't open, tell the
   user to open the project in Android Studio and wait for indexing to finish.
3. **Unique project name.** `render-compose-preview` selects the project by
   **name** via `--project=<name>`, and a *path* is rejected. If two open
   projects share the same name (this really happens — e.g. two "Foldio"
   projects open at once), every `--project` value fails with
   `No project with name ...`. If `android studio check` shows duplicate names,
   stop and ask the user to close all but the intended one, then re-invoke.
4. **Figma MCP reachable.** The `mcp__plugin_figma_figma__get_design_context`
   tool must be callable. If not, tell the user to connect the Figma MCP server.

## Step 1 — Render the preview (image + semantics)

Render the exact composable the caller named, capturing both the image and the
semantics tree:

```bash
android studio render-compose-preview \
  <file-path> \
  <ComposableName> \
  --project=<ProjectName> \
  --output-image-file=/tmp/preview-figma/<ComposableName>.png \
  --print-semantics
```

- `--output-image-file` is what you'll look at visually.
- `--print-semantics` prints the rendered view tree **with the actual rendered
  text and bounds**. This is gold: it tells you what state the preview is truly
  in (which labels, which values, which items), which drives the state-match
  gate. Capture and keep it.

Then read the PNG so you can see it.

## Step 2 — Fetch the Figma frame

```
mcp__plugin_figma_figma__get_design_context(nodeId=<nodeId>, fileKey=<fileKey>)
```

This returns the frame screenshot plus structured code carrying the ground-truth
values you'll compare against: exact text strings, hex colors, font
weight/size, border radii, spacing, and Material Symbol icon names (e.g.
`folder_open`, `mark_email_read`). For design tokens, also call
`get_variable_defs`. For a higher-resolution image, call `get_screenshot` with a
larger `maxDimension`.

## Step 3 — State-match gate (warn but proceed)

Before comparing appearance, confirm the two artifacts depict the **same state**.
Diff the rendered semantics text-set (from Step 1) against the frame's text and
visible state (from Step 2), and for selection/toggle states verify the *same
specific items* are in the same condition.

- **States match** → proceed to the full comparison.
- **States diverge** → still proceed, but:
  - Put a prominent **STATE MISMATCH** warning at the very top of the report,
    listing each specific divergence (e.g. "frame shows 3 of 6 list rows
    selected; preview selects 0").
  - **Exclude from the findings any difference that is explained by the state
    divergence.** A row that looks different only because it's selected in the
    frame and not in the preview is not a design defect — reporting it as one is
    exactly the hallucination this skill exists to prevent.

This is "warn but proceed," but *state-aware*: the comparison continues, yet
state-caused differences never get graded as defects.

## Step 4 — Compare

Compare the rendered preview against the Figma frame. **Figma is the single
source of truth** — if the implementation diverges, that's a finding, even when
the implementation's choice seems reasonable. (Whether to actually change the
code is the caller's decision; your job is to report faithfully.)

### Always ignore (never a finding)

- **System / platform UI** — status bar, notch, navigation bar, and especially
  the **iOS home indicator** (Figma frames are often iOS-sized; you're rendering
  Android). The frame may have a "Home Indicator" node — skip it.
- **Text-masking artifacts** — the number of password bullet dots, caret/cursor.
- **Anything excluded by the state-match gate** (Step 3).

### Focus areas, in priority order

1. **Text labels** — exact string comparison. Highest signal; cheap and
   unambiguous.
2. **Colors** — compare hex values; allow a small perceptual tolerance for
   near-identical shades.
3. **Icons** — the right glyph/symbol is used and has the right shape.
4. **Spacing / sizing / position** — allow tolerance (≈ ±8dp, and judge
   *proportionally* in landscape/tablet where the layout reflows rather than
   scales 1:1). Only flag deviations beyond tolerance.
5. **Border radii** — allow tolerance; flag clear shape changes.

## Severity rubric

Grade every finding by one question: **what does this difference do to the
person using the screen?** This keeps grading reproducible — two runs over the
same diff should land on the same severity.

- **BLOCKER** — changes *function or meaning*, or *removes/hides* content or an
  affordance, or it's the wrong screen entirely. Examples: a missing primary
  button or input; text clipped so content is hidden; a wrong icon glyph or a
  wrong label that changes *what an action does* (a trash icon where the design
  has archive; a button reading "Delete" where the design says "Save").
- **MAJOR** — clearly wrong content or appearance that a designer would reject,
  but the screen is still usable. Examples: an **extra or missing element**
  (icon, divider, badge — decorative or not; present-vs-absent is always at
  least MAJOR); a wrong label whose meaning is *preserved* ("PASSPHRASE" where
  the design says "PASSWORD"); a wrong glyph that doesn't change the action's
  meaning; a wrong color on a prominent element beyond tolerance; wrong font
  family or a bold↔regular weight flip on prominent text; a **state/behavioral
  deviation from the frame** (e.g. a button rendered disabled/gray where the
  frame shows it enabled/blue, or an item shown unselected where the frame
  selects it — Figma is the source of truth, so this is a defect to report);
  spacing/alignment beyond tolerance that causes overlap, clipping, or
  misalignment.
- **MINOR** — subtle, cosmetic deviation near tolerance: small color/tint,
  spacing, size, weight, or border-radius differences that don't break the
  layout; pure typographic punctuation (straight vs curly quotes, en-dash vs
  hyphen, a stray trailing period).
- **Not reported** — within tolerance, system/platform UI, masking artifacts, or
  excluded by the state-match gate.

## Report format

Return this to the calling agent. Be high-signal: lead with the verdict, list
findings grouped by severity, and make each finding actionable.

```
# Preview ↔ Figma verification

Preview: <ComposableName>  (<file path>)
Figma:   node <nodeId>  (<frame name>)

## State match
<✓ states match  |  ⚠ STATE MISMATCH — list each divergence; note that
state-caused differences were excluded from findings below>

## Verdict
<PASS — no BLOCKER/MAJOR findings  |  N finding(s): X BLOCKER, Y MAJOR, Z MINOR>

## Findings
- [BLOCKER] <category> — Figma <value> (node <id>) vs rendered <value>. Fix: <concrete change>
- [MAJOR]   <category> — Figma <value> (node <id>) vs rendered <value>. Fix: <concrete change>
- [MINOR]   <category> — Figma <value> (node <id>) vs rendered <value>. Fix: <concrete change>

## Verified matching
<short bullet list of the important things that DID match — so the caller knows
the comparison was thorough, not that you simply stopped early>
```

When nothing beyond tolerance differs, say so plainly: a **PASS** with a
"Verified matching" list is a valid and valuable result. Do not manufacture
findings to look thorough.

## Worked examples

These are real comparisons from the Foldio app, illustrating each grade.

**Example 1 — `SignInScreenWrongCredentialsCalloutPreview` vs node `1:857`** (state matched):

- `[MAJOR] text` — Figma label "PASSWORD" (node `1:890`) vs rendered "PASSPHRASE". Meaning preserved → MAJOR, not BLOCKER. Fix: align the label string with the design (or confirm the design should adopt the app's terminology).
- `[MAJOR] element` — error callout: Figma has text + a trailing close `X` only (node `1:873`); rendered adds a leading `(!)` icon. Extra element → MAJOR. Fix: remove the leading icon.
- `[MAJOR] element` — password field: Figma shows only `visibility_off` (node `1:892`); rendered adds a trailing red `(!)` icon. Extra element → MAJOR. Fix: remove the error icon from the field.
- `[MAJOR] state` — Figma Sign In button is enabled/blue `#4f8ef7` (node `1:899`); rendered is disabled/gray. State deviation from the source of truth → MAJOR. Fix: keep the button enabled in this state to match the design.

Note both extra-icon findings are MAJOR via the *same* rule ("element present in
render, absent in Figma"). Grading the leading icon and the trailing icon
differently would be exactly the kind of inconsistency this rubric prevents.

**Example 2 — `OnboardingScreenPage1Preview` vs node `1:726`** (state matched):

- **Verdict: PASS.** Text, all elements (Skip, 3 file cards, glow, 3 device
  icons + connectors, 3-dot page indicator, title, subtitle, Next button),
  colors, icons, and stacking order all matched. The only sub-MINOR observation
  (device-icon connectors render as dashes vs the frame's dotted asset) is within
  tolerance and was not reported. A clean PASS is the correct output here.
