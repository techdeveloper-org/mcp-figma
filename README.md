# mcp-figma

A FastMCP server providing **Figma** capabilities for Claude Code workflows.

---

## Overview

Figma design file operations via REST API for design-to-code workflows. Fetches file metadata, nodes, styles, components, design tokens (colors/typography/spacing), frame layouts, and exports. Adds implementation comments. Uses stdlib urllib only — no heavy SDK dependency.

---

## Tools

| Tool | Description |
|------|-------------|
| `figma_get_file_info` | Fetch Figma file metadata (name, version, last modified) |
| `figma_get_node` | Retrieve a specific node by ID with full properties |
| `figma_get_styles` | List all styles defined in the file (colors, text, effects) |
| `figma_get_components` | List all reusable components with metadata |
| `figma_extract_design_tokens` | Extract design tokens: colors, typography, spacing, border-radius |
| `figma_get_frame_layout` | Get frame layout properties (auto-layout, constraints, grid) |
| `figma_export_image` | Export a frame/node as PNG/SVG/PDF |
| `figma_get_comments` | List all comments on the file |
| `figma_add_comment` | Add an implementation comment to a frame/component |
| `figma_health_check` | Verify Figma API token and connectivity |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/techdeveloper-org/mcp-figma.git
cd mcp-figma
```

### 2. Install dependencies

```bash
pip install mcp fastmcp
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `FIGMA_ACCESS_TOKEN` | Figma personal access token (required) |
| `FIGMA_FILE_KEY` | Default Figma file key (optional, can be passed per-call) |

---

## Usage in Claude Code

Add to your `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "figma": {
      "command": "python",
      "args": [
        "/path/to/mcp-figma/server.py"
      ],
      "env": {}
    }
  }
}
```

---

## Benefits

- Design tokens injection into prompts ensures pixel-accurate implementation
- Component extraction for UI task breakdown (Step 3 of pipeline)
- Implementation lifecycle comments keep Figma in sync with code progress
- No heavy Figma SDK — pure stdlib urllib keeps dependencies minimal

---

## Requirements

- Python 3.8+
- `mcp fastmcp`
- See `requirements.txt` for pinned versions

---

## Project Context

This MCP server is part of the **Claude Workflow Engine** ecosystem — a LangGraph-based
orchestration pipeline for automating Claude Code development workflows.

Related repos:
- [`claude-workflow-engine`](https://github.com/techdeveloper-org/claude-workflow-engine) — Main pipeline
- [`mcp-base`](https://github.com/techdeveloper-org/mcp-base) — Shared base utilities used by all MCP servers

---

## License

Private — techdeveloper-org
