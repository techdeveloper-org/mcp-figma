---
name: design-tokens-automation-core
description: "Provides complete design token pipeline implementation — W3C DTCG 2025.10 schema, color space math (sRGB/HSL/OKLCH), modular typography scales, 8-point grid derivation, token inheritance DAG resolution, and Style Dictionary v4 multi-platform transform pipeline. Use when building or auditing token pipelines, migrating from legacy token formats to W3C DTCG, or automating design-to-development token handoff. Keywords: design tokens automation, w3c dtcg format, style dictionary pipeline, figma variables to tokens, token inheritance resolution, oklch color tokens, typography scale math"
allowed-tools: Read,Glob,Grep,Bash,Edit,Write
user-invocable: true
---


<!-- generated-by: claude-global-library/tools/project_sync -->
<!-- source: skills/design-tokens-automation-core/SKILL.md -- edit the library, then re-run sync_project.py -->

# design-tokens-automation-core

## Description

Complete design token pipeline implementation covering the W3C DTCG 2025.10 specification, color space mathematics (sRGB/HSL/OKLCH), modular typography scale generation, 8-point grid derivation, token inheritance DAG resolution with cycle detection, and Style Dictionary v4 multi-platform transform pipeline.

## 1. W3C DTCG 2025.10 Token Format

The W3C Design Tokens Community Group published the first stable specification (version 2025.10) on October 28 2025. It is a W3C Community Group publication — **not a W3C Standard** and not on the W3C Standards Track — but it is production-grade and vendor-neutral.

**Mandatory fields:**
- `$value` — the token value (required on every token)
- `$type` — the token type (required at token or group level; inheritable from parent group)

**Optional fields (officially ratified):**
- `$description` — human-readable description
- `$extensions` — vendor-specific metadata (e.g., `$extensions.figma`, `$extensions.styledict`)

**Token types:**
| Type | Example |
|------|---------|
| `color` | `"#3b82f6"`, `"oklch(60% 0.2 250)"` |
| `dimension` | `"16px"`, `"1rem"`, `"8pt"` |
| `fontFamily` | `"Inter"`, `["Inter", "system-ui", "sans-serif"]` |
| `fontWeight` | `400`, `"bold"` |
| `fontSize` | `"1rem"`, `"16px"` |
| `duration` | `"200ms"`, `"0.2s"` |
| `cubicBezier` | `[0.4, 0, 0.2, 1]` |
| `number` | `4`, `1.5` |
| `strokeStyle` | `"solid"`, `{ dashArray: [...] }` |
| `border` | Composite |
| `transition` | Composite |
| `shadow` | Composite |
| `gradient` | Composite |
| `typography` | Composite |

**Composite types contain nested `$value` objects.** Example — `typography` composite:
```json
{
  "body": {
    "$type": "typography",
    "$value": {
      "fontFamily": "Inter",
      "fontWeight": 400,
      "fontSize": "1rem",
      "letterSpacing": "0em",
      "lineHeight": 1.5
    }
  }
}
```

**Token references (aliases):** `{token.group.name}` — dot-separated path enclosed in `{}`.
```json
{
  "color": {
    "primitive": {
      "blue500": { "$type": "color", "$value": "#3b82f6" }
    },
    "semantic": {
      "primary": { "$type": "color", "$value": "{color.primitive.blue500}" }
    }
  }
}
```

**Group-level type inheritance:** `$type` declared on a group applies to all child tokens that do not override it:
```json
{
  "spacing": {
    "$type": "dimension",
    "sm": { "$value": "4px" },
    "md": { "$value": "8px" },
    "lg": { "$value": "16px" }
  }
}
```

**Tooling adoption (2025.10 conformant):** Style Dictionary v4, Tokens Studio, Terrazzo, Supernova, Knapsack, Penpot, Figma, Sketch, Framer, zeroheight.

## 2. Color Token Math — sRGB, HSL, and OKLCH

**Color space hierarchy for design tokens:**
1. **OKLCH** — perceptually uniform; use for algorithmic palette generation
2. **sRGB (hex/rgba)** — storage and delivery format; universal support in DTCG `$value`
3. **HSL** — design-tool manipulation format; not suitable for algorithmic generation

