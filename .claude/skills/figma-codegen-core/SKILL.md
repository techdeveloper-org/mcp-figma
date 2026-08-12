---
name: figma-codegen-core
description: "Provides complete algorithms for generating production-quality React/TypeScript/CSS code from Figma designs — Auto Layout to Flexbox/Grid mapping, variant Cartesian product enumeration, responsive breakpoint interpolation, prop type inference, and generated code complexity estimation. Use when implementing design-to-code pipelines, Figma Code Connect integrations, or automated component scaffolding from design files. Keywords: figma to react code generation, auto layout to flexbox, figma variant codegen, design to typescript, responsive code generation figma, figma component code, figma css grid generation"
allowed-tools: Read,Glob,Grep,Bash,Edit,Write
user-invocable: true
---


<!-- generated-by: claude-global-library/tools/project_sync -->
<!-- source: skills/figma-codegen-core/SKILL.md -- edit the library, then re-run sync_project.py -->

# figma-codegen-core

## Description

Complete algorithms for generating production-quality React/TypeScript/CSS code from Figma designs. Covers Auto Layout to Flexbox/Grid mapping, variant Cartesian product enumeration, responsive breakpoint interpolation, TypeScript prop type inference, Code Connect integration, and generated code complexity estimation with McCabe and Halstead metrics.

## 1. Auto Layout to Flexbox/Grid Mapping

Figma Auto Layout properties map deterministically to CSS Flexbox.

**Direction mapping:**
| Figma `layoutMode` | CSS |
|---------------------|-----|
| `HORIZONTAL` | `flex-direction: row` |
| `VERTICAL` | `flex-direction: column` |

**Primary axis alignment (`primaryAxisAlignItems`):**
| Figma Value | CSS |
|-------------|-----|
| `MIN` | `justify-content: flex-start` |
| `CENTER` | `justify-content: center` |
| `MAX` | `justify-content: flex-end` |
| `SPACE_BETWEEN` | `justify-content: space-between` |

**Cross axis alignment (`counterAxisAlignItems`):**
| Figma Value | CSS |
|-------------|-----|
| `MIN` | `align-items: flex-start` |
| `CENTER` | `align-items: center` |
| `MAX` | `align-items: flex-end` |
| `BASELINE` | `align-items: baseline` |

**Sizing mode per child (`layoutSizingHorizontal` / `layoutSizingVertical`):**
| Figma Value | CSS |
|-------------|-----|
| `FIXED` | `width: {value}px` (explicit) |
| `HUG` | No explicit size (content-determined) |
| `FILL` | `flex: 1 1 0` (fills available space) |

**Gap:** `itemSpacing` → `gap: {value}px`
**Padding:** `paddingTop`, `paddingRight`, `paddingBottom`, `paddingLeft` → CSS `padding`

**Min/max constraints:**
- `minWidth` → `min-width: {value}px; flex-grow: 1`
- `maxWidth` → `max-width: {value}px`
- `minHeight`, `maxHeight` → same pattern for height
- Aspect ratio: `aspectRatio` (Figma) → `aspect-ratio: W/H` (CSS Level 4)

**Layout Grid → CSS Grid:**
- Count-based equal columns: `grid-template-columns: repeat(n, 1fr)`
- Fixed column width: `grid-template-columns: repeat(auto-fill, minmax({width}px, 1fr))`
- Fixed count + stretch: `grid-template-columns: repeat(n, 1fr); gap: {gutter}px`

## 2. Component Set Variants and Prop Interface Generation

**ComponentSet structure:** A ComponentSet node contains multiple Component children. Each component is identified by variant property values. Example: `Size=Small, Theme=Primary, State=Default` identifies one component within the set.

**Prop type inference rules:**
| Property Pattern | TypeScript Type |
|-----------------|-----------------|
| 2 values: True/False, On/Off, Yes/No | `boolean` |
| 2+ string values | `'value1' \| 'value2' \| ...` (literal union) |
| TEXT node content | `string` |
| BOOLEAN variable bound | `boolean` |
| FLOAT variable bound | `number` |
| COLOR variable bound | `string` (hex/rgba) |
| Nested Component instance | `React.ReactNode` |
| Visibility toggle | `boolean` |

