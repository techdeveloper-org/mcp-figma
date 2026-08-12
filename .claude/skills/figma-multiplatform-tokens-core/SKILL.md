---
name: figma-multiplatform-tokens-core
description: "Provides complete multi-platform design token deployment mathematics — Android dp/sp density math, iOS pt scaling, CSS rem conversion, P3/OKLCH wide-gamut color transforms, fluid typography derivation, cubic-bezier animation easing, dark mode alias resolution, and multi-target pipeline cost modeling. Use when deploying design tokens from a single DTCG source to CSS, Android XML, iOS Swift/Xcode Color Assets, and Compose simultaneously. Keywords: design tokens android ios css, multi-platform token deployment, figma tokens android dp sp, dark mode design tokens, figma oklch p3 color tokens, fluid typography tokens, animation easing tokens"
allowed-tools: Read,Glob,Grep,Bash,Edit,Write
user-invocable: true
---


<!-- generated-by: claude-global-library/tools/project_sync -->
<!-- source: skills/figma-multiplatform-tokens-core/SKILL.md -- edit the library, then re-run sync_project.py -->

# figma-multiplatform-tokens-core

## Description

Complete multi-platform design token deployment mathematics. Covers Android dp/sp density math, iOS pt point scaling and Xcode Color Assets, CSS rem/px conversion, Display P3/OKLCH wide-gamut color transforms, fluid typography clamp derivation, cubic-bezier animation easing parametric form, dark mode alias resolution algebra, and Style Dictionary v4 multi-target pipeline cost modeling.

## 1. W3C DTCG Multi-Platform Transform Architecture

**Single source of truth:** One DTCG-format token file set. All platforms receive tokens from the same source, transformed by Style Dictionary v4.

**Platform output files:**
| Platform | Output Files |
|----------|-------------|
| CSS | `dist/css/variables.css` (custom properties) |
| SCSS | `dist/scss/_variables.scss` |
| JavaScript | `dist/js/tokens.mjs` (ES module) |
| Android | `dist/android/res/values/colors.xml`, `values/dimens.xml` |
| iOS | `dist/ios/TokenColors.xcassets/` + `TokenStyles.swift` |
| Compose | `dist/compose/TokenStyles.kt` |

**Atomic deployment principle:** All platform outputs updated together or none. If Android XML generation fails, roll back the entire pipeline run — do not ship inconsistent platform states.

**Style Dictionary v4 multi-platform config:**
```javascript
export default {
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/css/',
      files: [{ destination: 'variables.css', format: 'css/variables' }],
    },
    android: {
      transformGroup: 'android',
      buildPath: 'dist/android/res/values/',
      files: [
        { destination: 'colors.xml', format: 'android/colors' },
        { destination: 'dimens.xml', format: 'android/dimens' },
      ],
    },
    ios: {
      transformGroup: 'ios-swift',
      buildPath: 'dist/ios/',
      files: [{ destination: 'TokenStyles.swift', format: 'ios-swift/class.swift' }],
    },
    compose: {
      transformGroup: 'compose',
      buildPath: 'dist/compose/',
      files: [{ destination: 'TokenStyles.kt', format: 'compose/object' }],
    },
  },
};
```

**Token Transformer (Tokens Studio) integration:** Runs before Style Dictionary as a pre-processing step:
```bash
npx token-transformer tokens/figma-export.json tokens/dtcg-format.json
npx style-dictionary build --config sd.config.js
```

## 2. Android Density and Accessibility Units

**Screen density model:**
| Density Bucket | Dots Per Inch | Scale Multiplier | Physical px per dp |
|----------------|--------------|-----------------|-------------------|
| ldpi | 120 dpi | 0.75× | 0.75 px |
| mdpi (baseline) | 160 dpi | 1.0× | 1 px |
| hdpi | 240 dpi | 1.5× | 1.5 px |
| xhdpi | 320 dpi | 2.0× | 2 px |
| xxhdpi | 480 dpi | 3.0× | 3 px |
| xxxhdpi | 640 dpi | 4.0× | 4 px |

**dp (density-independent pixel):**
```
1dp = 1/160 inch at mdpi baseline
physical_px = dp × multiplier  (for current density bucket)
dp_value = px_value × 160 / PPI
```
For standard design workflow: design at @1× in Figma → 1 Figma px = 1dp (direct 1:1 mapping at mdpi baseline).