**Key principle:** Generate palettes in OKLCH (perceptual uniformity), store in sRGB hex for DTCG `$value`, convert via the full chain: OKLCH → OKLab → XYZ → linear RGB → sRGB.

**Perceptual uniformity of OKLCH:**
- Equal Euclidean distance in OKLCH ≈ equal perceived color difference
- Unlike HSL (highly non-uniform perceptually), equal chroma/hue steps in OKLCH produce equal perceived differences
- Enables generating n accessible palette steps with uniform perceived spacing: ΔC = C_max / n per step

**sRGB vs HSL for palette generation — key difference:**
- HSL: two colors with identical S and L but different H can appear dramatically different in perceived lightness
- OKLCH: L channel is truly perceptual lightness; L=0.60 appears the same perceived brightness across all hue angles

## 3. Typography Scale Mathematics

**Modular type scale:** Generates harmonious font-size progressions using a fixed ratio.
```
size_n = base × ratio^n
```
Where `base = 1rem (16px)`, n is the scale step (negative for smaller, positive for larger).

**Common ratios:**
| Name | Ratio | Notes |
|------|-------|-------|
| Major Second | 1.125 | Subtle progression |
| Major Third | 1.250 | Comfortable for text-heavy interfaces |
| Perfect Fourth | 1.333 | Widely used web scale |
| Minor Fifth | 1.414 | √2, strong contrast |
| Golden Ratio | 1.618 | Maximum drama, limited steps |

**Example (Perfect Fourth, ratio=1.333, base=1rem):**
| Step | Size | Use |
|------|------|-----|
| n=−1 | 0.750rem | Caption, label |
| n=0 | 1.000rem | Body text |
| n=1 | 1.333rem | Lead, large body |
| n=2 | 1.777rem | Heading 3 |
| n=3 | 2.369rem | Heading 2 |
| n=4 | 3.157rem | Heading 1 |

**Fluid typography:** CSS `clamp()` produces responsive size between min and max values at defined viewport breakpoints. The slope and intercept are derived mathematically (see M2).

**DTCG typography composite token:** `{$type: "typography", $value: {fontFamily, fontWeight, fontSize, letterSpacing, lineHeight}}`

## 4. Spacing and Grid Token Mathematics

**8-point grid system (base unit = 8px):**
- All spacing values are multiples of 8px (or 4px for micro-spacing)
- Standard values: 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96, 128 px
- Rationale: most display resolutions are multiples of 8; 8px avoids sub-pixel rendering artifacts at standard densities; minimum touch target = 44px (iOS HIG) = 5.5 × 8px

**DTCG dimension tokens encode spacing with units:**
```json
{
  "spacing": {
    "$type": "dimension",
    "xs": { "$value": "4px" },
    "sm": { "$value": "8px" },
    "md": { "$value": "16px" },
    "lg": { "$value": "24px" },
    "xl": { "$value": "32px" },
    "2xl": { "$value": "48px" }
  }
}
```

**Grid layout token math:**
```
column_width = (container_width − (n_cols − 1) × gutter − 2 × margin) / n_cols
```
Responsive gutter: `gutter_fluid = gutter_min + (gutter_max − gutter_min) × (vw − W_min) / (W_max − W_min)`

**Component-level naming convention:** `{component}.{spacing-role}` — e.g., `card.padding.horizontal`, `button.gap`.

## 5. Style Dictionary v4 Transform Pipeline

**Version:** Style Dictionary v4 is the current version — near-complete rewrite from v3. **v3 config format does not work in v4** (breaking change). Native W3C DTCG `$value`/`$type` support — no pre-processing required for standard DTCG files.