**Generated interface example:**
```typescript
interface ButtonProps {
  size: 'sm' | 'md' | 'lg';
  variant: 'primary' | 'secondary' | 'ghost';
  isDisabled?: boolean;  // optional: absent in some variants
  children: React.ReactNode;
}
```

**Prop name normalization:** Figma property names → camelCase. Strip spaces and special characters. Preserve boolean prefixes: "Is Disabled" → `isDisabled`, "Has Icon" → `hasIcon`.

**Discriminated unions:** Required when variant combinations have structurally incompatible prop shapes (e.g., icon-only variant has no `children` prop). Use variant property value as discriminant:
```typescript
type ButtonProps =
  | { variant: 'icon-only'; icon: React.ReactNode }
  | { variant: 'text'; children: React.ReactNode; icon?: React.ReactNode };
```

**Code Connect integration (GA 2024):**
```typescript
// Button.figma.connect.tsx
import figma from '@figma/code-connect';
import { Button } from './Button';

figma.component(
  'https://www.figma.com/design/FILE_KEY/File?node-id=NODE_ID',
  Button,
  {
    props: {
      size: figma.enum('Size', { Small: 'sm', Medium: 'md', Large: 'lg' }),
      isDisabled: figma.boolean('Is Disabled'),
      children: figma.string('Label'),
    },
    example: ({ size, isDisabled, children }) => (
      <Button size={size} isDisabled={isDisabled}>{children}</Button>
    ),
  }
);
```

## 3. Responsive Breakpoint Code Generation

**Breakpoint detection from Figma frames:**
1. Identify frames with different viewport widths (e.g., 375px mobile, 768px tablet, 1440px desktop)
2. Extract property values at each frame width
3. Derive interpolation function between adjacent breakpoints

**Mobile-first media query generation (mandatory for GIGW compliance):**
```css
/* Base: 375px mobile */
.component { font-size: 1rem; }

/* Tablet: ≥768px */
@media (min-width: 768px) {
  .component { font-size: 1.125rem; }
}

/* Desktop: ≥1440px */
@media (min-width: 1440px) {
  .component { font-size: 1.25rem; }
}
```

**Indian government portal breakpoints (GIGW v3.0):**
- 375px (mobile-S, baseline)
- 768px (tablet)
- 1024px (desktop)
- 1440px (large desktop)

**Fluid value using `clamp()`:** Single declaration covers full viewport range without media queries (see M4 for full derivation).

## 4. Prop Type Inference and TypeScript Generation

**TypeSafety scoring:**
```
TypeSafety = strongly_typed_props / total_props
```
- **Strongly typed:** `boolean`, `number`, string literal union, `React.ReactNode`, concrete `ComponentProps<typeof X>`
- **Weakly typed:** `any`, generic `string`, `object`
- Target: TypeSafety ≥ 0.90

**Optional prop inference:**
- If a variant exists without a property value (property absent in some variants) → mark as optional (`prop?: type`)
- If absent in <20% of variants → add a sensible `defaultProps` value

**Coverage scoring:**
```
Coverage(Interface, VariantSet) = count of variants expressible by interface / total variant count
```
Target: Coverage = 1.0. If Coverage < 1.0, add discriminated union members for uncovered variant combinations.

**Generated component structure:**
```typescript
import React from 'react';
import styles from './Button.module.css';  // CSS Modules (no inline styles)

interface ButtonProps {
  size: 'sm' | 'md' | 'lg';
  variant: 'primary' | 'secondary' | 'ghost';
  isDisabled?: boolean;
  children: React.ReactNode;
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
}

export function Button({
  size = 'md',
  variant = 'primary',
  isDisabled = false,
  children,
  onClick,
}: ButtonProps): JSX.Element {
  return (
    <button
      className={`${styles.button} ${styles[size]} ${styles[variant]}`}
      disabled={isDisabled}
      aria-disabled={isDisabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
```