**sp (scale-independent pixel) — for fonts ONLY:**
```
sp_value = dp_value × font_scale_factor
```
User-configurable font_scale_factor in Android Accessibility settings: 0.85, 1.0, 1.15, 1.30, 1.85.
**Always use sp for font size tokens on Android.** Using dp for fonts ignores user accessibility preferences (WCAG 1.4.4 violation).

**Android XML token formats:**
```xml
<!-- values/colors.xml: COLOR tokens -->
<!-- Android color format: #AARRGGBB (alpha first) -->
<resources>
  <color name="colorPrimary">#FF3B82F6</color>
  <color name="colorSurface">#FFFAFAFA</color>
</resources>

<!-- values/dimens.xml: DIMENSION tokens -->
<resources>
  <dimen name="spacingMd">16dp</dimen>
  <dimen name="fontSizeBody">16sp</dimen>
  <dimen name="cornerRadiusCard">8dp</dimen>
</resources>
```

**Compose color token:**
```kotlin
object TokenStyles {
  val ColorPrimary = Color(0xFF3B82F6)  // ARGB hex in Compose
  val SpacingMd = 16.dp
  val FontSizeBody = 16.sp
}
```

## 3. iOS Point Scaling and Xcode Color Assets

**iOS coordinate system:**
```
1pt (iOS point) = 1 physical pixel at @1× (non-retina, 163 dpi)
@2× Retina:  1pt = 2 physical pixels
@3× ProMotion: 1pt = 3 physical pixels
Figma @1× design pixel → iOS: 1:1 mapping to points
```

**Xcode Color Asset (Contents.json):**
```json
{
  "colors": [
    {
      "idiom": "universal",
      "appearances": [{ "appearance": "luminosity", "value": "light" }],
      "color": {
        "color-space": "srgb",
        "components": { "red": "0.231", "green": "0.510", "blue": "0.965", "alpha": "1.000" }
      }
    },
    {
      "idiom": "universal",
      "appearances": [{ "appearance": "luminosity", "value": "dark" }],
      "color": {
        "color-space": "srgb",
        "components": { "red": "0.431", "green": "0.647", "blue": "0.996", "alpha": "1.000" }
      }
    }
  ],
  "info": { "author": "xcode", "version": 1 }
}
```

**Swift UIColor initializer:**
```swift
extension UIColor {
  static let colorPrimary = UIColor(red: 0.231, green: 0.510, blue: 0.965, alpha: 1.0)
}
```

**SwiftUI Color initializer:**
```swift
extension Color {
  static let colorPrimary = Color("colorPrimary")  // from asset catalog
  // Or programmatic:
  static let colorPrimaryDynamic = Color(uiColor: .colorPrimary)
}
```

**Dynamic Type for font tokens:**
```swift
// Use Dynamic Type scale for accessibility-respecting font sizes
Text("Headline").font(.headline)  // respects user Dynamic Type settings
Text("Body").font(.body)          // maps to system font at preferred size
```

## 4. Wide-Gamut Color and OKLCH

**Display P3 vs sRGB:**
- sRGB covers ~35% of visible colors (CIE 1931 xy chromaticity)
- Display P3 covers ~45% of visible colors (strict superset of sRGB)
- P3 can represent more saturated greens and reds than sRGB

**CSS Color Level 4 P3 syntax:**
```css
/* Wide-gamut P3 color */
.element {
  color: color(display-p3 0.5 0.7 0.3);
}

/* sRGB fallback in cascade (browser support check) */
@supports (color: color(display-p3 0 0 0)) {
  .element { color: color(display-p3 0.5 0.7 0.3); }
}
```

**OKLCH for perceptual palette generation:**
- L (lightness): 0–1 perceptual lightness
- C (chroma): 0–~0.4+ (saturation equivalent)
- H (hue): 0–360° hue angle
- Equal L steps in OKLCH = equal perceived lightness steps (unlike HSL)

**Dark mode semantic alias pattern:**
```json
{
  "color": {
    "primitive": {
      "blue-300": { "$type": "color", "$value": "#93c5fd" },
      "blue-500": { "$type": "color", "$value": "#3b82f6" }
    },
    "semantic": {
      "action": { "$type": "color", "$value": "{color.primitive.blue-500}" }
    }
  }
}
```
Dark mode override set:
```json
{
  "color": {
    "semantic": {
      "action": { "$value": "{color.primitive.blue-300}" }
    }
  }
}
```

