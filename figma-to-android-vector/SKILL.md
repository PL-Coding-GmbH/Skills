---
name: figma-to-android-vector
description: |
  SVG to Android VectorDrawable XML and Compose ImageVector conversion — faithful, mechanical transformation of SVG path data into Android-native vector formats. Use this skill whenever creating vector drawables from Figma designs, converting SVG icons to Android XML, generating ImageVector code from SVG, or implementing any icon from a Figma design system. This skill is critical because Claude tends to hallucinate vector paths instead of using actual SVG data — it prevents that failure mode.
  Trigger on phrases like "vector drawable", "SVG to Android", "icon from Figma", "create icon", "vector icon", "ImageVector", "pathData", "drawable XML", "convert SVG", "Figma icon", "export icon", "icon drawable", "vector XML", "android icon", "convert icon", "icon asset", "VectorDrawable", or any task involving creating Android vector files from design tool exports.
---

# SVG to Android Vector Conversion

## The #1 Rule

**NEVER invent, hallucinate, simplify, or approximate SVG path data.**

The `d` attribute from the source SVG must be copied **verbatim** into `android:pathData` (or the Compose `pathData` string). If you do not have the actual SVG source code, you **must** obtain it before creating any vector — do not attempt to recreate an icon from a screenshot, description, or memory.

Why this matters: the most common failure mode is ignoring the real SVG path data and generating a generic shape (like a circle) instead of the actual icon. This produces visually wrong icons that look nothing like the design.

---

## Getting SVG Data from Figma

When working with Figma MCP:

1. **Always request the SVG asset** — Figma MCP serves SVG files via localhost URLs. Fetch these URLs to get the actual SVG code with real path data.
2. **Do not rely on screenshots alone** — screenshots show what the icon looks like but contain no path data. You need the SVG source.
3. **Do not rely on icon names or descriptions** — knowing an icon is called "checkmark" does not give you the path data. Fetch the SVG.
4. If the SVG source is truly unavailable, tell the user you need the SVG code and suggest they export it from Figma manually.

---

## SVG to Android XML VectorDrawable

### Attribute Mapping

| SVG | Android VectorDrawable | Notes |
|-----|----------------------|-------|
| `viewBox="0 0 W H"` | `android:viewportWidth="W"` / `android:viewportHeight="H"` | Use the viewBox values, not width/height |
| `width` / `height` | `android:width="Xdp"` / `android:height="Ydp"` | Derive from SVG `viewBox` aspect ratio — scale longest side to 24dp, compute the other proportionally. Do NOT blindly use Figma frame size (often square padding around a non-square icon). See **Dimension Handling** below. |
| `<path d="...">` | `android:pathData="..."` | **Copy the `d` value VERBATIM** |
| `fill="#RRGGBB"` | `android:fillColor="#RRGGBB"` | |
| `fill="none"` | Omit `fillColor` entirely, or use `#00000000` | Do NOT convert to `fillColor="#000000"` |
| `stroke="#RRGGBB"` | `android:strokeColor="#RRGGBB"` | Do NOT use `fillColor` for stroke-based icons |
| `stroke-width="X"` | `android:strokeWidth="X"` | |
| `stroke-linecap="round"` | `android:strokeLineCap="round"` | Values: `butt`, `round`, `square` |
| `stroke-linejoin="round"` | `android:strokeLineJoin="round"` | Values: `miter`, `round`, `bevel` |
| `stroke-miterlimit="X"` | `android:strokeMiterLimit="X"` | |
| `opacity="X"` | `android:alpha="X"` | |
| `fill-opacity="X"` | `android:fillAlpha="X"` | |
| `stroke-opacity="X"` | `android:strokeAlpha="X"` | |
| `fill-rule="evenodd"` | `android:fillType="evenOdd"` | Default is `nonZero`; getting this wrong breaks complex shapes with holes |

### Stroke vs Fill — Critical Distinction

Many icons (especially line icons from Figma) are **stroke-based**, meaning they use `stroke` with `fill="none"`. These must become `strokeColor` in Android, NOT `fillColor`. Check the SVG source:

- If `fill="none"` and `stroke="..."` → use `android:strokeColor`, `android:strokeWidth`, and omit `fillColor`
- If `fill="..."` and no `stroke` → use `android:fillColor`
- If both `fill` and `stroke` are present → use both `android:fillColor` and `android:strokeColor`

### Dimension Handling — Preserving Aspect Ratio

Android `width`/`height` (in dp) control the rendered size. These **must** preserve the source icon's actual aspect ratio.

