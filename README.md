# mcp-figma

![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)
![License MIT](https://img.shields.io/badge/License-MIT-green)
![MCP Server](https://img.shields.io/badge/MCP-Server-purple)
![Plugin CI](https://github.com/techdeveloper-org/mcp-figma/actions/workflows/plugin-ci.yml/badge.svg)

Figma design-to-code MCP server for Claude Code. Connects Claude to the Figma REST API over stdio JSON-RPC, enabling design file inspection, component extraction, design token parsing, frame layout analysis, image export, and design review comments — all without any external HTTP client dependencies (stdlib `urllib` only). Used by the Claude Workflow Engine to automate the design-to-code lifecycle: extracting components and tokens during orchestration planning (Step 0), posting implementation progress comments (Step 10), running design fidelity review (Step 11), and closing the design review loop on merge (Step 12).

This repository also contains the **Design Spec Importer** — a TypeScript Figma Plugin that reads AI-generated `design_spec.json` files and creates complete Figma designs (pages, frames, components, design token variables, and FR coverage annotations) inside an open Figma file. It bridges Phase 3 of the AI-driven UI/UX pipeline: AI agents generate the spec, the plugin writes it to Figma, and mcp-figma reads the result back for token export and accessibility validation.

---

## Features

- Retrieve Figma file metadata, pages, and version information
- Inspect individual nodes (frames, components, groups) with size, fills, strokes, and effects
- List all published styles (colors, text, effects, grids) grouped by type
- List all published components and component sets with containing frame context
- Extract design tokens (colors, typography, spacing, border radii, drop shadows) from the full document tree or scoped to specific nodes
- Get auto-layout and flexbox properties for frame nodes (padding, gap, alignment, sizing)
- Export nodes as PNG, SVG, JPG, or PDF with configurable scale factor
- Read all design review comments with open/resolved breakdown
- Post implementation or review comments anchored to specific frames
- Health check to verify API token and connectivity
- Full design variable CRUD: collections, variables, aliases, batch updates, team library publishing
- Webhook lifecycle management with HMAC-SHA256 signature verification
- APCA Lc and WCAG 2.1 contrast computation with accessible color pair search
- DTCG-format token extraction, validation, diffing (Levenshtein rename detection), and alias resolution
- Platform-specific token output: Android XML, iOS Swift, CSS custom properties, fluid typography
- Component code generation: React, SwiftUI, Android XML, CSS, Flutter from Figma frames
- Visual regression via perceptual hash (pHash) and Hamming distance comparison
- Semantic version bump computation from two DTCG token snapshots

**Design Spec Importer Plugin (`plugin/`):**

- Reads AI-generated `design_spec.json` (validated against JSON Schema Draft-07 at startup)
- Creates Figma pages, frames with auto-layout, and reusable components from spec
- Builds component variant sets via `figma.combineAsVariants()`
- Creates design token variable collections (Colors, Spacing, Typography) using the Figma Variables API
- Annotates each frame with FR coverage references for traceability
- Outputs a structured completion summary (file key + page/frame node IDs) for mcp-figma read-back

---

## Architecture

mcp-figma exposes 47 tools across 8 domain modules, all registered in a single `server.py` entry point:

| Module | Tools | Purpose |
|--------|-------|---------|
| `server.py` | 10 | Core tools: file info, nodes, styles, components, tokens, layout, export, comments, health |
| `figma_variables.py` | 8 | Design variable CRUD, alias resolution, batch updates, collection publishing |
| `figma_webhooks.py` | 5 | Webhook lifecycle management with HMAC-SHA256 signature verification |
| `figma_accessibility.py` | 3 | APCA Lc and WCAG 2.1 contrast computation, accessible color pair search |
| `figma_tokens.py` | 6 | DTCG token extraction, validation, diffing, alias resolution, platform transforms |
| `figma_multiplatform.py` | 5 | Android XML, iOS Swift, CSS custom properties, fluid typography, type scale |
| `figma_codegen.py` | 6 | React, SwiftUI, Android, CSS, Flutter component stubs from Figma frames |
| `figma_visual.py` | 4 | Perceptual hash (pHash), Hamming distance, semver bump, version history |

All tools communicate over stdio using the MCP protocol. No HTTP server is started.

---

## Tool Reference

### Core Tools (10)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `figma_get_file_info` | Get file metadata: name, last modified, version, pages | `file_key` |
| `figma_get_node` | Get details of a specific node: type, size, fills, strokes, effects, children summary | `file_key`, `node_id` |
| `figma_get_styles` | Extract all published styles (colors, text, effects, grids) grouped by type | `file_key` |
| `figma_get_components` | List all published components and component sets with containing frame info | `file_key` |
| `figma_extract_design_tokens` | Extract design tokens: colors, typography, spacing, radii, shadows | `file_key`, `node_ids` (optional) |
| `figma_get_frame_layout` | Get auto-layout / flexbox properties for a frame node | `file_key`, `node_id` |
| `figma_export_image` | Export a node as PNG, SVG, JPG, or PDF and return a CDN URL | `file_key`, `node_id`, `format`, `scale` |
| `figma_get_comments` | Get all design review comments with open/resolved counts | `file_key` |
| `figma_add_comment` | Post an implementation or review comment, optionally anchored to a node | `file_key`, `message`, `node_id` (optional) |
| `figma_health_check` | Verify API connectivity and token validity via GET /v1/me | -- |

### Variable Tools (8)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `figma_get_variable_collections` | List all variable collections in a Figma file | `file_key` |
| `figma_get_variables` | Get all variables in a collection with resolved values | `file_key`, `collection_id` |
| `figma_set_variable_value` | Set a variable value for a specific mode | `file_key`, `variable_id`, `mode_id`, `value` |
| `figma_create_variable` | Create a new design variable in a collection | `file_key`, `collection_id`, `name`, `resolved_type` |
| `figma_resolve_variable_alias` | Resolve a variable alias to its underlying value | `file_key`, `variable_id` |
| `figma_get_local_variables` | Fetch all local variables from the REST API | `file_key` |
| `figma_publish_variable_collection` | Publish a variable collection to team library | `file_key`, `collection_id` |
| `figma_batch_update_variables` | Batch-update multiple variable values atomically | `file_key`, `updates` |

### Webhook Tools (5)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `figma_create_webhook` | Register a webhook for Figma file events | `team_id`, `event_type`, `endpoint`, `passcode` |
| `figma_list_webhooks` | List all webhooks for the current team | `team_id` |
| `figma_delete_webhook` | Delete a registered webhook by ID | `webhook_id` |
| `figma_get_webhook_events` | Retrieve recent events delivered to a webhook | `webhook_id` |
| `figma_verify_webhook_signature` | Verify HMAC-SHA256 webhook payload signature | `payload`, `signature`, `passcode` |

### Accessibility Tools (3)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `compute_apca_contrast` | Compute APCA Lc contrast (APCA 0.0.98G coefficients) | `text_color`, `bg_color` |
| `compute_wcag_contrast` | Compute WCAG 2.1 contrast ratio via relative luminance | `color_a`, `color_b` |
| `get_accessible_color_pairs` | Find accessible foreground/background color pairs from a palette | `colors`, `min_contrast` |

### Token Tools (6)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `extract_dtcg_tokens` | Extract DTCG-format design tokens from a Figma file | `file_key` |
| `validate_token_schema` | Validate a token set against the DTCG W3C specification | `tokens` |
| `diff_token_sets` | Compute diff between two token sets with Levenshtein rename detection | `old_tokens`, `new_tokens` |
| `resolve_token_aliases` | Resolve alias chains in a token set using Kahn topological sort | `tokens` |
| `generate_token_transforms` | Generate platform-specific token transforms (CSS, Android, iOS) | `tokens`, `platform` |
| `export_tokens_dtcg` | Export resolved tokens in DTCG JSON format | `tokens` |

### Multiplatform Tools (5)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `generate_android_tokens` | Generate Android XML resources from design tokens | `tokens` |
| `generate_ios_tokens` | Generate Swift/Objective-C token constants from design tokens | `tokens` |
| `generate_css_tokens` | Generate CSS custom properties from design tokens | `tokens` |
| `generate_fluid_typography` | Generate fluid type scale with CSS clamp() expressions | `min_size`, `max_size`, `min_vw`, `max_vw` |
| `generate_type_scale` | Generate a modular type scale from a base size and ratio | `base_size`, `ratio`, `steps` |

### Code Generation Tools (6)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `generate_react_component` | Generate a React component stub from a Figma frame | `file_key`, `node_id` |
| `generate_swift_component` | Generate a SwiftUI view stub from a Figma frame | `file_key`, `node_id` |
| `generate_android_component` | Generate an Android XML layout from a Figma frame | `file_key`, `node_id` |
| `generate_css_from_frame` | Generate CSS styles from a Figma frame's properties | `file_key`, `node_id` |
| `generate_flutter_component` | Generate a Flutter widget stub from a Figma frame | `file_key`, `node_id` |
| `get_codegen_context` | Extract structured codegen context from a Figma node | `file_key`, `node_id` |

### Visual Regression Tools (4)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `compute_phash` | Compute a perceptual hash (pHash) of a Figma CDN image URL (SSRF-safe) | `image_url` |
| `compare_phash_hamming` | Compare two pHash digests using Hamming distance | `hash_a`, `hash_b` |
| `bump_token_semver` | Compute semantic version bump from two DTCG token snapshots | `old_tokens`, `new_tokens` |
| `get_file_version_history` | Retrieve version history for a Figma file | `file_key` |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/techdeveloper-org/mcp-figma.git
cd mcp-figma
```

### 2. Install dependencies

The server uses Python stdlib only (`urllib`, `json`, `os`, `sys`) for all HTTP calls. The only install requirement is the `mcp` package:

```bash
pip install mcp
```

No other external packages are required.

### 3. Register in Claude Code settings

Add the server to `~/.claude/settings.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "figma-api": {
      "command": "python",
      "args": ["/path/to/mcp-figma/server.py"],
      "env": {
        "FIGMA_ACCESS_TOKEN": "your-figma-personal-access-token",
        "ENABLE_FIGMA": "1"
      }
    }
  }
}
```

Replace `/path/to/mcp-figma/server.py` with the absolute path to the cloned repository.

---

## Configuration

| Environment Variable | Required | Default | Description |
|----------------------|----------|---------|-------------|
| `FIGMA_ACCESS_TOKEN` | Yes | — | Figma Personal Access Token. Sent as `X-Figma-Token` header on every request. |
| `FIGMA_TEAM_ID` | No | — | Team ID for team-level queries. Returned in `figma_health_check` output. |
| `ENABLE_FIGMA` | No | `0` | Set to `1` to activate the Figma integration in the Claude Workflow Engine pipeline. |

### Obtaining a Figma Personal Access Token

1. Log in to [figma.com](https://figma.com)
2. Go to **Account Settings** (top-left profile menu)
3. Scroll to **Personal access tokens**
4. Click **Generate new token**, give it a name, and copy the value
5. Set it as `FIGMA_ACCESS_TOKEN` in your environment or in the Claude Code `settings.json` `env` block

---

## Usage Examples

### Get file metadata

```python
# Using a raw file key
result = figma_get_file_info(file_key="AbCdEfGhIjKlMnOp")

# Also accepts full Figma URLs
result = figma_get_file_info(
    file_key="https://www.figma.com/file/AbCdEfGhIjKlMnOp/My-Design-System"
)
# Returns: name, last_modified, version, thumbnail_url, pages list, page_count
```

### Extract design tokens from a file

```python
# Scan the full document tree for all design tokens
result = figma_extract_design_tokens(file_key="AbCdEfGhIjKlMnOp")

# Scope extraction to specific nodes (comma-separated node IDs)
result = figma_extract_design_tokens(
    file_key="AbCdEfGhIjKlMnOp",
    node_ids="1:23,4:56,7:89"
)
# Returns: tokens.colors (hex strings), tokens.typography (font family/size/weight/
#          line-height/letter-spacing), tokens.spacing (padding + gap from auto-layout),
#          tokens.radii (corner radius values), tokens.shadows (drop shadow definitions)
```

### List components and component sets

```python
result = figma_get_components(file_key="AbCdEfGhIjKlMnOp")

for component in result["components"]:
    print(component["name"], component["containing_frame"], component["node_id"])

# result["component_sets"] lists variant groups
```

### Get auto-layout properties for a frame

```python
result = figma_get_frame_layout(
    file_key="AbCdEfGhIjKlMnOp",
    node_id="1:23"
)

print(result["layout_mode"])                  # "HORIZONTAL" or "VERTICAL"
print(result["item_spacing"])                 # gap between children
print(result["primary_axis_align_items"])     # alignment on main axis
print(result["padding_top"], result["padding_left"])  # padding values
```

### Export a node as an image

```python
result = figma_export_image(
    file_key="AbCdEfGhIjKlMnOp",
    node_id="1:23",
    format="png",   # "png", "svg", "jpg", or "pdf"
    scale=2         # 1 to 4
)

print(result["image_url"])  # Temporary CDN URL, expires in approximately 30 days
```

### Post a design review comment

```python
# File-level comment
figma_add_comment(
    file_key="AbCdEfGhIjKlMnOp",
    message="Implementation started — PR #42 open for review"
)

# Anchored to a specific frame node
figma_add_comment(
    file_key="AbCdEfGhIjKlMnOp",
    message="Button component matches spec — padding and corner radius verified",
    node_id="1:23"
)
```

### Verify connectivity

```python
result = figma_health_check()
print(result["connected"])       # True if token is valid
print(result["name"])            # Figma account handle
print(result["enable_figma"])    # Current value of ENABLE_FIGMA env var
```

---

## Integration Lifecycle (Claude Workflow Engine)

When `ENABLE_FIGMA=1`, the Claude Workflow Engine integrates this server across four pipeline steps:

| Step | Action |
|------|--------|
| **Step 0** — Orchestration Planning | `figma_get_components` and `figma_extract_design_tokens` are called during the orchestration template fill. Component list and token data are injected into the planning prompt so the orchestrator understands the design system before generating implementation tasks. |
| **Step 10** — Implementation | `figma_add_comment` posts an "Implementation started" comment to the Figma file listing the components being implemented, optionally anchored to relevant frames. |
| **Step 11** — Code Review | `figma_get_styles` and `figma_get_frame_layout` provide data for a design fidelity checklist included in the pull request review. `figma_get_comments` retrieves any open design feedback for the reviewer. |
| **Step 12** — Issue Closure | `figma_add_comment` posts an "Implementation complete" comment with the merged PR number and branch name, closing the design review loop. |

This lifecycle ensures design intent flows from Figma into the codebase without manual handoff between design and engineering.

---

## Phase 3 — Design Spec Importer Plugin

The plugin bridges AI-generated design specs to a live Figma file. It is part of the Phase 3 UI/UX Design Pipeline that runs after Phase 2 (Joint Blueprint Validation) and before Phase B (Engineering).

### How it works

```
Phase 2 JOINT APPROVED
        ↓
[Phase 3.2] AI agents generate design_spec.json from PRD + HLD
        ↓
[Phase 3.3] User runs Design Spec Importer plugin in Figma
            → Pages, frames, components, tokens created automatically
            → Completion summary (file key + node IDs) saved to docs/phase-3-design/figma_file.md
        ↓
[Phase 3.4] mcp-figma reads the created file back:
            → figma_extract_design_tokens → design_tokens.dtcg.json
            → generate_css_tokens / generate_android_tokens / generate_ios_tokens
            → compute_apca_contrast + compute_wcag_contrast → accessibility_report.json
            → generate_react_component / generate_swift_component (code stubs)
        ↓
[Phase 3.6] consensus-agent reviews: FR coverage? AC implementable? Accessibility passes?
        ↓
DESIGN APPROVED → Engineers start Phase B with HLD + Figma + tokens + code stubs
```

### Plugin quick start

```bash
cd plugin
npm install
npm run build          # bundles src/code.ts → dist/code.js via esbuild
npm run test           # 121 tests, 100% coverage (vitest + @figma/plugin-ds mock)
npm run typecheck      # tsc --noEmit, strict mode
```

Install in Figma: **Plugins → Development → Import plugin from manifest** → select `plugin/manifest.json`.

### design_spec.json format

```json
{
  "_metadata": {
    "generated_by": "figma-automation-agent",
    "model": "claude-sonnet-4-6",
    "timestamp": "2026-05-28T00:00:00Z",
    "schema_version": "1.0.0"
  },
  "project": "MyApp",
  "design_system": {
    "colors": { "primary": "#2563EB", "surface": "#F8FAFC", "error": "#DC2626" },
    "typography": {
      "heading-1": { "fontFamily": "Inter", "fontSize": 32, "fontWeight": 700 },
      "body": { "fontFamily": "Inter", "fontSize": 16, "fontWeight": 400 }
    },
    "spacing": [4, 8, 12, 16, 24, 32, 48]
  },
  "screens": [
    { "name": "Login", "fr_coverage": ["FR-001", "FR-002"], "width": 390, "height": 844, "components": ["LoginButton"] }
  ],
  "components": [
    { "name": "LoginButton", "variants": ["Default", "Loading", "Disabled"], "layout": "horizontal", "padding": { "top": 12, "right": 24, "bottom": 12, "left": 24 } }
  ]
}
```

Full schema at `plugin/schema/design_spec.schema.json`. See `docs/phase-3-design/token-pipeline-spec.md` for the complete mcp-figma read-back sequence.

---

## File Structure

```
mcp-figma/
+-- server.py                 # FastMCP server: all 47 tools registered, stdio transport
+-- figma_client.py           # HTTP client (ETag, PKCE, pagination, retry backoff)
+-- figma_variables.py        # 8 variable tools
+-- figma_webhooks.py         # 5 webhook tools (HMAC-SHA256 verification)
+-- figma_accessibility.py    # 3 accessibility tools (APCA 0.0.98G, WCAG 2.1)
+-- figma_tokens.py           # 6 token tools (DTCG, Kahn sort, Levenshtein diff)
+-- figma_multiplatform.py    # 5 multiplatform tools (Android/iOS/CSS/fluid)
+-- figma_codegen.py          # 6 codegen tools (React/SwiftUI/Android/CSS/Flutter)
+-- figma_visual.py           # 4 visual regression tools (pHash, semver)
+-- base/                     # Shared mcp-base package copy (MCPResponse, @mcp_tool_handler)
+-- input_validator.py        # Input validation utilities
+-- mcp_errors.py             # Structured MCP error types
+-- rate_limiter.py           # Token bucket rate limiting
+-- tests/                    # Test suite: 202 unit + 14 integration + 22 e2e tests
+-- requirements.txt          # Pinned dependencies
+-- plugin/                   # Design Spec Importer — Figma Plugin (TypeScript)
|   +-- manifest.json         # Figma plugin manifest (networkAccess: no external domains)
|   +-- package.json          # devDeps: @figma/plugin-typings, esbuild, vitest, ajv
|   +-- tsconfig.json         # strict: true, target: ES2017
|   +-- esbuild.config.js     # Bundles src/code.ts → dist/code.js (IIFE, no externals)
|   +-- vitest.config.ts      # 100% coverage thresholds (lines/functions/branches/stmts)
|   +-- src/
|   |   +-- code.ts           # Main sandbox: origin check, 1MB guard, schema validate, orchestrate
|   |   +-- ui.html           # Plugin UI: textarea, progress, completion summary panel
|   |   +-- types.ts          # DesignSpec, Screen, Component, PluginCompletionSummary interfaces
|   |   +-- schema.ts         # AJV-compiled JSON Schema Draft-07 validator
|   |   +-- builders/
|   |       +-- token-builder.ts     # figma.variables.* — Colors/Spacing/Typography collections
|   |       +-- page-builder.ts      # figma.createPage() per screen
|   |       +-- frame-builder.ts     # figma.createFrame() + VERTICAL auto-layout
|   |       +-- component-builder.ts # figma.createComponent() + figma.combineAsVariants()
|   |       +-- comment-builder.ts   # FR coverage text annotation per frame
|   +-- schema/
|   |   +-- design_spec.schema.json  # JSON Schema Draft-07 (used by AI agents to validate output)
|   +-- tests/                # 121 vitest unit tests — 100% line/branch/function/statement coverage
+-- docs/
|   +-- orchestration_prompt.md       # Phase 3 orchestration prompt (Pattern 43)
|   +-- staging-env-spec.md           # CERT-In compliant Figma PAT rotation procedure
|   +-- phase-3-design/
|       +-- README.md                 # Output file registry (10 artifacts, creation order)
|       +-- token-pipeline-spec.md    # DTCG pipeline + APCA/WCAG validation sequence
+-- .github/workflows/
|   +-- plugin-ci.yml         # 4-job CI: typecheck → unit tests (100%) → npm audit → package
+-- README.md
```

The server uses `urllib.request` exclusively for all HTTP calls -- no `httpx`, `requests`, or other HTTP client libraries. All JSON-RPC communication with Claude Code happens over stdio.

The `base/` directory is a copy of the shared [mcp-base](https://github.com/techdeveloper-org/mcp-base) package, which provides the `@mcp_tool_handler` decorator for uniform error handling and `MCPResponse` for consistent response shaping across all 13 MCP servers in the ecosystem.

---

## Related projects

> **Standalone.** This server has no runtime dependency on any other project. It speaks MCP over stdio and works with any MCP client.

This server is one of 13 that were split out of the [claude-workflow-engine](https://github.com/techdeveloper-org/claude-workflow-engine) into independent repositories for separate versioning and reuse:

| Server | Purpose |
|--------|---------|
| mcp-session-mgr | Session lifecycle management |
| mcp-git-ops | Git branch, commit, push, pull operations |
| mcp-github-api | GitHub PR, issue, merge, label operations |
| mcp-policy-enforcement | Policy compliance and system health |
| mcp-token-optimizer | Token reduction via AST navigation |
| mcp-pre-tool-gate | Pre-tool validation with policy checks |
| mcp-post-tool-tracker | Post-tool progress tracking |
| mcp-standards-loader | Standards detection and hot-reload |
| mcp-uml-diagram | UML generation (13 diagram types) |
| mcp-drawio-diagram | Draw.io editable diagram generation |
| mcp-jira-api | Jira issue lifecycle integration |
| mcp-jenkins-ci | Jenkins CI/CD trigger and monitoring |
| **mcp-figma** | **Figma design-to-code pipeline (this server)** |

All servers share the [mcp-base](https://github.com/techdeveloper-org/mcp-base) package via an included `base/` directory copy.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make changes and ensure all tools return consistent response shapes using `base/decorators.py`
4. Submit a pull request with a clear description of the change

When adding a new tool:
- Decorate with `@mcp.tool()` and `@mcp_tool_handler`
- Include a complete docstring with an `Args:` block
- Use `_make_figma_request` for all Figma API calls
- Accept `file_key` as either a raw key or a full Figma URL (via `_parse_file_key`)

---

## License

MIT License. See [LICENSE](LICENSE) for full text.