## 5. Fluid Typography and Animation Tokens

**Fluid typography with CSS `clamp()`:**
Single token value spans a viewport range without media queries.

**DTCG fluid typography token encoding:**
```json
{
  "font-size-body": {
    "$type": "dimension",
    "$value": "clamp(1rem, calc(0.857rem + 0.714vw), 1.5rem)"
  }
}
```
Alternative: store min/max/slope as separate reference tokens and compute clamp in a Style Dictionary transform.

**Animation easing tokens (W3C DTCG `cubicBezier` type):**
```json
{
  "easing": {
    "standard": { "$type": "cubicBezier", "$value": [0.4, 0, 0.2, 1] },
    "decelerate": { "$type": "cubicBezier", "$value": [0, 0, 0.2, 1] },
    "accelerate": { "$type": "cubicBezier", "$value": [0.4, 0, 1, 1] }
  },
  "duration": {
    "short": { "$type": "duration", "$value": "100ms" },
    "medium": { "$type": "duration", "$value": "200ms" },
    "long": { "$type": "duration", "$value": "400ms" }
  }
}
```

**Platform output for animation tokens:**
```css
/* CSS */
--easing-standard: cubic-bezier(0.4, 0, 0.2, 1);
--duration-medium: 200ms;
```
```kotlin
// Compose
val EasingStandard = CubicBezierEasing(0.4f, 0f, 0.2f, 1f)
val DurationMedium = 200  // milliseconds
```
```swift
// iOS UIKit
let easingStandard = CAMediaTimingFunction(controlPoints: 0.4, 0.0, 0.2, 1.0)
let durationMedium: TimeInterval = 0.2  // seconds
```

## 6. Cross-Platform Deployment Automation

**Atomic multi-platform deployment pattern:**
```bash
#!/bin/bash
set -euo pipefail  # exit on first error → atomic rollback

# Pre-flight: validate input token file
npx dtcg-validate tokens/source.json

# Transform (Style Dictionary v4 — all platforms in parallel)
node -e "
  import('./sd.config.js').then(({ default: config }) => {
    const StyleDictionary = require('style-dictionary');
    new StyleDictionary(config).buildAllPlatforms();
  })
"

# Per-platform validation
# Android: validate XML parse
xmllint --noout dist/android/res/values/colors.xml
xmllint --noout dist/android/res/values/dimens.xml

# iOS: validate Swift compile
swiftc -typecheck dist/ios/TokenStyles.swift

# CSS: validate custom property syntax
npx stylelint dist/css/variables.css

echo "All platforms validated — deployment complete"
```

**Rollback on failure:**
If any platform validation fails, `set -euo pipefail` causes immediate exit. CI system reverts to previous successful build artifacts. Never ship partial platform outputs.

**Per-platform health check in CI:**
```yaml
- name: Validate Android XML
  run: xmllint --noout dist/android/res/values/*.xml

- name: Validate CSS
  run: npx stylelint dist/css/**/*.css

- name: Validate Swift
  run: swiftc -typecheck dist/ios/TokenStyles.swift
```

## Deep Mathematical Foundations

### M1: Density Math (dp/sp/pt Conversions + PPI-Aware Scaling)

**Android dp physical definition:**
```
1dp = 1/160 inch (mdpi baseline, 160 dpi)
physical_pixels = dp × (PPI / 160)
```

**Density multiplier derivation:**
```
mdpi (160 dpi): multiplier = 160/160 = 1.0×   → 1dp = 1 physical pixel
hdpi (240 dpi): multiplier = 240/160 = 1.5×   → 1dp = 1.5 physical pixels
xhdpi (320 dpi): multiplier = 320/160 = 2.0×  → 1dp = 2 physical pixels
xxhdpi (480 dpi): multiplier = 480/160 = 3.0× → 1dp = 3 physical pixels
xxxhdpi (640 dpi): multiplier = 640/160 = 4.0×→ 1dp = 4 physical pixels
```