**Figma frame vs actual icon dimensions:**
Figma often wraps icons in a square bounding frame (e.g., 24×24) for alignment/grid purposes, but the actual icon artwork inside may be non-square (e.g., a 16×11 checkmark inside a 24×24 frame). The SVG `viewBox` reflects the actual icon geometry — **use the `viewBox` as the source of truth for aspect ratio**, not the Figma frame size or the SVG `width`/`height` attributes (which may reflect the frame).

**Deriving dp dimensions:**
1. Read the SVG `viewBox` width and height (e.g., `viewBox="0 0 16 11"` → W=16, H=11).
2. Scale the **longest** viewBox dimension to 24dp. Compute the other proportionally.
   - Example: longest=16, scale=24÷16=1.5 → `width="24dp"`, `height="16.5dp"` (11×1.5).
3. Square viewBox → 24×24dp is fine.
4. If the SVG `width`/`height` attributes differ from the viewBox (common with Figma exports that include frame padding), **prefer the viewBox**.

**Never** default both dimensions to 24dp for a non-square icon. This stretches or squashes the graphic.

Note: `viewportWidth`/`viewportHeight` always come from the SVG `viewBox` — they define the coordinate system and are unrelated to dp sizing.

### Conversion Template

```xml
<!-- Input SVG -->
<svg width="16" height="11" viewBox="0 0 16 11" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0.749999 4.93327L5.72133 9.90469L14.876 0.75"
          stroke="black" stroke-width="1.5"
          stroke-linecap="round" stroke-linejoin="round"/>
</svg>

<!-- Correct Android VectorDrawable -->
<!-- viewBox is 16x11 (non-square). Longest side 16 → 24dp. Height = 11 × (24/16) = 16.5dp -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="16.5dp"
    android:viewportWidth="16"
    android:viewportHeight="11">
    <path
        android:pathData="M0.749999,4.93327L5.72133,9.90469L14.876,0.75"
        android:strokeColor="#000000"
        android:strokeWidth="1.5"
        android:strokeLineCap="round"
        android:strokeLineJoin="round"/>
</vector>

<!-- WRONG — what Claude often produces instead -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#000000"
        android:pathData="M12,12m-8,0a8,8 0,1 1,16 0a8,8 0,1 1,-16 0"/>
</vector>
<!-- This is a filled circle — completely wrong! The path data was hallucinated
     and the stroke was incorrectly converted to fill. -->
```

### pathData Syntax Note

SVG `d` and Android `pathData` use the same path command syntax (M, L, C, A, Z, etc.). The only formatting difference: Android separates coordinate pairs with commas. So `M0.75 4.93L5.72 9.90` becomes `M0.75,4.93L5.72,9.90`. Both forms are actually valid in Android, but comma-separated is conventional.

---

## SVG Special Cases

### Shape Elements

Android VectorDrawable only supports `<path>` — no `<circle>`, `<rect>`, `<ellipse>`, `<line>`, `<polygon>`, or `<polyline>`. Convert them:

| SVG Element | Path Equivalent |
|---|---|
| `<circle cx="X" cy="Y" r="R"/>` | `M(X-R),Y A R,R 0 1,1 (X+R),Y A R,R 0 1,1 (X-R),Y Z` |
| `<rect x="X" y="Y" width="W" height="H"/>` | `M X,Y L (X+W),Y L (X+W),(Y+H) L X,(Y+H) Z` |
| `<rect ... rx="R" ry="R"/>` | Use arc commands for rounded corners |
| `<ellipse cx="X" cy="Y" rx="RX" ry="RY"/>` | `M(X-RX),Y A RX,RY 0 1,1 (X+RX),Y A RX,RY 0 1,1 (X-RX),Y Z` |
| `<line x1="X1" y1="Y1" x2="X2" y2="Y2"/>` | `M X1,Y1 L X2,Y2` |
| `<polygon points="x1,y1 x2,y2 ..."/>` | `M x1,y1 L x2,y2 L ... Z` |
| `<polyline points="x1,y1 x2,y2 ..."/>` | `M x1,y1 L x2,y2 L ...` (no Z) |

Compute the actual numeric values — do not leave expressions like `(X+R)` in the pathData.

### Groups and Transforms

SVG `<g transform="...">` maps to Android `<group>`:

