# DTCG Token Pipeline Specification — Phase 3.4–3.5

**Document:** token-pipeline-spec.md
**Status:** Active
**Owner:** figma-automation-agent (SDLC pipeline)
**Last Updated:** 2026-05-28

---

## 1. Overview

Phase 3.4–3.5 of the SDLC pipeline converts raw Figma file data into platform-ready design token artifacts. After the Figma plugin creates the file and populates it with the design system (Phase 3.3), the `figma-automation-agent` drives a sequence of `mcp-figma` tool calls that extract, validate, transform, and output tokens in four target formats: DTCG 2025.10 JSON, CSS custom properties, Android XML resources, and Swift enum constants.

The pipeline calls `mcp-figma` tools directly over the MCP stdio transport. Each tool call is synchronous from the agent's perspective. Accessibility validation (APCA + WCAG) runs in parallel after token extraction completes, before any platform-specific output is written. All output files land in `docs/phase-3-design/` and are registered in the output file registry (§6).

This specification is the authoritative reference for the agent's behaviour in Phases 3.4 and 3.5. The design_spec.schema.json (at `plugin/schema/design_spec.schema.json`) is the authoritative reference for the input contract.

---

## 2. mcp-figma Tool Call Sequence (Phase 3.4)

The agent executes the following nine tool calls in order. Steps 7–9 may execute concurrently after Step 3 completes.

### Step 1 — Verify Connectivity

**Tool:** `figma_health_check`
**Parameters:** none
**Expected result:** `{ "status": "ok", "token_valid": true }`
**On failure:** Abort Phase 3.4; emit `ERROR: Figma API token invalid or unreachable` to pipeline log.

### Step 2 — Verify File Created Correctly

**Tool:** `figma_get_file_info`
**Parameters:** `{ "file_key": "<FIGMA_FILE_KEY from design_spec.json context>" }`
**Expected result:** Object containing `name`, `version`, `lastModified`, and `pages` (array with at least one entry). The agent asserts `pages.length >= 1` and that `name` matches `design_spec.json → project`.
**On failure:** Log a warning and continue; Phase 3.4 is non-blocking on file name mismatch.

### Step 3 — Extract Design Tokens

**Tool:** `figma_extract_design_tokens`
**Parameters:** `{ "file_key": "<FIGMA_FILE_KEY>" }`
**Expected result:** DTCG-compatible token tree (see §3). This is the canonical token dataset used by all subsequent steps. The agent persists the response as `docs/phase-3-design/design_tokens.dtcg.json`.
**On failure:** Abort Phase 3.4.

### Step 4 — Generate CSS Tokens

**Tool:** `generate_css_tokens`
**Parameters:** `{ "file_key": "<FIGMA_FILE_KEY>" }`
**Expected result:** CSS string containing a `:root {}` block with `--color-*` and `--spacing-*` custom properties (see §4). Persisted as `docs/phase-3-design/tokens_css.css`.

### Step 5 — Generate Android Tokens

**Tool:** `generate_android_tokens`
**Parameters:** `{ "file_key": "<FIGMA_FILE_KEY>" }`
**Expected result:** Android XML `<resources>` document with `<dimen>` entries using `dp` for spacing and `sp` for typography font sizes (see §4). Persisted as `docs/phase-3-design/tokens_android.xml`.

### Step 6 — Generate iOS Tokens

**Tool:** `generate_ios_tokens`
**Parameters:** `{ "file_key": "<FIGMA_FILE_KEY>" }`
**Expected result:** Swift source file declaring `enum DesignTokens` with nested `Color`, `Spacing`, and `Typography` enums, each containing `static let` constants (see §4). Persisted as `docs/phase-3-design/tokens_ios.swift`.

### Step 7 — APCA Contrast per Color Pair

**Tool:** `compute_apca_contrast`
**Parameters (per pair):** `{ "foreground": "<hex>", "background": "<hex>" }`
**Invocation:** Called once for every foreground × background combination derived from `design_system.colors` in design_spec.json. The agent iterates all pairs where `foreground != background`.
**Expected result per call:** `{ "Lc": <number> }`. The agent collects all results into `accessibility_report.json`.

### Step 8 — WCAG Contrast per Color Pair