**sp accessibility scaling:**
```
sp = dp × font_scale_factor
User font_scale settings: 0.85 (small), 1.0 (default), 1.15, 1.30, 1.85 (largest)
At font_scale=1.85: a 16sp font renders at 16×1.85 = 29.6sp ≈ 30 sp effective
```
This means a 16sp base font size can reach 30sp at maximum accessibility setting. Layout must accommodate this expansion.

**Figma px to dp mapping:**
```
Figma design at @1× → 1 Figma px = 1dp (direct 1:1 at mdpi baseline)
Figma design at @2× → 1 Figma px = 0.5dp
Figma design at @3× → 1 Figma px = 0.333dp
```
Design at @1× in Figma for 1:1 dp mapping (canonical convention for Android design system).

**iOS pt physical definition:**
```
1pt (iOS point) = 1/163 inch (base @1× non-retina device PPI)
@1× device: 1pt = 1 physical pixel (163 PPI)
@2× Retina: 1pt = 2 physical pixels (326 PPI)
@3× ProMotion: 1pt = 3 physical pixels (458–460 PPI)
```
Figma @1× → iOS: 1 Figma px = 1 iOS pt (1:1 mapping by convention).

**CSS px absolute definition:**
```
1px = 1/96 inch (CSS 2.1 absolute unit)
1rem = 16px (browser default root font size, user-configurable)
pt_value_css = px_value × 0.75  (CSS print points, 1pt = 1/72 inch)
```

**Cross-platform conversion matrix (from Figma @1×):**
```
Figma px (@1×) → CSS px:          1px
Figma px (@1×) → Android dp:      1dp
Figma px (@1×) → Android sp (font):1sp
Figma px (@1×) → iOS pt:          1pt
Figma px (@1×) → CSS rem (font):  0.0625rem (÷16)
```

### M2: Color Space P3/OKLCH (Gamut Boundary + 3×3 Transform Matrix)

**sRGB primary chromaticities (CIE xy):**
```
R: (0.640, 0.330), G: (0.300, 0.600), B: (0.150, 0.060)
White point D65: (0.3127, 0.3290)
sRGB covers ≈35% of CIE 1931 visible gamut
```

**Display P3 primary chromaticities (CIE xy):**
```
R: (0.680, 0.320), G: (0.265, 0.690), B: (0.150, 0.060)
White point D65: (0.3127, 0.3290) (same as sRGB)
P3 covers ≈45% of CIE 1931 visible gamut
P3 gamut ⊃ sRGB gamut (strict superset)
```

**sRGB → P3 color transform (step-by-step):**

Step 1: sRGB → linear RGB (apply piecewise gamma):
```
C_lin = C / 12.92                          if C ≤ 0.04045
C_lin = ((C + 0.055) / 1.055) ^ 2.4       if C > 0.04045
```

Step 2: Linear RGB → XYZ (D65), using sRGB→XYZ matrix:
```
[X]   [0.4124  0.3576  0.1805] [R_lin]
[Y] = [0.2126  0.7152  0.0722] [G_lin]
[Z]   [0.0193  0.1192  0.9505] [B_lin]
```

Step 3: XYZ → P3 linear (D65 white point, using inverse P3→XYZ matrix):
```
[R_p3_lin]   [ 2.4935  -0.9314  -0.4027] [X]
[G_p3_lin] = [-0.8290   1.7627   0.0236] [Y]
[B_p3_lin]   [ 0.0358  -0.0762   0.9568] [Z]
```

Step 4: P3 linear → P3 gamma (same 2.4 TRC as sRGB display-p3):
```
C_p3 = 1.055 × C_p3_lin ^ (1/2.4) − 0.055  if C_p3_lin > 0.0031308
C_p3 = 12.92 × C_p3_lin                      if C_p3_lin ≤ 0.0031308
```

**OKLCH gamut check for P3 deployment:**
Colors with high OKLCH chroma (C > ~0.26) at specific hue angles may exceed the P3 gamut boundary. Gamut mapping algorithm: binary search on C axis, reducing C until `max(R_p3, G_p3, B_p3) ≤ 1.0` and `min(R_p3, G_p3, B_p3) ≥ 0.0`.

**CSS color-gamut media query:**
```css
@media (color-gamut: p3) {
  :root {
    --color-primary: color(display-p3 0.263 0.510 0.965);
  }
}
```

