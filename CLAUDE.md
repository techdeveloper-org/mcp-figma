# mcp-figma — Claude Project Context

**Type:** FastMCP Server
**Transport:** stdio
**Python:** 3.8+

---

## What This Server Does

Figma design file operations via REST API for design-to-code workflows. Fetches file metadata, nodes, styles, components, design tokens (colors/typography/spacing), frame layouts, and exports. Adds implementation comments. Uses stdlib urllib only — no heavy SDK dependency.

---

## Entry Point

```
server.py
```

Run via `python server.py` — communicates over stdio using the MCP protocol.

---

## Available Tools

- `figma_get_file_info` — Fetch Figma file metadata (name, version, last modified)
- `figma_get_node` — Retrieve a specific node by ID with full properties
- `figma_get_styles` — List all styles defined in the file (colors, text, effects)
- `figma_get_components` — List all reusable components with metadata
- `figma_extract_design_tokens` — Extract design tokens: colors, typography, spacing, border-radius
- `figma_get_frame_layout` — Get frame layout properties (auto-layout, constraints, grid)
- `figma_export_image` — Export a frame/node as PNG/SVG/PDF
- `figma_get_comments` — List all comments on the file
- `figma_add_comment` — Add an implementation comment to a frame/component
- `figma_health_check` — Verify Figma API token and connectivity

---

## Shared Utilities (in this repo)

- `base/` — Shared MCP infrastructure package (response builder, decorators, persistence, clients)
- `mcp_errors.py` — Structured error response helpers
- `input_validator.py` — Null-byte strip, length limits, prompt injection detection
- `rate_limiter.py` — Token bucket rate limiter (enable via ENABLE_RATE_LIMITING=1)

---

## Environment Variables

- `FIGMA_ACCESS_TOKEN` — Figma personal access token (required)
- `FIGMA_FILE_KEY` — Default Figma file key (optional, can be passed per-call)

---

## Development

### Running locally

```bash
# Install deps
pip install -r requirements.txt

# Run the MCP server (stdio mode)
python server.py
```

### Testing a tool call manually

```python
import subprocess, json

proc = subprocess.Popen(
    ["python", "server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
)
# Send MCP initialize + tool call via stdin
```

### File structure

```
mcp-figma/
+-- server.py          # Main FastMCP server (entry point)
+-- base/              # Shared base package (response, decorators, persistence, clients)
+-- mcp_errors.py      # Error helpers
+-- input_validator.py # Input validation
+-- rate_limiter.py    # Rate limiting
+-- requirements.txt
+-- .gitignore
+-- README.md
+-- CLAUDE.md
```

---

## Key Rules

1. Do NOT edit `base/` directly — it is a copy from `mcp-base` repo
2. To update shared utilities, edit in `mcp-base` and re-copy
3. Keep `server.py` as the single entry point
4. All tool handlers must use `@mcp_tool_handler` decorator for consistent error handling
5. All responses must use `success()` / `error()` / `MCPResponse` builder from `base.response`

---

**Last Updated:** 2026-03-31