**Tool:** `compute_wcag_contrast`
**Parameters (per pair):** `{ "foreground": "<hex>", "background": "<hex>" }`
**Invocation:** Same color pair loop as Step 7. May execute concurrently with Step 7.
**Expected result per call:** `{ "ratio": <number>, "AA_normal": <boolean>, "AAA_normal": <boolean> }`. Results merged into `accessibility_report.json`.

### Step 9 — Accessible Color Pair Discovery

**Tool:** `get_accessible_color_pairs`
**Parameters:** `{ "file_key": "<FIGMA_FILE_KEY>" }`
**Expected result:** List of `{ foreground, background, wcag_ratio, apca_Lc }` objects for all pairs that meet the WCAG AA threshold (≥4.5:1 for normal text). Appended to `accessibility_report.json` as `accessible_pairs` key.

---

## 3. DTCG 2025.10 Token Format

The canonical token output stored in `design_tokens.dtcg.json` follows the W3C Design Token Community Group 2025.10 specification. Each token has `$type`, `$value`, and an optional `$description`.

```json
{
  "color": {
    "primary": {
      "$type": "color",
      "$value": "#2563EB",
      "$description": "Primary brand color"
    },
    "surface": {
      "$type": "color",
      "$value": "#F8FAFC",
      "$description": "Surface / background color"
    },
    "error": {
      "$type": "color",
      "$value": "#DC2626",
      "$description": "Error state color"
    }
  },
  "spacing": {
    "spacing-0": { "$type": "dimension", "$value": "4px",  "$description": "Spacing step 0" },
    "spacing-1": { "$type": "dimension", "$value": "8px",  "$description": "Spacing step 1" },
    "spacing-2": { "$type": "dimension", "$value": "12px", "$description": "Spacing step 2" },
    "spacing-3": { "$type": "dimension", "$value": "16px", "$description": "Spacing step 3" },
    "spacing-4": { "$type": "dimension", "$value": "24px", "$description": "Spacing step 4" },
    "spacing-5": { "$type": "dimension", "$value": "32px", "$description": "Spacing step 5" },
    "spacing-6": { "$type": "dimension", "$value": "48px", "$description": "Spacing step 6" }
  },
  "typography": {
    "heading-1": {
      "fontFamily": { "$type": "fontFamily", "$value": "Inter" },
      "fontSize":   { "$type": "dimension",  "$value": "32px" },
      "fontWeight": { "$type": "fontWeight",  "$value": 700 }
    },
    "body": {
      "fontFamily": { "$type": "fontFamily", "$value": "Inter" },
      "fontSize":   { "$type": "dimension",  "$value": "16px" },
      "fontWeight": { "$type": "fontWeight",  "$value": 400 }
    }
  }
}
```

Spacing token keys are auto-generated as `spacing-N` where N is the zero-based index into the `design_system.spacing` array. Color token keys and typography token keys mirror the keys in `design_spec.json` exactly.

---

## 4. Platform-Specific Output Formats

### CSS (`tokens_css.css`)

All tokens are emitted as CSS custom properties inside a single `:root {}` block. Naming convention: `--{category}-{token-name}`.

```css
/* Generated by figma-automation-agent — do not edit manually */
:root {
  /* Colors */
  --color-primary: #2563EB;
  --color-surface: #F8FAFC;
  --color-error: #DC2626;

  /* Spacing */
  --spacing-0: 4px;
  --spacing-1: 8px;
  --spacing-2: 12px;
  --spacing-3: 16px;
  --spacing-4: 24px;
  --spacing-5: 32px;
  --spacing-6: 48px;

  /* Typography */
  --typography-heading-1-font-family: Inter;
  --typography-heading-1-font-size: 32px;
  --typography-heading-1-font-weight: 700;
  --typography-body-font-family: Inter;
  --typography-body-font-size: 16px;
  --typography-body-font-weight: 400;
}
```

### Android (`tokens_android.xml`)

Spacing values use `dp` (density-independent pixels). Typography font size values use `sp` (scale-independent pixels). Color values use Android `#AARRGGBB` format (fully opaque: `FF` alpha prefix). Resource name convention: `{category}_{token_name}` with hyphens replaced by underscores.