```xml
<!-- SVG -->
<g transform="translate(4, 4) rotate(45) scale(0.5)">
    <path d="M0,0 L10,10"/>
</g>

<!-- Android -->
<group
    android:translateX="4"
    android:translateY="4"
    android:rotation="45"
    android:scaleX="0.5"
    android:scaleY="0.5">
    <path android:pathData="M0,0 L10,10"/>
</group>
```

If the SVG has a `transform` directly on a `<path>`, wrap it in a `<group>` with the transform attributes.

### Non-Zero viewBox Origin

If `viewBox="X Y W H"` where X or Y are not zero, translate all paths by (-X, -Y) or wrap everything in a group:

```xml
<!-- SVG with viewBox="5 5 24 24" -->
<!-- Android: use viewport 24x24, wrap in a translating group -->
<vector android:viewportWidth="24" android:viewportHeight="24" ...>
    <group android:translateX="-5" android:translateY="-5">
        <!-- paths with original coordinates -->
    </group>
</vector>
```

### CSS Styles and Classes

Figma SVG exports sometimes use `<style>` blocks or class attributes instead of inline attributes. Resolve these to inline Android attributes:

```xml
<!-- SVG with CSS class -->
<style>.cls-1 { fill: #FF5722; stroke: #333; stroke-width: 2; }</style>
<path class="cls-1" d="M10,20 L30,40"/>

<!-- Android: resolve the class to inline attributes -->
<path
    android:pathData="M10,20 L30,40"
    android:fillColor="#FF5722"
    android:strokeColor="#333333"
    android:strokeWidth="2"/>
```

### Defs, Use, and Symbol

SVG `<defs>`, `<use>`, and `<symbol>` reference reusable elements. Android has no equivalent — inline/expand every reference:

```xml
<!-- SVG with <use> -->
<defs>
    <path id="arrow" d="M0,0 L10,5 L0,10"/>
</defs>
<use href="#arrow" x="20" y="20"/>

<!-- Android: inline the referenced path, apply the x/y as a group translate -->
<group android:translateX="20" android:translateY="20">
    <path android:pathData="M0,0 L10,5 L0,10"/>
</group>
```

### Gradients

SVG gradients map to Android `<gradient>` (API 24+):

```xml
<!-- SVG -->
<linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%">
    <stop offset="0%" stop-color="#FF0000"/>
    <stop offset="100%" stop-color="#0000FF"/>
</linearGradient>
<path fill="url(#grad)" d="M0,0 L100,0 L100,100 L0,100 Z"/>

<!-- Android (API 24+) -->
<path android:pathData="M0,0 L100,0 L100,100 L0,100 Z">
    <aapt:attr name="android:fillColor">
        <gradient
            android:type="linear"
            android:startX="0" android:startY="0"
            android:endX="100" android:endY="0">
            <item android:offset="0.0" android:color="#FFFF0000"/>
            <item android:offset="1.0" android:color="#FF0000FF"/>
        </gradient>
    </aapt:attr>
</path>
```

Note: gradient colors require ARGB format (`#AARRGGBB`).

### Clip Paths

SVG `<clipPath>` maps to Android `<clip-path>`:

```xml
<!-- SVG -->
<clipPath id="clip">
    <circle cx="50" cy="50" r="40"/>
</clipPath>
<g clip-path="url(#clip)">
    <path d="..."/>
</g>

<!-- Android -->
<group>
    <clip-path android:pathData="M10,50 A40,40 0 1,1 90,50 A40,40 0 1,1 10,50 Z"/>
    <path android:pathData="..."/>
</group>
```

Convert the clip shape to a path (same shape-to-path rules as above).

### Multi-Color Icons

Each SVG `<path>` with different colors becomes a separate `<path>` in the Android `<vector>`. Preserve every path with its own color attributes:

```xml
<!-- SVG with multiple colored paths -->
<path d="M10,10 L20,20" fill="#FF0000"/>
<path d="M30,30 L40,40" fill="#0000FF"/>

<!-- Android: each path keeps its own color -->
<path android:pathData="M10,10 L20,20" android:fillColor="#FF0000"/>
<path android:pathData="M30,30 L40,40" android:fillColor="#0000FF"/>
```

Do NOT merge paths or flatten colors.

### Unsupported SVG Features

These SVG features have **no VectorDrawable equivalent**: `<filter>`, `<mask>`, `<pattern>`, `<text>`, `<foreignObject>`, CSS `blur()`, `drop-shadow()`.

If the SVG relies on these, warn the user and suggest either:
- Rasterizing the icon to PNG/WebP instead
- Simplifying the SVG in the design tool to avoid these features
- Using a different approach (e.g., Compose Canvas for complex rendering)