**Storybook story from variant matrix:**
```typescript
// Auto-generated story covering all variants
import type { Meta, StoryObj } from '@storybook/react';
const meta: Meta<typeof Button> = {
  title: 'Components/Button',
  component: Button,
};
export const AllVariants: StoryObj = {
  render: () => (
    <>
      {(['sm', 'md', 'lg'] as const).map(size =>
        (['primary', 'secondary', 'ghost'] as const).map(variant =>
          <Button key={`${size}-${variant}`} size={size} variant={variant}>Label</Button>
        )
      )}
    </>
  ),
};
```

## 5. Figma Code Connect Integration

**Code Connect (GA 2024, actively evolving 2025):** Links Figma components to real production code. Dev Mode displays true-to-production code snippets instead of auto-generated code when Code Connect files are published.

**Supported frameworks:** React, HTML/Web Components, Angular, Vue, SwiftUI, Android Compose.

**CLI publication:**
```bash
npx figma connect publish --token $FIGMA_ACCESS_TOKEN
```

**GitHub Actions workflow (confirmed pattern):**
```yaml
name: Publish Code Connect
on:
  push:
    branches: [main]
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npx figma connect publish --token ${{ secrets.FIGMA_ACCESS_TOKEN }}
```

**Complete end-to-end pattern:**
Figma Design → Tokens Studio → Token Transformer → Style Dictionary v4 → CSS/JSON tokens → React components → Code Connect mapped → `figma connect publish` on PR merge.

## 6. Generated Code Quality Assessment

**McCabe Cyclomatic Complexity target: V(G) ≤ 10**
- V(G) = 1 + count of decision points (if, ternary, `&&`, `||`, switch cases)
- For generated React component: decision points = conditional renders + prop-dependent style conditions

**Minimization strategies:**
- Replace if/else chain for k values with lookup table → saves k−1 decision points
- CSS custom properties eliminate JS conditionals entirely (V(G) contribution = 0)
- Extract variant sub-components for components exceeding 3 major axes

**Halstead volume target: H_V ≤ 3000**
- n₁ = distinct operators, n₂ = distinct operands
- N₁ = total operators, N₂ = total operands
- Volume: H_V = (N₁ + N₂) × log₂(n₁ + n₂)
- Difficulty: H_D = (n₁/2) × (N₂/n₂)
- H_V > 3000 or H_D > 25: split component into sub-components

**Automated measurement:**
- ESLint `complexity` rule → reports V(G)
- `escomplex` npm package → Halstead metrics via AST analysis
- Both integrate into CI quality gate: fail on V(G) > 10 or H_V > 3000

## Deep Mathematical Foundations

### M1: Auto Layout → Flexbox Distribution Algorithm

**FILL child free space allocation:**
```
S_avail = container_width − Σ(fixed_child_widths) − (n_children − 1) × gap
```
Each FILL child receives: `S_avail / n_fill_children` (equal distribution with `flex-grow: 1`).

**Weighted FILL distribution (proportional flex-grow):**
```
child_i_width = S_avail × grow_i / Σ_j grow_j   (∀j ∈ FILL children)
```
CSS encodes these weights directly via `flex-grow: grow_i`.

**Cross-axis FILL:** `align-self: stretch`; effective height = container_height − 2 × padding_cross. FIXED cross-axis overrides stretch.

**SPACE_BETWEEN math:**
When `primaryAxisAlignItems = SPACE_BETWEEN`, the `itemSpacing` value is ignored. The actual gap becomes:
```
gap_eff = (S_avail − Σ child_main_sizes) / (n_children − 1)
```
Edge case: for n_children = 1 with SPACE_BETWEEN → equivalent to CENTER.

**Nested Auto Layout:** Each frame creates an independent flex context. FILL child in outer container propagates as `align-self: stretch` in inner container only if the cross-axis sizing is also FILL; otherwise explicit size applies.

