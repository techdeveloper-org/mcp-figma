# mcp-figma

![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)
![License MIT](https://img.shields.io/badge/License-MIT-green)
![Part of claude-workflow-engine](https://img.shields.io/badge/Part%20of-claude--workflow--engine-orange)
![MCP Server](https://img.shields.io/badge/MCP-Server-purple)

Figma design-to-code MCP server for Claude Code. Connects Claude to the Figma REST API over stdio JSON-RPC, enabling design file inspection, component extraction, design token parsing, frame layout analysis, image export, and design review comments — all without any external HTTP client dependencies (stdlib `urllib` only). Used by the Claude Workflow Engine to automate the design-to-code lifecycle: extracting components and tokens during orchestration planning (Step 0), posting implementation progress comments (Step 10), running design fidelity review (Step 11), and closing the design review loop on merge (Step 12).

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

---

## Tool Reference

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `figma_get_file_info` | Get file metadata: name, last modified, version, pages | `file_key` |
| `figma_get_node` | Get details of a specific node: type, size, fills, strokes, effects, children summary | `file_key`, `node_id` |
| `figma_get_styles` | Extract all published styles (colors, text, effects, grids) grouped by type | `file_key` |
| `figma_get_components` | List all published components and component sets with containing frame info | `file_key` |
| `figma_extract_design_tokens` | Extract design tokens: colors, typography, spacing, radii, shadows | `file_key`, `node_ids` (optional) |
| `figma_get_frame_layout` | Get auto-layout / flexbox properties for a frame node | `file_key`, `node_id` |
| `figma_export_image` | Export a node as PNG, SVG, JPG, or PDF and return a CDN URL | `file_key`, `node_id`, `format` (default `png`), `scale` (default `2`) |
| `figma_get_comments` | Get all design review comments with open/resolved counts | `file_key` |
| `figma_add_comment` | Post an implementation or review comment, optionally anchored to a node | `file_key`, `message`, `node_id` (optional) |
| `figma_health_check` | Verify API connectivity and token validity via GET /v1/me | — |

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

## Architecture

```
mcp-figma/
+-- server.py          # FastMCP server: 10 tools, stdlib urllib only, stdio transport
+-- base/              # Shared mcp-base package copy (MCPResponse, @mcp_tool_handler)
+-- input_validator.py # Input validation utilities
+-- mcp_errors.py      # MCP error types
+-- rate_limiter.py    # Token bucket rate limiting
+-- requirements.txt   # Pinned dependencies
+-- README.md
```

The server uses `urllib.request` exclusively for all HTTP calls — no `httpx`, `requests`, or other HTTP client libraries. All JSON-RPC communication with Claude Code happens over stdio.

The `base/` directory is a copy of the shared [mcp-base](https://github.com/techdeveloper-org/mcp-base) package, which provides the `@mcp_tool_handler` decorator for uniform error handling and `MCPResponse` for consistent response shaping across all 13 MCP servers in the ecosystem.

---

## Part of the Claude Workflow Engine Ecosystem

This server is one of 13 MCP servers extracted from the [claude-workflow-engine](https://github.com/techdeveloper-org/claude-workflow-engine) into independent repositories for separate versioning and reuse:

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