### M3: Fluid Typography Math (Viewport-Relative Interpolation)

**Two-breakpoint linear interpolation:**
```
slope m = (V₂ − V₁) / (W₂ − W₁)
intercept = V₁ − m × W₁
preferred = intercept + m × viewport_width
CSS: clamp(V₁_rem, calc(intercept_rem + m × 100vw), V₂_rem)
```

**Rem conversion:**
```
intercept_rem = intercept_px / 16
V₁_rem = V₁_px / 16
V₂_rem = V₂_px / 16
```
Slope m is dimensionless (px/px = rem/rem) — no conversion needed for the `m × 100vw` term.

**Multi-breakpoint extension (3 breakpoints):**
```
Segment 1: clamp(V₁, calc(intercept₁ + m₁ × 100vw), V₂)  [W₁ to W₂]
Segment 2: clamp(V₂, calc(intercept₂ + m₂ × 100vw), V₃)  [W₂ to W₃]
Combined: min(max(segment₁, W₂_trigger), segment₂)
```

**Optimal logarithmic breakpoint spacing:**
For n breakpoints with target step sizes appearing perceptually equal:
```
W_k = W₁ × ratio^(k−1)
```
Logarithmic spacing gives equal perceived size changes across the viewport range.

**DTCG encoding of fluid value:**
Store as CSS clamp string in `$value` field with `$type: "dimension"`:
```json
{
  "font-size-body": {
    "$type": "dimension",
    "$value": "clamp(1rem, calc(0.857rem + 0.714vw), 1.5rem)",
    "$description": "Body font size: 16px at 320px → 24px at 1440px viewport"
  }
}
```

### M4: Animation Easing Math (Cubic-Bezier Parametric Form)

**CSS timing function cubic-bezier(P1x, P1y, P2x, P2y):**
Defines a Bézier curve from (0,0) to (1,1) with control points P1 and P2. P0=(0,0) and P3=(1,1) are fixed endpoints.

**Parametric Bézier form:**
```
B(t) = (1−t)³P0 + 3(1−t)²t×P1 + 3(1−t)t²×P2 + t³P3    t ∈ [0,1]
```

**X component (time):**
```
X(t) = 3(1−t)²t×P1x + 3(1−t)t²×P2x + t³
```

**Y component (animation progress):**
```
Y(t) = 3(1−t)²t×P1y + 3(1−t)t²×P2y + t³
```

**Solving for Y given X (CSS timing function evaluation via Newton-Raphson):**
1. Given x_input (time position), find t such that X(t) = x_input
2. Newton-Raphson iteration: `t_{n+1} = t_n − (X(t_n) − x_input) / X'(t_n)`
3. Derivative: `X'(t) = 3(1−t)²P1x + 6(1−t)t(P2x−P1x) + 3t²(1−P2x)`
4. After convergence (typically 4–8 iterations), evaluate Y(t) for animation progress

**Common preset control points:**
| Name | P1x | P1y | P2x | P2y | Curve Character |
|------|-----|-----|-----|-----|-----------------|
| ease-in | 0.42 | 0 | 1.0 | 1.0 | Slow start, fast end |
| ease-out | 0.0 | 0.0 | 0.58 | 1.0 | Fast start, slow end |
| ease-in-out | 0.42 | 0 | 0.58 | 1.0 | Slow at both ends |
| Material standard | 0.4 | 0 | 0.2 | 1 | Material Design motion |
| Material decelerate | 0 | 0 | 0.2 | 1 | Objects entering screen |
| Material accelerate | 0.4 | 0 | 1 | 1 | Objects leaving screen |

**DTCG cubicBezier token value:** Array `[P1x, P1y, P2x, P2y]` — all values normalized to [0, 1] range.

### M5: Dark Mode Alias Math (Semantic Alias Resolution + Luminance Polarity)

**Semantic alias structure:**
```
semantic_token → primitive_token (light mode value)
semantic_token → different_primitive_token (dark mode value)
```
Resolution based on active color scheme (light/dark).

**Token set layering for dark mode (Style Dictionary v4):**
```javascript
// config: source = light (base); dark set overrides semantic aliases
const sd = new StyleDictionary({
  source: ['tokens/primitive.json', 'tokens/semantic.light.json'],
  // platforms, transforms, and formats configured here
});
// For dark mode output:
const sdDark = new StyleDictionary({
  include: ['tokens/primitive.json'],
  source: ['tokens/semantic.dark.json'],  // overrides light semantic values
  // same platform config as light mode
});
```