**min/max constraint CSS mapping:**
```
minWidth → min-width: {value}px; flex-grow: 1   (allow growth but not shrink below min)
maxWidth → max-width: {value}px                  (cap growth)
Aspect ratio → aspect-ratio: W/H                 (CSS Level 4)
```

### M2: Variant Matrix Cartesian Product

**Variant space cardinality:**
```
|V| = Π_{i=1}^{n} |P_i|
```
Where n = number of variant properties, |P_i| = number of values for property i.
Example: Size(3) × Variant(3) × State(4) × HasIcon(2) = 72 variants.

**Sparsity ratio:**
```
σ = |designed_variants| / |V|
```
σ < 0.5 → sparse variant matrix → generate only designed prop combinations, not full Cartesian product.

**Boolean collapse rule:**
A property with exactly 2 values where one is the semantic negation of the other (True/False, On/Off, Enabled/Disabled) → collapse to `boolean` prop. Reduces union type to primitive, improves type safety.

**Coverage function:**
```
Coverage(I, V) = |{v ∈ V : I.accepts(v)}| / |V|
```
Where `I.accepts(v)` iff all of v's property values are representable by some legal combination of I's prop types.

**Combinatorial explosion mitigation:**
For |V| > 100 variants: decompose into sub-components per major property axis rather than a single mega-component with deeply nested conditionals. Example: `ButtonBase + SizeWrapper + ThemeWrapper` instead of `Button` with all combinations inline.

### M3: Grid Layout Algorithms (fr Unit + auto-fill/auto-fit)

**fr (fractional) unit resolution:**
```
available_space = container_width − Σ(fixed_track_widths) − Σ(column_gaps)
1fr = available_space / Σ(all_fr_values)
track_i_width = fr_i × 1fr
```

**Figma grid type → CSS mapping:**
| Figma Grid Type | CSS |
|-----------------|-----|
| Count-based (n equal columns) | `grid-template-columns: repeat(n, 1fr)` |
| Fixed column width | `grid-template-columns: repeat(auto-fill, minmax({width}px, 1fr))` |
| Fixed count + gutter | `grid-template-columns: repeat(n, 1fr); column-gap: {gutter}px` |

**auto-fill vs auto-fit:**
- `auto-fill`: creates empty tracks (minimum column count maintained even with fewer items)
- `auto-fit`: collapses empty tracks to 0px width (items stretch to fill)
- Use `auto-fill` when a minimum column count must be maintained; `auto-fit` for wrapping item grids.

**minmax(min, max) track sizing:**
```
track_size = max(min, min(max, available_space / n_tracks))
```
`minmax(200px, 1fr)` ensures minimum 200px per column but expands proportionally.

**Fractional/fixed hybrid:**
`grid-template-columns: 250px 1fr 1fr` — fixed sidebar (250px consumed first) + two equal fluid columns distributing the remainder.

### M4: Breakpoint Interpolation Math (CSS clamp Derivation)

**Two-breakpoint linear interpolation:**
Given (W₁, V₁) = minimum width + value, (W₂, V₂) = maximum width + value:
```
slope m = (V₂ − V₁) / (W₂ − W₁)       [dimensionless, px/px]
intercept = V₁ − m × W₁                 [px]
preferred = intercept + m × viewport_width
CSS: clamp(V₁, calc(intercept_rem + m × 100vw), V₂)
```

**Worked example (font size 16px at 320px → 24px at 1440px):**
```
m = (24 − 16) / (1440 − 320) = 8 / 1120 ≈ 0.00714 px/px
intercept = 16 − 0.00714 × 320 = 16 − 2.286 ≈ 13.714 px
intercept_rem = 13.714 / 16 ≈ 0.857 rem
CSS: clamp(1rem, calc(0.857rem + 0.714vw), 1.5rem)
```

**rem conversion of slope:** slope m is dimensionless (px/px = rem/rem), so `m × 100vw` is correct in both px and rem. Only intercept and clamp bounds need /16 conversion.