### currentColor

SVG `currentColor` must be resolved. In Android tinted icons, use a placeholder color and apply tinting:

```xml
<!-- Use black as placeholder, tint at usage -->
<path android:fillColor="#000000" android:pathData="..."/>
```

Then in Compose: `Icon(painter = painterResource(R.drawable.ic_icon), tint = MaterialTheme.colorScheme.primary)`

---

## SVG to Compose ImageVector

The same conversion rules apply. Use `ImageVector.Builder`:

```kotlin
val CheckIcon: ImageVector
    get() {
        if (_checkIcon != null) return _checkIcon!!
        _checkIcon = ImageVector.Builder(
            name = "Check",
            defaultWidth = 24.dp,
            defaultHeight = 16.5.dp,  // viewBox 16x11 → 24dp × 16.5dp
            viewportWidth = 16f,
            viewportHeight = 11f
        ).apply {
            path(
                stroke = SolidColor(Color.Black),
                strokeLineWidth = 1.5f,
                strokeLineCap = StrokeCap.Round,
                strokeLineJoin = StrokeJoin.Round
            ) {
                // Verbatim from SVG: d="M0.749999 4.93327L5.72133 9.90469L14.876 0.75"
                moveTo(0.749999f, 4.93327f)
                lineTo(5.72133f, 9.90469f)
                lineTo(14.876f, 0.75f)
            }
        }.build()
        return _checkIcon!!
    }

private var _checkIcon: ImageVector? = null
```

### Key Compose Mappings

| SVG / Android XML | Compose ImageVector |
|---|---|
| `fill` / `fillColor` | `fill = SolidColor(Color(...))` |
| `stroke` / `strokeColor` | `stroke = SolidColor(Color(...))` |
| `fill="none"` | `fill = null` (omit the parameter) |
| `stroke-width` / `strokeWidth` | `strokeLineWidth = Xf` |
| `stroke-linecap` / `strokeLineCap` | `strokeLineCap = StrokeCap.Round` |
| `stroke-linejoin` / `strokeLineJoin` | `strokeLineJoin = StrokeJoin.Round` |
| `fill-rule="evenodd"` / `fillType="evenOdd"` | `pathFillType = PathFillType.EvenOdd` |
| `<group>` | `group { ... }` |
| `<clip-path>` | `clipPathData = ...` in group |

### Path Commands Mapping

| SVG Command | Compose Builder Method |
|---|---|
| `M x,y` | `moveTo(x, y)` |
| `m dx,dy` | `moveToRelative(dx, dy)` |
| `L x,y` | `lineTo(x, y)` |
| `l dx,dy` | `lineToRelative(dx, dy)` |
| `H x` | `horizontalLineTo(x)` |
| `h dx` | `horizontalLineToRelative(dx)` |
| `V y` | `verticalLineTo(y)` |
| `v dy` | `verticalLineToRelative(dy)` |
| `C x1,y1 x2,y2 x,y` | `curveTo(x1, y1, x2, y2, x, y)` |
| `c ...` | `curveToRelative(...)` |
| `S x2,y2 x,y` | `reflectiveCurveTo(x2, y2, x, y)` |
| `Q x1,y1 x,y` | `quadTo(x1, y1, x, y)` |
| `A rx,ry rot large,sweep x,y` | `arcTo(rx, ry, rot, largeArc, sweep, x, y)` |
| `Z` | `close()` |

Parse the `d` attribute command by command and call the corresponding builder method with the exact numeric values from the SVG.

---

## Conversion Checklist

For every icon conversion, verify:

- [ ] Path data is copied verbatim from the SVG `d` attribute — not invented
- [ ] `viewportWidth`/`viewportHeight` match the SVG `viewBox` dimensions
- [ ] Stroke-based icons use `strokeColor`, not `fillColor`
- [ ] `fill="none"` is not converted to `fillColor="#000000"`
- [ ] `stroke-width`, `stroke-linecap`, `stroke-linejoin` are preserved
- [ ] `fill-rule="evenodd"` is mapped to `fillType="evenOdd"` when present
- [ ] Shape elements (`<circle>`, `<rect>`, etc.) are converted to path commands with computed values
- [ ] Groups and transforms are preserved
- [ ] Multi-color paths each keep their own color attributes
- [ ] CSS styles/classes are resolved to inline attributes
- [ ] `<use>`/`<defs>` references are inlined
- [ ] `width`/`height` (dp) preserve the actual icon aspect ratio from the `viewBox` — not forced square from a Figma bounding frame