**DTCG alias override in dark mode set:**
```json
// tokens/semantic.dark.json
{
  "color": {
    "semantic": {
      "action": { "$value": "{color.primitive.blue-300}" }
    }
  }
}
```
Same key path as light set, different alias target. Style Dictionary resolves using source priority (dark overrides include/base).

**Relative luminance polarity flip:**
If light mode has background luminance L_bg and foreground luminance L_fg:
```
Approximate dark mode background: L_bg_dark ≈ 1 − L_bg
Approximate dark mode foreground: L_fg_dark ≈ 1 − L_fg
```
This is a heuristic approximation — actual dark mode color values are designer-determined.

**WCAG 2.1 contrast invariance requirement:**
Light mode achieves: CR_light = (L1 + 0.05) / (L2 + 0.05) ≥ 4.5
Dark mode must be independently validated: CR_dark ≥ 4.5
Polarity flip does NOT automatically preserve CR. Must verify both modes.

**APCA dark mode asymmetry:**
APCA Lc has polarity asymmetry: dark text on light background (positive Lc) uses different exponents than light text on dark background (negative Lc). See figma-ai-automation-core M3 for full APCA coefficient derivation.
```
Dark mode (light text on dark bg): |Lc| ≥ 60 minimum for body text
Light mode (dark text on light bg): |Lc| ≥ 60 minimum for body text
Both must be independently verified with separate APCA computations.
```

### M6: Cross-Platform Transform Complexity (O(T × S × P) Cost Model)

**Pipeline cost model:**
```
T_total = O(N_tokens × T_avg × P)
```
Where:
- N_tokens = total tokens in source file(s)
- T_avg = average transforms per token per platform
- P = number of target platforms

**Per-token transform breakdown:**
- Color tokens: sRGB linearization (O(1)), hex↔components conversion (O(1)), P3 matrix multiply (O(1) — 9 multiplications)
- Dimension tokens: unit conversion (O(1) — one multiplication)
- Typography tokens: fontFamily string lookup (O(1)), fontWeight mapping (O(1))
- All transforms: O(1) constant-time per token (no dependencies between tokens at transform stage)

**Style Dictionary v4 parallel execution:**
Platforms run in parallel (async):
```
wall_clock_time = max(T_platform_i) + parallelization_overhead
NOT Σ(T_platform_i)
```
Practical: all 4 platforms complete in max(slowest_platform_time) ≈ 2–5 seconds for 500 tokens.

**Total output files:**
```
F_total = Σ_platform F_platform
Typical: CSS=1, SCSS=1, Android=2, iOS=N_colors+1, Compose=1 → F_total ≈ 10–20 files
```

**Incremental transform optimization:**
Diff token source files before running full pipeline:
```
ΔN_tokens = tokens changed since last build (typically 2–10% of total)
```
Re-transform only changed tokens:
```
T_incremental = O(ΔN_tokens × T × P)
Speedup = N_tokens / ΔN_tokens (at 5% change rate: 20× faster)
```
Worth implementing for N_tokens > 200 in production pipelines.

## Anti-Patterns to Avoid