**Multi-breakpoint piecewise:** k breakpoints → k−1 clamp segments:
```css
/* 3 breakpoints: mobile, tablet, desktop */
font-size: min(max(clamp(14px, calc(0.875rem + 0.5vw), 18px), 768px-threshold), clamp(18px, calc(1.125rem + 0.25vw), 22px));
```

**Mobile-first requirement (GIGW mandate):** `@media (min-width: W₂)` applies larger-viewport styles. Base (mobile) styles are always the default.

**rem conversion for accessibility:** Convert all px clamp values to rem before encoding. This ensures the font-size respects user-configured browser default font size, satisfying WCAG 1.4.4 (Resize Text).

### M5: Prop Type Inference (Coverage + TypeSafety Scoring)

**Inference rule table:**
| Figma Source | TypeScript Type | Notes |
|-------------|-----------------|-------|
| 2 values: True/False | `boolean` | Collapse to primitive |
| n>2 string values | `'a' \| 'b' \| ...` | Literal union |
| TEXT node | `string` | |
| BOOLEAN variable | `boolean` | |
| FLOAT variable | `number` | |
| COLOR variable | `string` | hex/rgba representation |
| Nested Component | `React.ReactNode \| ComponentProps<typeof X>` | |
| Visibility toggle | `boolean` | |

**Coverage function:**
```
Coverage(I, V) = |{v ∈ V : I.accepts(v)}| / |V|
```
`I.accepts(v)` iff every property value in variant v is representable by a legal combination of interface I's prop types. Target = 1.0 (all variants covered by the interface).

**TypeSafety score:**
```
TypeSafety = |strongly_typed_props| / |total_props|
```
Strongly typed: `boolean`, `number`, literal string union, `React.ReactNode`, concrete `ComponentProps<typeof X>`.
Weakly typed: `any`, generic `string`, `object`.
Target: TypeSafety ≥ 0.90.

**Optional prop rule:**
- If a property is absent in ≥1 variant → mark as optional (`prop?: type`)
- If absent in <20% of variants → add default value in `defaultProps` or destructuring default

**Prop name normalization:**
1. Split Figma property name on spaces, special characters
2. Lowercase first word, capitalize subsequent words (camelCase)
3. Preserve semantic boolean prefix: "Is Disabled" → `isDisabled`, "Has Badge" → `hasBadge`
4. Numbers suffix: "Icon Size 24" → `iconSize24` or extract as enum value

### M6: Code Complexity Estimation (McCabe + Halstead)

**McCabe Cyclomatic Complexity:**
```
V(G) = E − N + 2P
```
Where E = edges, N = nodes, P = connected components in the control flow graph. Simplified:
```
V(G) = 1 + decision_points
decision_points = count(if) + count(ternary) + count(&&) + count(||) + count(switch_cases)
```

**For generated React component:**
- V(G) = 1 + |conditional_renders| + |prop-dependent style conditions|
- Target: V(G) ≤ 10

**Minimization — lookup table replacement:**
```typescript
// Before: 4 if-else → V(G) += 3
const bg = size === 'sm' ? '8px' : size === 'md' ? '12px' : size === 'lg' ? '16px' : '0';

// After: lookup table → V(G) += 0
const paddingMap = { sm: '8px', md: '12px', lg: '16px' } as const;
const bg = paddingMap[size];
```
V(G) reduction per lookup table replacement: k−1 (for k values).

**Halstead metrics derivation:**
```
n₁ = distinct operators in the component
n₂ = distinct operands (variables, literals)
N₁ = total operator occurrences
N₂ = total operand occurrences

Program length:   N = N₁ + N₂
Vocabulary:       n = n₁ + n₂
Volume:           H_V = N × log₂(n)
Difficulty:       H_D = (n₁/2) × (N₂/n₂)
Effort:           H_E = H_D × H_V
```

**Target thresholds:**
- H_V ≤ 3000 per component
- H_D ≤ 25
- Above threshold: split into sub-components

## Anti-Patterns to Avoid

