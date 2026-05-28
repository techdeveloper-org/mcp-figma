# Design Spec Importer — Figma Plugin

Imports AI-generated `design_spec.json` files into Figma, automatically creating pages, frames, components, design tokens, and FR coverage annotations.

## Prerequisites
- Figma account (Desktop or Web, version 116+)
- Node.js 18+
- `design_spec.json` from the Phase 3.2 AI pipeline

## Build

```bash
cd plugin
npm install
npm run build
```

## Install in Figma

1. Open Figma desktop or web
2. Go to **Plugins → Development → Import plugin from manifest**
3. Select `plugin/manifest.json`

## Usage

1. Open a blank Figma file (name it `{Project}-Design-Phase3`)
2. Run **Plugins → Development → Design Spec Importer**
3. Paste your `design_spec.json` content into the textarea
4. Click **Import to Figma**
5. Wait for progress (one step per screen)
6. Copy the completion summary JSON from the success panel
7. Save to `docs/phase-3-design/figma_file.md`

## Publish as Team Plugin

1. Build: `npm run build`
2. In Figma: **Plugins → Development → Publish plugin** (requires Figma Organization plan)

## CI Status

![Plugin CI](../../.github/workflows/plugin-ci.yml)
