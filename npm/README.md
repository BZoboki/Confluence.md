# confluence-md

CLI tool to export Confluence pages to Markdown files — **no Python required**.

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![npm version](https://img.shields.io/npm/v/confluence-md.svg)](https://www.npmjs.com/package/confluence-md)

## Installation

```bash
# Install globally
npm install -g confluence-md

# Or run directly with npx
npx confluence-md --help
```

## Usage

```bash
confluence-md --page-id <PAGE_ID> --output-path <OUTPUT_DIR> [OPTIONS]
```

### Required Options

| Option | Description |
|--------|-------------|
| `--page-id` | Confluence page ID to export |
| `--output-path` | Output directory for Markdown files |

### Authentication

Set these environment variables (or pass as CLI options):

```bash
export CONFLUENCE_URL="https://your-domain.atlassian.net"
export CONFLUENCE_USER="your-email@example.com"  # For Cloud
export CONFLUENCE_TOKEN="your-api-token"
```

Or use a `.env` file in your working directory.

### All Options

```
--url              Confluence base URL
--user             Username/email (Cloud) or omit for Server PAT
--token            API token (Cloud) or Personal Access Token (Server)
--delay-ms         Delay between API calls in ms (default: 100)
--timeout          HTTP timeout in seconds (default: 30)
--skip-existing    Skip files that already exist (resume capability)
--max-depth        Maximum recursion depth (default: 50)
--verbose          Enable verbose logging
--no-update-check  Disable update check
--version          Show version and exit
--help             Show help and exit
```

### Example

```bash
# Export a page and all its children
confluence-md --page-id 123456789 --output-path ./docs

# Resume an interrupted export
confluence-md --page-id 123456789 --output-path ./docs --skip-existing
```

## Output Format

Each page is exported as a Markdown file with YAML frontmatter:

```markdown
---
title: "Page Title"
confluence_id: "123456789"
space_key: "SPACE"
last_modified: "2024-01-15T10:30:00Z"
source_url: "https://your-domain.atlassian.net/wiki/spaces/SPACE/pages/123456789"
---

# Page Title

Page content in Markdown...
```

## Supported Platforms

- Windows (x64)
- macOS (arm64, x64 via Rosetta 2)
- Linux (x64)

## Links

- [GitHub Repository](https://github.com/bzoboki/Confluence.md)
- [Report Issues](https://github.com/bzoboki/Confluence.md/issues)
- [Python Installation](https://github.com/bzoboki/Confluence.md#python-installation) (alternative)

## License

MIT