- **Mapping `FILL` sizing mode to `flex: 1 1 0` without also emitting a `min-width`/`min-height` constraint**: §1's mapping table treats `FILL` as "fills available space," but flexbox's default `min-width: auto` can still let a filled child overflow its content — Figma's Auto Layout resolves this implicitly via its own layout engine, so a literal `flex: 1 1 0` translation without an explicit min-size can produce overflow the original design never had.
- **Generating a single flat union type instead of a discriminated union for structurally incompatible variants**: §2 explicitly calls out that an icon-only variant with no `children` prop needs a discriminant-keyed union — collapsing all variants into one interface with every prop marked optional (rather than a `variant: 'icon-only' | 'text'` discriminant) loses the compile-time guarantee that icon-only usage can't accidentally omit the icon or supply children that will never render.
- **Inflating the TypeSafety score by widening prop types to `string`/`any` instead of narrowing to literal unions**: `TypeSafety = strongly_typed_props / total_props` (§4) is gameable — a generic `string` prop count toward `total_props` but not `strongly_typed_props`, so the honest fix is deriving the literal union from the actual variant values, not loosening the type to make the ratio look acceptable without doing so.
- **Reporting Coverage = 1.0 without actually enumerating uncovered variant combinations**: §4's Coverage formula requires checking every variant combination is expressible by the generated interface — a discriminated union that only covers the variant combinations seen in the current file (rather than the full cross-product Figma's ComponentSet defines) can silently under-report Coverage < 1.0 as if it were complete.
- **Generating desktop-first media queries for GIGW-governed government portal components**: §3 mandates mobile-first (`min-width` queries ascending from the 375px baseline) for GIGW v3.0 compliance — a desktop-first generation (`max-width` queries descending) inverts the cascade order and, more importantly, violates the specific compliance requirement this skill flags as mandatory for Indian government portal breakpoints.
- **Treating McCabe V(G) ≤ 10 as satisfied by moving conditionals into nested helper functions without measuring the caller**: V(G) = 1 + decision points counts branches in the function actually being measured — extracting conditionals into an unmeasured sibling function to keep the top-level component's reported V(G) under 10 doesn't reduce the codebase's actual decision-point density, it just moves where the complexity is hidden from the CI gate.
- **Using an if/else chain for a variant property with many string values instead of a lookup table**: §6's minimization strategy notes a lookup table saves k−1 decision points versus an if/else chain of the same k values — for a `size` or `variant` prop with 5+ possible values, the if/else form alone can push V(G) past the ≤10 threshold that a `styles[variant]` object-lookup would have kept well under.
- **Publishing Code Connect mappings for components whose Figma variant structure has since diverged from production code**: §5's entire value proposition (true-to-production Dev Mode snippets instead of auto-generated code) depends on the mapping staying current — a stale Code Connect file for a component whose props were refactored in code silently shows designers an incorrect "true-to-production" snippet, which is more actively misleading than falling back to auto-generated code would have been.

## India-Specific Layer

**BIS IS 16333 (Parts 1–4) — Unicode for Indian Languages:**
Generated code for Indian government portals must include Devanagari-capable font stacks:
```css
font-family: 'Noto Sans Devanagari', 'Mangal', 'Kokila', sans-serif;
```
Part 2 covers Devanagari Unicode encoding; Part 3 covers rendering requirements. Exact section applicability to generated code font-family declarations: [CONFIDENCE: MED — awaiting synthesis agent Search 3 confirmation.]

**GIGW v3.0 — Mobile-First and Responsive Requirements:**
Generated code for Indian government portals must use mobile-first media queries (`min-width`, not `max-width`). Standard GIGW breakpoints: 375px, 768px, 1024px, 1440px. [Exact GIGW section for responsive web requirements: CONFIDENCE: MED — confirm from official NIC/MeitY GIGW v3.0 document.]