- **Using `dp` instead of `sp` for Android font-size tokens**: §2 states this explicitly as a WCAG 1.4.4 violation — `dp` is fixed relative to display density only, while `sp` additionally scales with the user's `font_scale_factor` (0.85–1.85 in Android Accessibility settings); a font token emitted in `dp` silently ignores every user who has increased their system font size for readability.
- **Assuming Figma `@1×` design pixels map 1:1 to both Android dp and iOS pt without checking the baseline density**: §2 and §3 both state the 1:1 mapping holds specifically at Android's mdpi (160 dpi) baseline and iOS's @1× non-retina baseline — reusing raw Figma px values as dp/pt tokens without confirming the design file's export baseline density produces systematically wrong physical sizes on any project not authored at that exact baseline.
- **Shipping Display P3 colors without an sRGB fallback in the cascade**: §4 notes P3 covers a strictly larger gamut (~45% vs ~35% of visible colors) — a browser or device without P3 support that receives a `color(display-p3 ...)` value with no `@supports`-gated sRGB fallback either clips the color unpredictably or fails to render it, rather than gracefully degrading to the nearest in-gamut sRGB equivalent.
- **Overriding only the semantic alias, not auditing the full alias chain, when building a dark-mode token set**: §4's dark-mode pattern relies on `semantic.action` re-pointing to a different primitive (`blue-300` instead of `blue-500`) — if a downstream token references the semantic alias through an intermediate layer that itself hardcodes a primitive rather than re-resolving the alias, the dark-mode override silently fails to propagate for that one token while appearing correct everywhere else.
- **Encoding fluid typography as a static `clamp()` string without also emitting the min/max/slope as separate reference tokens**: §5 flags this as an alternative specifically because Style-Dictionary-transform-computed clamp values stay traceable to their source min/max/viewport inputs — a hardcoded clamp string loses that traceability, making a later request to adjust just the max size require re-deriving the entire clamp expression by hand instead of updating one reference token.
- **Deploying per-platform token outputs independently instead of atomically**: §6's `set -euo pipefail` pattern exists so a validation failure on any one platform (Android XML, iOS Swift, CSS) halts the entire deployment — shipping Android and CSS outputs while iOS validation is still failing (or retrying failed platforms independently rather than as one atomic unit) risks platforms drifting to different token versions, defeating the point of a single-source multi-platform pipeline.
- **Treating `swiftc -typecheck` or `xmllint --noout` success as proof the token values themselves are correct**: §6's per-platform validation confirms the generated files are syntactically valid Swift/XML/CSS, not that the color/dimension values they encode are the intended ones — a token pipeline bug that emits a well-formed but wrong hex value passes every health check in §6 while shipping incorrect colors to production.
- **Animating with a raw numeric duration or easing curve instead of the shared DTCG `cubicBezier`/`duration` tokens**: §5's animation tokens exist so `easing.standard` and `duration.medium` resolve identically across CSS `cubic-bezier()`, Compose `CubicBezierEasing`, and iOS `CAMediaTimingFunction` — hardcoding a platform-local easing curve or duration value that happens to look similar breaks the cross-platform motion consistency the token layer is meant to guarantee.

## India-Specific Layer

**Digital India Design System (DIDS) — NIC/MeitY:**
Multi-platform output is mandatory for DIDS-compliant deployments. GOV.IN portals require simultaneous consistency across Android GOV apps (dp/sp), iOS GOV apps (pt), and government web portals (CSS rem). DIDS token format: [UNVERIFIED — whether W3C DTCG-compliant or custom JSON schema; synthesis agent Search 1 pending. Token pipelines targeting DIDS should maintain format flexibility until confirmed.]

**RPwD Act 2016 §40 (Accessibility — Multi-Platform):**
- **Android:** Font size tokens must use sp units (not dp). Respects user font-scale in Android accessibility settings. Mandatory per RPwD §40 applicability to Android apps for government services.
- **iOS:** Dynamic Type must be supported. Font tokens should map to iOS text style categories (`.body`, `.headline`, etc.) or use scaled metrics. Mandatory for iOS GOV.IN apps.
- **CSS:** Font tokens must use rem units (not px). Respects user browser font-size preference (WCAG 1.4.4 Resize Text). Mandatory for GOV.IN web portals.
- **Wide-gamut:** P3 colors must always have sRGB CSS fallback. Accessibility users on older devices must receive equivalent colors.

**GIGW v3.0 (Multi-Device and Accessibility Requirements):**
Government websites must be equally usable on mobile (Android/iOS) and desktop. Token pipelines must produce validated, tested outputs for all three platform targets simultaneously. Fluid typography clamp values must produce font sizes ≥ GIGW minimum (confirm exact minimums from official GIGW v3.0). [CONFIDENCE: MED for exact GIGW section numbers.]

**BIS IS 16333 (Parts 1–4) — Unicode for Indian Languages:**
Typography tokens for multi-script Indian government apps must include Devanagari-capable font families per platform:
```
Android fontFamily: "Noto Sans Devanagari"
iOS fontFamily: "Devanagari Sangam MN" (system) or "Noto Sans Devanagari"
CSS fontFamily: "Noto Sans Devanagari", "Mangal", sans-serif
```
Part 2: Devanagari Unicode encoding; Part 3: Devanagari rendering requirements. Exact section applicability to fontFamily token definitions: [CONFIDENCE: MED — confirm via synthesis agent Search 3.]