**v4 platform configuration example:**
```javascript
// sd.config.js (v4 format)
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

**Async transform support:** v4 transforms can be async functions — enables transforms that fetch external data or perform async computations during pipeline execution.

**Token Transformer (by Tokens Studio):** Pre-processing utility that converts Tokens Studio JSON format (with non-DTCG metadata) to W3C DTCG format for Style Dictionary v4 input. Required when using Tokens Studio plugin as the design token authoring tool.

**Tooling ecosystem:**
- **Style Dictionary v4** — primary transform pipeline (Amazon, open source)
- **Terrazzo** — DTCG-native alternative; reference implementation alongside Style Dictionary
- **Tokens Studio** — Figma plugin for authoring tokens; exports via Token Transformer
- **Supernova, Knapsack, zeroheight** — enterprise token management with 2025.10 conformance

## 6. Figma Variables → DTCG Pipeline and Tooling Ecosystem

**Export path from Figma:**
1. `GET /v1/files/:key/variables/local` — retrieve all VariableCollections and Variables
2. Map VariableCollection → DTCG token group; each Mode → separate token set
3. Map Variable resolvedType to DTCG `$type`: COLOR→`color`, FLOAT→`number` or `dimension`, STRING→`fontFamily` or text token, BOOLEAN→custom extension
4. Map VariableScope → DTCG `$extensions.figma.scopes`: FONT_SIZE → `$type: "fontSize"`, etc.
5. Alias variables → DTCG alias syntax `{collection.variable.name}`

**Mode → token set mapping:**
```
VariableCollection "Colors" with modes [Light, Dark]
→ tokens/colors.light.json  (Light mode values)
→ tokens/colors.dark.json   (Dark mode values)
Style Dictionary: source: ['tokens/colors.light.json'], include: ['tokens/colors.light.json'], override: ['tokens/colors.dark.json']
```

**Variable alias preservation:**
A variable that references another variable via `{ type: "VARIABLE_ALIAS", id: "<id>" }` becomes a DTCG alias `{group.token}` in the exported token file. Alias chain depth is unbounded in the API but practically should be ≤ 5 hops for Style Dictionary performance.

## Deep Mathematical Foundations

### M1: Color Space Transforms (sRGB Linearization, HSL↔RGB, OKLCH)

**sRGB to linear RGB (IEC 61966-2-1 piecewise transfer function):**
```
C_lin = C / 12.92                          if C ≤ 0.04045
C_lin = ((C + 0.055) / 1.055) ^ 2.4       if C > 0.04045
```
Where C ∈ [0, 1] is the sRGB channel value (R, G, or B).

**Linear RGB to sRGB (inverse transfer function):**
```
C_srgb = 12.92 × C_lin                    if C_lin ≤ 0.0031308
C_srgb = 1.055 × C_lin ^ (1/2.4) − 0.055 if C_lin > 0.0031308
```

**HSL to RGB conversion (H ∈ [0°, 360°], S ∈ [0,1], L ∈ [0,1]):**
```
C = (1 − |2L − 1|) × S                    (chroma)
X = C × (1 − |H/60 mod 2 − 1|)            (intermediate)
m = L − C/2                               (lightness match factor)