```xml
<?xml version="1.0" encoding="utf-8"?>
<!-- Generated by figma-automation-agent — do not edit manually -->
<resources>
    <!-- Colors -->
    <color name="color_primary">#FF2563EB</color>
    <color name="color_surface">#FFF8FAFC</color>
    <color name="color_error">#FFDC2626</color>

    <!-- Spacing -->
    <dimen name="spacing_0">4dp</dimen>
    <dimen name="spacing_1">8dp</dimen>
    <dimen name="spacing_2">12dp</dimen>
    <dimen name="spacing_3">16dp</dimen>
    <dimen name="spacing_4">24dp</dimen>
    <dimen name="spacing_5">32dp</dimen>
    <dimen name="spacing_6">48dp</dimen>

    <!-- Typography font sizes (sp) -->
    <dimen name="typography_heading_1_font_size">32sp</dimen>
    <dimen name="typography_body_font_size">16sp</dimen>
</resources>
```

### iOS Swift (`tokens_ios.swift`)

A top-level `enum DesignTokens` (caseless, namespace-only) contains nested enums for `Color`, `Spacing`, and `Typography`. All properties are `static let`. Color constants use `UIColor(red:green:blue:alpha:)` with values normalised to the 0–1 range from hex.

```swift
// Generated by figma-automation-agent — do not edit manually
import UIKit

enum DesignTokens {

    enum Color {
        static let primary = UIColor(red: 0.145, green: 0.388, blue: 0.922, alpha: 1.0)
        static let surface = UIColor(red: 0.973, green: 0.980, blue: 0.988, alpha: 1.0)
        static let error   = UIColor(red: 0.863, green: 0.149, blue: 0.149, alpha: 1.0)
    }

    enum Spacing {
        static let step0: CGFloat =  4
        static let step1: CGFloat =  8
        static let step2: CGFloat = 12
        static let step3: CGFloat = 16
        static let step4: CGFloat = 24
        static let step5: CGFloat = 32
        static let step6: CGFloat = 48
    }

    enum Typography {
        enum HeadingOne {
            static let fontFamily = "Inter"
            static let fontSize: CGFloat = 32
            static let fontWeight = UIFont.Weight.bold        // 700
        }
        enum Body {
            static let fontFamily = "Inter"
            static let fontSize: CGFloat = 16
            static let fontWeight = UIFont.Weight.regular     // 400
        }
    }
}
```

---

## 5. Accessibility Validation (APCA + WCAG)

### APCA v0.0.98G Coefficients

The `compute_apca_contrast` tool implements the APCA 0.0.98G algorithm with the following coefficients:

| Coefficient | Value | Role |
|-------------|-------|------|
| `APCA_Sa` | 0.55 | Soft-clamp exponent for light backgrounds |
| `APCA_Sb` | 0.22 | Soft-clamp exponent for dark backgrounds |
| `APCA_Sc` | 0.20 | Scale factor offset |

The Lc (lightness contrast) value is a signed number; absolute value is used for threshold comparisons.

### Minimum Lc Thresholds (RPwD Act 2016 §40 / GIGW v3.0)

| Content Type | Minimum |Lc| |
|--------------|-----------------|
| Body text (< 18pt normal, < 14pt bold) | ≥ 60 |
| UI components, icons, placeholder text | ≥ 45 |
| Large text (≥ 18pt normal or ≥ 14pt bold) | ≥ 30 |

### WCAG 2.1 Minimum Ratios

| Content Type | Minimum Ratio |
|--------------|---------------|
| Normal text (< 18pt regular, < 14pt bold) — AA | 4.5:1 |
| Large text (≥ 18pt regular or ≥ 14pt bold) — AA | 3.0:1 |
| Normal text — AAA | 7.0:1 |
| Large text — AAA | 4.5:1 |
| UI components and graphical objects — AA | 3.0:1 |

### Output Structure

Results are saved to `docs/phase-3-design/accessibility_report.json` with the following top-level structure:

```json
{
  "generated_at": "<ISO 8601 timestamp>",
  "color_pairs": [
    {
      "foreground": "#2563EB",
      "background": "#F8FAFC",
      "apca_Lc": 72.4,
      "apca_pass_body": true,
      "apca_pass_ui": true,
      "wcag_ratio": 5.3,
      "wcag_AA_normal": true,
      "wcag_AAA_normal": false,
      "wcag_AA_large": true
    }
  ],
  "accessible_pairs": [
    { "foreground": "#2563EB", "background": "#F8FAFC", "wcag_ratio": 5.3, "apca_Lc": 72.4 }
  ],
  "summary": {
    "total_pairs_tested": 6,
    "apca_pass_body": 4,
    "apca_fail_body": 2,
    "wcag_AA_pass": 5,
    "wcag_AA_fail": 1
  }
}
```