## Response Rules

- Always use sp (not dp) for Android font size tokens — sp respects user accessibility font-scale settings in Android Accessibility menu. Using dp for fonts violates WCAG 1.4.4 (Resize Text) and RPwD Act §40.
- Always use rem (not px) for CSS font size tokens — rem respects the user's configured browser default font size preference. px font sizes do not scale when users change their browser font size.
- Always test dark mode alias token values for WCAG 2.1 AA contrast independently — polarity flip from light to dark mode does NOT automatically preserve the contrast ratio. Both light and dark modes must be explicitly validated.
- Always include a CSS fallback before wide-gamut `color(display-p3 ...)` declarations — P3 syntax requires CSS Color Level 4 support. Use `@supports (color: color(display-p3 0 0 0))` guard or cascade fallback.
- Always deploy all platform token outputs atomically — never update CSS tokens without simultaneously updating Android and iOS tokens from the same DTCG source. Platform drift causes visual inconsistency and accessibility failures on some platforms.

## What Not to Do

- Do not use dp for Android font sizes — always use sp. px is not a valid Android resource dimension unit. dp does not respect user font-scale accessibility settings.
- Do not use OKLCH colors directly in production CSS without sRGB fallbacks — `oklch(...)` CSS syntax requires CSS Color Level 4 support (not universal as of 2026). Provide sRGB equivalent in the cascade.
- Do not generate separate dark mode token files that diverge from the light mode primitive token structure — dark mode aliases must reference the same primitive token set. Parallel primitive sets diverge over time and are unmaintainable.
- Do not encode cubic-bezier control points as pixels or percentages — DTCG `cubicBezier` `$value` must use normalized numbers in [0, 1] range. CSS `cubic-bezier()` expects the same normalized values.
- Do not manually convert dp to px for iOS token values — 1 Figma px at @1× = 1dp (Android) = 1pt (iOS). The mapping is 1:1 at @1× design resolution. Unit conversion is only needed when the source design is at @2× or @3×.

## Output Expectations

Responses provide:
- Complete platform unit conversion table with formulas (dp/sp/pt/rem/px)
- Style Dictionary v4 multi-platform configuration with Android/iOS/Compose/CSS platform definitions
- DTCG token file examples with dark mode set (light + dark token files)
- sRGB → Display P3 transform matrices (3×3 numeric values)
- Fluid typography clamp derivations for specified viewport breakpoints
- Cubic-bezier parametric form and Newton-Raphson evaluation for CSS timing functions
- Dark mode alias resolution patterns with contrast ratio validation requirements
- Android XML and iOS Swift/Compose code samples for each token type
- M1–M6 full mathematical derivations with all formulas and proofs
- India multi-platform accessibility compliance checklist (RPwD §40, DIDS, GIGW, BIS IS 16333)

## Skill Scope

**In scope:** Android dp/sp density math and density bucket multipliers, iOS pt point scaling and @1×/@2×/@3× mapping, CSS rem/px conversion, Display P3 gamut and sRGB→P3 3×3 transform matrix, OKLCH gamut check and chroma mapping, fluid typography CSS clamp derivation, cubic-bezier parametric form and Newton-Raphson evaluation, dark mode alias resolution with WCAG invariance requirement, multi-platform Style Dictionary v4 pipeline cost model and incremental optimization.

**Out of scope:** W3C DTCG token schema and DAG alias resolution (see design-tokens-automation-core), REST API authentication for token fetching (see figma-rest-api-core), code generation algorithms (see figma-codegen-core), plugin/widget development (see figma-plugin-widget-core), CI/CD pipeline orchestration (see figma-ci-cd-pipeline-core), APCA contrast computation (see figma-ai-automation-core).

## Version: 1.1 — Added Anti-Patterns to Avoid section (dp-vs-sp accessibility violation, baseline-density mapping assumptions, P3-without-sRGB-fallback, dark-mode alias-chain gaps, hardcoded clamp values, non-atomic multi-platform deploys, syntax-valid-but-wrong-value validation gap, hardcoded easing/duration bypassing shared tokens)