H sector assignment:
  0° ≤ H < 60°:   (R', G', B') = (C, X, 0)
  60° ≤ H < 120°: (R', G', B') = (X, C, 0)
  120° ≤ H < 180°:(R', G', B') = (0, C, X)
  180° ≤ H < 240°:(R', G', B') = (0, X, C)
  240° ≤ H < 300°:(R', G', B') = (X, 0, C)
  300° ≤ H < 360°:(R', G', B') = (C, 0, X)

Final: (R, G, B) = (R' + m, G' + m, B' + m)
```

**RGB to HSL:**
```
max = max(R, G, B), min = min(R, G, B), delta = max − min
L = (max + min) / 2
S = delta / (1 − |2L − 1|)   if delta ≠ 0, else S = 0
H from atan2 based on which channel is max
```

**OKLCH conversion chain (sRGB → OKLCH):**
1. sRGB → linear RGB (apply sRGB linearization above)
2. Linear RGB → XYZ_D65: `[X, Y, Z] = M_sRGB × [R_lin, G_lin, B_lin]`
   ```
   M_sRGB = [[0.4124, 0.3576, 0.1805],
              [0.2126, 0.7152, 0.0722],
              [0.0193, 0.1192, 0.9505]]
   ```
3. XYZ → LMS (Bradford cone response): `[l, m, s] = M_Bradford × [X, Y, Z]`
4. Apply cube root: `[l', m', s'] = [∛l, ∛m, ∛s]`
5. LMS → OKLab (linear mix): `[L_ok, a_ok, b_ok] = M_OKLab × [l', m', s']`
6. OKLab → OKLCH:
   ```
   L = L_ok
   C = √(a_ok² + b_ok²)
   H = atan2(b_ok, a_ok) × 180/π   (mod 360°)
   ```

**Perceptual uniformity theorem:** Equal Euclidean distance in OKLCH ≈ equal perceived color difference. HSL violates this — equal HSL steps produce wildly varying perceived differences. For n accessible palette steps with uniform perceived spacing: generate `C_k = C_base`, `L_k = L_start + k × ΔL`, varying L uniformly across OKLCH steps.

### M2: Typography Scale Math (Modular Scale + Fluid Clamp)

**Modular scale:**
```
size_n = base × ratio^n
```
Base = 1rem (16px); ratio ∈ {1.125, 1.250, 1.333, 1.414, 1.618}.

**Fluid clamp derivation (two-breakpoint interpolation):**
Given minimum value V₁ at viewport width W₁, maximum value V₂ at viewport width W₂:
```
slope m = (V₂ − V₁) / (W₂ − W₁)            [px/px, dimensionless]
intercept = V₁ − m × W₁                      [px]
preferred = intercept + m × viewport_width
CSS: clamp(V₁, calc(intercept_rem + m × 100vw), V₂)
```

**Worked example (font size 16px at 320px → 24px at 1440px):**
```
m = (24 − 16) / (1440 − 320) = 8 / 1120 ≈ 0.00714 px/px
intercept = 16 − 0.00714 × 320 ≈ 13.71 px = 0.857 rem
CSS: clamp(1rem, calc(0.857rem + 0.714vw), 1.5rem)
```

**Converting px coefficients to rem:** Divide all px values by 16 (browser default root font size). The slope m is dimensionless (px/px = rem/rem), so `m × 100vw` is unchanged in rem units.

**Line-height optimization:**
- Optimal for body text: LH_opt = (font_size + 4px) / font_size (add 4px to font size for comfortable reading)
- Target range: 1.4 ≤ LH ≤ 1.6 for body text
- Use dimensionless ratio (not px) to preserve accessibility scaling

**Letter-spacing normalization:**
- Use em units for proportional scaling: 0.01em = 10 units of tracking (print DTP convention: tracking_points / 1000)
- Never use px for letter-spacing in design tokens (breaks proportional scaling)

### M3: Spacing and Grid Math (8-Point Grid + Golden Ratio)

**8-point grid:**
```
spacing_n = 8 × n
n ∈ {0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 16}
values: 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96, 128 px
```

**Physical basis:** 1dp on Android mdpi (160dpi) = 1/160 inch; 8px = 8/96 inch (CSS) ≈ 0.083 inch. Most display resolutions (768, 1024, 1440, 1920px) are multiples of 8. Sub-pixel rendering artifacts do not occur when all measurements are multiples of 8px at standard device pixel ratios.

**Touch target minimum:** 44px (iOS HIG) = 5.5 × 8px; 48dp (Android Material 3) = 6 × 8dp. Both align to the 8-point grid.

**Golden ratio harmonic sequence:**
```
φ = (1 + √5) / 2 ≈ 1.618
spacing_n = base × φ^n, base = 8px
Values: ≈5, 8, 13, 21, 34, 55, 89 px
```

**Fibonacci approximation:** The Fibonacci sequence F_n satisfies F_n / F_{n-1} → φ as n → ∞. Fibonacci values (5, 8, 13, 21, 34, 55, 89) round to the nearest 4px for grid compatibility.

**Responsive grid layout:**
```
column_width = (container_width − (n_cols − 1) × gutter − 2 × margin) / n_cols
total_spacing = (n_cols − 1) × gutter + 2 × margin
```
Fluid gutter: `gutter_fluid = gutter_min + (gutter_max − gutter_min) × (vw − W_min) / (W_max − W_min)`

### M4: Token Inheritance DAG (Topological Sort + Cycle Detection)

**Token reference graph:**
- V = all tokens (vertices)
- E = directed edges: `(consumer_token → provider_token)` for each alias `{provider.path}` in consumer's `$value`
- Valid graph: must be a DAG (Directed Acyclic Graph)

**Topological sort using Kahn's algorithm:**
```
L ← [] (sorted output)
S ← {v ∈ V : in_degree(v) = 0}  (tokens with no dependencies)
while S not empty:
    u = extract any node from S
    append u to L
    for each (u → v) in E:
        in_degree(v) -= 1
        if in_degree(v) = 0:
            add v to S
if |L| ≠ |V|:
    CYCLE DETECTED — nodes with remaining in_degree > 0 form the cycle(s)
```

**Complexity:** O(V + E) time, O(V) space for in-degree tracking.

**W3C DTCG 2025.10 alias resolution:**
- Resolve tokens in topological order (Kahn's output L)
- Each `{token.path}` reference is resolved to its primitive `$value` at the token's position in topological order
- Circular references: DTCG 2025.10 treats them as an error condition; tools (Style Dictionary v4, Terrazzo) must detect cycles before resolution and report the full cycle path

**Cycle error reporting:**
```python
# After Kahn's: find nodes with remaining in_degree > 0
cycle_nodes = [v for v in V if in_degree[v] > 0]
# Trace cycle path using DFS from any cycle node
```

**Alias depth limit:** DTCG 2025.10 does not specify a maximum alias chain depth. Style Dictionary v4 default: unlimited (configurable). Deep chains (>10 hops) degrade resolution performance without memoization.

**Memoized resolution:** Cache resolved primitive values per token. On first resolution of token X: resolve all its dependencies recursively (respecting topological order), then cache X's resolved value. Subsequent lookups: O(1) cache hit. Total cost: O(V + E) amortized for full graph resolution.

### M5: Style Dictionary Pipeline Complexity (O(T × P × F))

**Cost model:**
```
T_total = O(N_tokens × T × P × F)
```
Where:
- N_tokens = total number of tokens in the token file(s)
- T = number of transforms applied per token per platform
- P = number of output platforms (CSS, Android, iOS, Compose, ...)
- F = number of output files per platform

**Each token:** processed by T transforms on each of P platforms, then written to F files per platform.

**Style Dictionary v4 async parallelism:**
- Transforms per platform run as async functions
- Platforms run in parallel: wall-clock time = max(T_platform_i) + overhead, NOT Σ(T_platform_i)
- Per-token parallelism is possible but limited by token dependency order

**Token Transformer (Tokens Studio bridge) overhead:**
- Pre-processing step: convert Tokens Studio JSON to DTCG format
- Complexity: O(N_tokens) — one pass through all tokens
- Adds fixed overhead before Style Dictionary pipeline executes

**Platform output examples:**
```
CSS custom properties:   --token-name: value;
Android values/colors.xml: <color name="token_name">#FFAABBCC</color>
Android values/dimens.xml: <dimen name="token_name">16dp</dimen>
iOS Swift: static let tokenName = UIColor(red: 0.2, green: 0.4, blue: 1.0, alpha: 1.0)
Compose: val TokenName = Color(0xFF3366FF)
```

**Optimization:** Skip platforms for token types with no applicable transforms. Skip color transforms on dimension tokens. Batch tokens by type before transforming.

### M6: Multi-Platform Unit Conversion Math

**rem/px (CSS):**
```
rem_value = px_value / base_font_size_px
Default: base = 16px → 1rem = 16px
Style Dictionary config: basePxFontSize: 16
```

**CSS pt (absolute print point):**
```
1pt = 1/72 inch (CSS absolute unit)
1px = 0.75pt
pt_value = px_value × 0.75
```

**Android dp (density-independent pixel):**
```
1dp = 1/160 inch (mdpi baseline)
dp_value = px_value × 160 / PPI_of_display
For mdpi (160dpi): dp_value = px_value × 1 (1:1)
For xhdpi (320dpi): dp_value = px_value × 0.5
```

**Android sp (scale-independent pixel — fonts only):**
```
sp_value = dp_value × font_scale_factor
Default font_scale_factor = 1.0 (user can change in Android accessibility settings)
```
sp tracks user accessibility font preferences. **Always use sp for font-related tokens on Android.**

**iOS pt (device point — NOT print pt):**
```
1pt = 1/163 inch (base @1×, non-retina)
@1× device: 1pt = 1 physical pixel
@2× device: 1pt = 2 physical pixels
@3× device: 1pt = 3 physical pixels
Figma @1× design: 1 Figma px = 1 iOS pt (1:1 mapping)
```

**Cross-platform conversion matrix from Figma @1×:**
| Target | Value |
|--------|-------|
| CSS px | 1px |
| Android dp | 1dp |
| Android sp (fonts) | 1sp |
| iOS pt | 1pt |
| CSS rem (fonts, base=16px) | 0.0625rem |

Design at @1× in Figma → all platform conversions are 1:1 (no arithmetic needed). This is the canonical design convention for design system token pipelines.

## Anti-Patterns to Avoid

- **Generating palette steps directly in HSL and expecting uniform perceived contrast**: HSL's S/L channels are not perceptually uniform — two colors with identical S and L but different H can look dramatically different in perceived lightness (§2), so a step function like `ΔL = 10% per step` in HSL produces visibly uneven palettes; only OKLCH's L channel is true perceptual lightness, and algorithmic palette generation must happen there before converting to sRGB for storage.
- **Storing generated colors as OKLCH strings directly in `$value` for broad tooling compatibility**: the recommended pipeline (§2) is generate-in-OKLCH, store-in-sRGB — most current DTCG-conformant tooling and downstream platforms expect sRGB hex/rgba for universal support, so skipping the OKLCH→OKLab→XYZ→linear RGB→sRGB conversion chain and shipping raw OKLCH values risks silent rendering failures in tools that only parse hex.
- **Resolving token aliases without running Kahn's algorithm first**: M4's DAG model exists because `{token.path}` references can form cycles — resolving tokens in file-declaration order (rather than topological order) instead of detecting `in_degree(v) > 0` remainders after Kahn's algorithm can either silently resolve a partial/incorrect value or infinite-loop on a cyclic reference the DTCG 2025.10 spec requires to be treated as a hard error.
- **Building deep alias chains without memoization**: M4 notes chains beyond ~10 hops degrade resolution performance without caching — resolving each token's full dependency chain from scratch on every lookup turns an O(V+E) amortized graph resolution into repeated O(chain depth) work per token, which compounds badly across a large token set with many semantic→primitive alias layers.
- **Treating Style Dictionary v3 config syntax as forward-compatible with v4**: §5 states v4 is a near-complete rewrite and v3 config format does not work in v4 — carrying over a v3 `sd.config.js` (or assuming its transform/format names still apply) produces a pipeline that fails outright rather than degrading gracefully, since v4's native DTCG `$value`/`$type` handling is architecturally different from v3's custom token format.
- **Applying all N_tokens × T × P × F transforms sequentially instead of exploiting platform parallelism**: M5's cost model shows wall-clock time can be `max(T_platform_i) + overhead` rather than `Σ(T_platform_i)` when platforms run as async functions in parallel — a pipeline that processes CSS, Android, iOS, and Compose outputs one after another pays the full sum unnecessarily, especially costly as N_tokens or the platform count grows.
- **Assuming Figma's `@1×` design convention makes all cross-platform unit math a no-op**: M6's 1:1 conversion matrix (CSS px, Android dp, Android sp, iOS pt) holds specifically for values designed at Figma `@1×` — reusing the same numeric token value for a design authored at a different Figma scale factor, or for font tokens where Android's sp must additionally track the user's accessibility `font_scale_factor`, silently breaks the "no arithmetic needed" assumption the convention depends on.
- **Ignoring VariableScope when mapping Figma variables to DTCG `$type`**: §6's export path maps `resolvedType` (COLOR, FLOAT, STRING, BOOLEAN) to a DTCG type, but VariableScope carries finer intent (e.g., FONT_SIZE) that a naive resolvedType-only mapping loses — a FLOAT variable scoped to font sizing exported as generic `dimension` instead of `fontSize` breaks downstream typography-specific tooling that filters on `$type`.

## India-Specific Layer

**RPwD Act 2016 §40 (Accessibility Standards):**
The Central Government may specify standards for accessibility in ICT products. WCAG 2.1 AA is the enforced reference standard in India. Color tokens must satisfy minimum contrast ratios:
- 4.5:1 for normal text (AA)
- 3:1 for large text (>18px or >14px bold) and UI components (AA)
Font-size tokens must encode minimum 14px for body text. Design token pipelines must include automated WCAG 2.1 AA contrast validation as a blocking CI gate for Indian government portals.

**Digital India Design System (DIDS) — NIC/MeitY:**
Official token naming and color system for GOV.IN portals. DIDS token format: [UNVERIFIED — whether W3C DTCG-compliant or custom JSON schema; synthesis agent Search 1 required before targeting DIDS format]. DIDS primary blue is #1f4e8a. Token pipelines targeting Indian government portals should validate output against DIDS color and spacing specifications.

**GIGW v3.0 (NIC/MeitY) — Typography and Multi-Script Requirements:**
Government web properties must include Devanagari font stack for Hindi/regional language portals. The `fontFamily` token for Indian government portals must include: `"Noto Sans Devanagari", "Mangal", "Kokila", sans-serif`. GIGW specifies minimum font sizes and line-height requirements for accessibility. [Exact GIGW chapter/section: CONFIDENCE: MED — confirm from official NIC/MeitY GIGW v3.0 document.]

**BIS IS 16333 (Parts 1–4) — Unicode for Indian Languages:**
Bureau of Indian Standards standard for Unicode encoding of Indian scripts. Part 2: Devanagari encoding; Part 3: Devanagari rendering requirements. Typography tokens for multi-script UI must specify Devanagari-capable font families. Exact section applicability to DTCG token definitions: [CONFIDENCE: MED — awaiting synthesis agent Search 3 confirmation.]

## Response Rules

- Always reference W3C DTCG 2025.10 (first stable version, October 28 2025) as the format standard. Do not call it a "W3C Standard" — it is a Community Group publication (not on the W3C Standards Track).
- Always perform topological sort (Kahn's algorithm) before resolving alias references. Report cycles as errors with the full cycle path before any resolution attempt.
- Always validate color token contrast ratios against RPwD Act 2016 requirements (WCAG 2.1 AA minimum) when generating color palettes for Indian government or public-sector portals.
- Use OKLCH for algorithmic palette generation (perceptually uniform spacing). Convert to sRGB hex for DTCG `$value` storage — sRGB is the universal DTCG color format.
- Specify Style Dictionary v4 (not v3) for all new pipeline implementations. Flag breaking changes from v3 when assisting migration: config format is incompatible between v3 and v4.

## What Not to Do

- Do not use HSL for generating accessible color palettes — HSL is not perceptually uniform; equal chroma and hue steps in HSL produce wildly varying perceived color differences. Use OKLCH instead.
- Do not call W3C DTCG 2025.10 a "W3C Standard" — it is a Community Group publication; stable and production-grade, but not on the W3C Recommendation track.
- Do not create circular token references — they produce infinite resolution loops. Always validate the token graph for cycles using Kahn's algorithm before committing to the repository.
- Do not use Style Dictionary v3 config format with Style Dictionary v4 — the config schema is incompatible; migration requires rewriting platform definitions and updating transform references.
- Do not embed raw hex color values in semantic or component tokens — use DTCG aliases to primitive color tokens. Raw values violate the single-source-of-truth principle and break dark mode alias chains.

## Output Expectations

Responses provide:
- Complete DTCG 2025.10 token schema examples with all token types (primitive, semantic, composite)
- Step-by-step color space conversion code (sRGB → OKLCH, OKLCH → sRGB, HSL → RGB)
- Modular scale calculation tables for common ratios
- M1–M6 full mathematical derivations with all formulas and proofs
- Style Dictionary v4 configuration with CSS, Android, iOS, and Compose platform outputs
- Figma Variables export → DTCG transformation workflow with mode-to-token-set mapping
- Automated WCAG 2.1 AA contrast validation code for color token pipelines
- India compliance checklist (RPwD §40, DIDS, GIGW, BIS IS 16333)

## Skill Scope

**In scope:** W3C DTCG 2025.10 format, color space mathematics (sRGB/HSL/OKLCH), typography scale generation, 8-point grid math, token DAG resolution with cycle detection, Style Dictionary v4, Figma Variables → DTCG pipeline, multi-platform unit conversion math, India accessibility token requirements.

**Out of scope:** Multi-platform output deployment (see figma-multiplatform-tokens-core), REST API authentication for token fetching (see figma-rest-api-core), code generation from tokens (see figma-codegen-core), CI/CD pipeline orchestration (see figma-ci-cd-pipeline-core), APCA contrast computation (see figma-ai-automation-core).

## Version: 1.1 — Added Anti-Patterns to Avoid section (HSL palette generation, OKLCH storage compatibility, DAG cycle resolution, alias-chain memoization, Style Dictionary v3→v4 config incompatibility, platform-parallel transform cost, Figma scale-factor assumptions, VariableScope-aware type mapping)