**RPwD Act 2016 §45 — Digital Accessibility:**
Generated code must include ARIA roles, labels, tabIndex, and focus management for all interactive components. Accessibility attributes must be generated alongside visual properties — not as optional post-processing step. Minimum requirements per component type:
- `<button>`: `type="button"`, `aria-disabled={isDisabled}`, `aria-label` if icon-only
- `<input>`: `aria-label` or `aria-labelledby`, `aria-required`, `aria-invalid`
- `<a>`: `aria-label` if link text is non-descriptive
- Modal/Dialog: `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, focus trap

**Digital India Design System (DIDS) — NIC/MeitY:**
Generated React components for Indian government portals must match DIDS component API signatures (prop names, component hierarchy). DIDS component library API: [CONFIDENCE: MED — exact specification format pending synthesis agent Search 1.]

## Response Rules

- Always generate mobile-first CSS (`min-width` media queries) as the default output when generating responsive code for Indian government portals or when no client preference is specified.
- Always include proper TypeScript prop types — never generate `any`-typed props without explicitly noting the type safety gap and providing a path to strongly-typed alternatives. Target TypeSafety ≥ 0.90.
- Always include Devanagari font fallbacks in `font-family` declarations for multi-script Indian design system code.
- Always compute and report McCabe cyclomatic complexity for generated components. Flag V(G) > 10 with a concrete refactoring recommendation (lookup table, CSS custom properties, or sub-component extraction).
- Always map Figma FILL sizing mode to `flex: 1 1 0` (not `flex: auto`). `flex: auto` implies `flex-basis: auto` (uses content size as basis), which does not replicate FILL behavior.

## What Not to Do

- Do not generate the full Cartesian variant space as a discriminated union type alias — generate separate boolean/string literal props and use discriminated unions only for structurally incompatible variant shapes. Full Cartesian types with 72+ members are unmaintainable.
- Do not use `max-width` media queries for responsive breakpoints — mobile-first (`min-width`) is required by GIGW v3.0 for Indian government portals and is the industry standard.
- Do not ignore Figma's `minWidth`/`maxWidth` node constraints — they must be mapped to CSS `min-width`/`max-width`; omitting them produces layouts that overflow at narrow viewports or collapse unexpectedly.
- Do not generate inline styles for variant-dependent properties — use CSS Modules, CSS custom properties, or Tailwind utility classes. Inline styles prevent theming, increase specificity conflicts, and block CSS-based dark mode.
- Do not omit ARIA attributes from generated interactive components — buttons, links, and inputs must always receive appropriate `role`, `aria-*`, and focus management attributes to meet RPwD Act 2016 §45 accessibility requirements.

## Output Expectations

Responses provide:
- Complete Auto Layout → Flexbox/Grid CSS mapping tables with edge cases
- TypeScript component interfaces with full prop types and JSDoc comments
- React component code with FILL → flex-grow mapping, ARIA attributes, CSS Modules
- Responsive `clamp()` CSS with full mathematical derivation
- Variant prop interface examples with Coverage and TypeSafety scores
- Code Connect `.figma.connect.tsx` file templates for all supported frameworks
- McCabe complexity analysis and Halstead volume for generated components
- M1–M6 full mathematical derivations with all formulas and proofs

## Skill Scope

**In scope:** Auto Layout to Flexbox/Grid mapping, variant Cartesian product enumeration, TypeScript prop type inference with Coverage/TypeSafety scoring, responsive clamp interpolation, Code Connect integration, generated code complexity (McCabe V(G), Halstead H_V), Devanagari font stack requirements, ARIA attribute generation.

**Out of scope:** Design token schema and transform pipelines (see design-tokens-automation-core), REST API authentication (see figma-rest-api-core), CI/CD orchestration (see figma-ci-cd-pipeline-core), plugin/widget development (see figma-plugin-widget-core), AI-powered code generation quality scoring (see figma-ai-automation-core), multi-platform Android/iOS output (see figma-multiplatform-tokens-core).

## Version: 1.1 — Added Anti-Patterns to Avoid section (FILL sizing overflow, discriminated-union collapsing, TypeSafety score gaming, Coverage under-reporting, desktop-first GIGW violation, hidden-complexity V(G) gaming, if/else vs lookup-table complexity, stale Code Connect mappings)