Any color pair that fails either APCA (body) or WCAG AA normal-text thresholds is flagged with a `"fail_reason"` field and surfaced as a pipeline warning — Phase 3.5 does not block on accessibility failures, but the CI job associated with Phase 3.5 marks the accessibility gate as `WARN`.

---

## 6. Output File Registry

All nine files produced by Phases 3.4–3.5 are written to `docs/phase-3-design/`. The table below lists each file, the tool or step that creates it, and the execution order.

| Order | File | Created By | Description |
|-------|------|------------|-------------|
| 1 | `design_tokens.dtcg.json` | `figma_extract_design_tokens` (Step 3) | DTCG 2025.10 canonical token tree |
| 2 | `tokens_css.css` | `generate_css_tokens` (Step 4) | CSS custom properties (`:root {}` block) |
| 3 | `tokens_android.xml` | `generate_android_tokens` (Step 5) | Android XML `<resources>` (`dp` / `sp` / `#AARRGGBB`) |
| 4 | `tokens_ios.swift` | `generate_ios_tokens` (Step 6) | Swift `enum DesignTokens` with `static let` constants |
| 5 | `accessibility_report.json` | `compute_apca_contrast` + `compute_wcag_contrast` + `get_accessible_color_pairs` (Steps 7–9) | Per-pair APCA Lc and WCAG ratio results plus accessible-pair list |
| 6 | `design_spec.json` | Phase 3.3 (plugin, pre-pipeline) | Input to Phase 3.4; validated against `plugin/schema/design_spec.schema.json` |
| 7 | `token-pipeline-spec.md` | Phase 3.3 (this document) | Pipeline specification (human reference) |
| 8 | `design_spec.schema.json` (copy) | Phase 3.3 bootstrap | Reference copy of the JSON Schema placed here for archive |
| 9 | `phase3-pipeline-summary.json` | Phase 3.5 (agent finalisation) | Machine-readable summary: file list, token counts, APCA/WCAG pass rates, timestamp |

---

## 7. India Regulatory Compliance

### DPDP Act 2023 — Data Protection

The `design_spec.json` produced in Phase 3.3 must not contain any Personal Data as defined under the Digital Personal Data Protection Act, 2023. Specifically:

- Screen names, component names, and color token names must be semantic labels (e.g. `primary`, `Login`) — not user names, email addresses, Aadhaar numbers, or any biometric identifiers.
- The `_metadata` block is limited to four fields: `generated_by`, `model`, `timestamp`, `schema_version`. No field in `_metadata` may store user identity information.
- Before Phase 3.3 writes `design_spec.json`, the pipeline performs a PII scan using keyword matching against known PII field names (`email`, `phone`, `aadhaar`, `pan`, `dob`, `name`, `address`) in all string values. Any match aborts Phase 3.3 with a `PII_DETECTED` error code.

### RPwD Act 2016 §40 — Accessibility for Persons with Disabilities

Section 40 of the Rights of Persons with Disabilities Act, 2016 mandates that digital public services (and products deployed in India) meet accessibility standards. The pipeline satisfies this by:

- Requiring APCA Lc ≥ 60 for all body-text color pairs (see §5).
- Requiring WCAG 2.1 AA (4.5:1) for all normal-text color pairs (see §5).
- Running Steps 7–9 unconditionally — accessibility validation is not optional.
- Blocking pipeline promotion to Phase 4.0 if `accessibility_report.json → summary.wcag_AA_fail > 0` for tokens used in body text.
- The GIGW v3.0 (Guidelines for Indian Government Websites) minimum Lc ≥ 45 for UI components is also enforced.

### MeitY AI Advisory 2023 — AI Provenance

The Ministry of Electronics and Information Technology AI Advisory (March 2023) requires that AI-generated artefacts be labelled with their origin. Compliance is implemented via the `_metadata` block in `design_spec.json`:

- `_metadata.generated_by` = `"figma-automation-agent"` — identifies the automated agent.
- `_metadata.model` = `"claude-sonnet-4-6"` — identifies the underlying LLM.
- `_metadata.timestamp` — ISO 8601 UTC generation time for audit trail.
- `_metadata.schema_version` — version of the schema used, enabling forward compatibility verification.

The JSON Schema at `plugin/schema/design_spec.schema.json` enforces that all four fields are present and non-empty; any `design_spec.json` missing this block fails schema validation and is rejected by Phase 3.4 Step 1.
