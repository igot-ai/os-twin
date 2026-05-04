---
name: agent-browser
description: Use Vercel agent-browser CLI for browser automation workflows including search, navigation, snapshots, clicks, form fills, screenshots, and file downloads. CLI-oriented alternative to Playwright MCP or obscura-browser MCP.
tags: [engineer, browser, automation, web, cli]
triggers:
  - "use agent-browser"
  - "browser automation"
  - "download from website"
  - "scrape webpage"
  - "take website screenshot"
  - "navigate to url"
  - "fill web form"
  - "click on page"
tools:
  - Bash
mutating: true
---

# agent-browser

## Contract

- Deterministic browser automation using refs like `@e1`, `@e2` from snapshots (not coordinates)
- All artifacts saved inside project under `artifacts/browser-downloads/`
- Exact artifact paths reported to user
- Graceful fallback to Playwright MCP or obscura-browser MCP if CLI unavailable
- No stealth or anti-bot bypass logic enabled by default

## When to Use

- Downloading files (PDFs, documents) from websites
- Taking screenshots or saving pages as PDF
- Filling forms and submitting data
- Navigating multi-step web workflows
- Scraping structured data from pages

## Installation

```bash
# Install CLI
npm install -g agent-browser

# Run post-install setup if needed
agent-browser install

# Verify
agent-browser --version
```

## Core Commands

| Command | Purpose |
|---------|---------|
| `agent-browser open <url>` | Navigate to URL |
| `agent-browser snapshot -i` | Get page snapshot with refs |
| `agent-browser snapshot -i --json` | Snapshot as JSON |
| `agent-browser click @eN` | Click element by ref |
| `agent-browser fill @eN "text"` | Fill input by ref |
| `agent-browser wait --load networkidle` | Wait for page load |
| `agent-browser screenshot <path>` | Save screenshot |
| `agent-browser pdf <path>` | Save page as PDF |
| `agent-browser close` | Close browser |

## Workflow

### 1. Navigate and Inspect

```bash
# Create artifacts directory
mkdir -p artifacts/browser-downloads

# Open URL
agent-browser open "https://example.com"

# Wait for page load
agent-browser wait --load networkidle

# Get snapshot to find element refs
agent-browser snapshot -i
```

Snapshot output includes refs like:
```
[@e1] <button>Submit</button>
[@e2] <input type="text" name="search">
```

### 2. Interact Using Refs

Always use refs from snapshots, never coordinates:

```bash
# Fill input
agent-browser fill @e2 "search query"

# Click button
agent-browser click @e1

# Re-snapshot after page changes
agent-browser snapshot -i
```

### 3. Capture Artifacts

```bash
# Screenshot
agent-browser screenshot artifacts/browser-downloads/page.png

# Save page as PDF
agent-browser pdf artifacts/browser-downloads/page.pdf
```

### 4. Handle Downloads

For download links, use marker-based verification to avoid moving old files:

```bash
# Create marker timestamp BEFORE clicking download
MARKER=$(date +%s)

# Click download link
agent-browser click @e3

# Wait for download to complete
agent-browser wait --load networkidle
sleep 2

# Find PDFs newer than marker (Linux/macOS)
DOWNLOADED=""
for f in "$HOME/Downloads"/*.pdf; do
    if [ -f "$f" ] && [ -s "$f" ]; then
        # Get file mtime as seconds since epoch
        if [ "$(uname)" = "Darwin" ]; then
            MTIME=$(stat -f %m "$f")
        else
            MTIME=$(stat -c %Y "$f")
        fi
        if [ "$MTIME" -ge "$MARKER" ]; then
            if [ -z "$DOWNLOADED" ] || [ "$MTIME" -gt "$NEWEST_TIME" ]; then
                DOWNLOADED="$f"
                NEWEST_TIME="$MTIME"
            fi
        fi
    fi
done

if [ -n "$DOWNLOADED" ] && [ -s "$DOWNLOADED" ]; then
    FILENAME=$(basename "$DOWNLOADED")
    mv "$DOWNLOADED" "artifacts/browser-downloads/$FILENAME"
    echo "Downloaded: artifacts/browser-downloads/$FILENAME"
else
    echo "ERROR: No new PDF downloaded after marker"
fi
```

**Rules:**
- Create marker timestamp before clicking download
- Only accept files newer than marker
- Verify file exists and has non-zero size
- Move exactly one newest matching file
- Report exact relative path
- Report explicit failure if no new file appears

### 5. Clean Up

```bash
agent-browser close
```

## Example: Download Vietnamese Legal Decree

```bash
# Setup
mkdir -p artifacts/browser-downloads

# Navigate to law library
agent-browser open "https://thuvienphapluat.vn"
agent-browser wait --load networkidle
agent-browser snapshot -i

# Search (refs from snapshot)
agent-browser fill @e1 "Nghi dinh 123/2024"
agent-browser click @e2
agent-browser wait --load networkidle
agent-browser snapshot -i

# Open result
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser snapshot -i

# Click download with marker verification
MARKER=$(date +%s)
agent-browser click @e4
sleep 3

DOWNLOADED=""
for f in "$HOME/Downloads"/*.pdf; do
    if [ -f "$f" ] && [ -s "$f" ]; then
        if [ "$(uname)" = "Darwin" ]; then
            MTIME=$(stat -f %m "$f")
        else
            MTIME=$(stat -c %Y "$f")
        fi
        if [ "$MTIME" -ge "$MARKER" ]; then
            if [ -z "$DOWNLOADED" ] || [ "$MTIME" -gt "$NEWEST_TIME" ]; then
                DOWNLOADED="$f"
                NEWEST_TIME="$MTIME"
            fi
        fi
    fi
done

if [ -n "$DOWNLOADED" ]; then
    FILENAME=$(basename "$DOWNLOADED")
    mv "$DOWNLOADED" "artifacts/browser-downloads/$FILENAME"
    echo "Downloaded: artifacts/browser-downloads/$FILENAME"
else
    echo "ERROR: No new PDF downloaded"
fi

# Cleanup
agent-browser close
```

## Fallback

If `agent-browser` CLI is unavailable:

### obscura-browser MCP

Use these tools:
- `browser_open` - Navigate to URL
- `browser_snapshot` - Get page state
- `browser_click` - Click element
- `browser_fill` - Fill input
- `browser_screenshot` - Capture screenshot
- `browser_pdf` - Save as PDF
- `browser_click_and_download` - Click and handle download
- `browser_close` - Close browser

### Playwright MCP

Use the currently available Playwright MCP browser tools for navigation, snapshots, interaction, and capture.

## Platform Notes

### Windows (PowerShell)

```powershell
# Create directory
New-Item -ItemType Directory -Path "artifacts/browser-downloads" -Force

# Create marker BEFORE clicking download
$marker = Get-Date

# ... click download link ...

# Find PDFs newer than marker with non-zero size
$downloaded = Get-ChildItem "$env:USERPROFILE\Downloads\*.pdf" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -gt $marker -and $_.Length -gt 0 } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($downloaded) {
    Move-Item $downloaded.FullName "artifacts/browser-downloads\"
    Write-Host "Downloaded: artifacts/browser-downloads\$($downloaded.Name)"
}
else {
    Write-Host "ERROR: No new PDF downloaded after marker"
}
```

### Linux / macOS (Bash)

```bash
# Create directory
mkdir -p artifacts/browser-downloads

# Create marker BEFORE clicking download
MARKER=$(date +%s)

# ... click download link ...

# Find PDFs newer than marker with non-zero size
DOWNLOADED=""
for f in "$HOME/Downloads"/*.pdf; do
    if [ -f "$f" ] && [ -s "$f" ]; then
        if [ "$(uname)" = "Darwin" ]; then
            MTIME=$(stat -f %m "$f")
        else
            MTIME=$(stat -c %Y "$f")
        fi
        if [ "$MTIME" -ge "$MARKER" ]; then
            if [ -z "$DOWNLOADED" ] || [ "$MTIME" -gt "$NEWEST_TIME" ]; then
                DOWNLOADED="$f"
                NEWEST_TIME="$MTIME"
            fi
        fi
    fi
done

if [ -n "$DOWNLOADED" ]; then
    FILENAME=$(basename "$DOWNLOADED")
    mv "$DOWNLOADED" "artifacts/browser-downloads/$FILENAME"
    echo "Downloaded: artifacts/browser-downloads/$FILENAME"
else
    echo "ERROR: No new PDF downloaded after marker"
fi
```

## Anti-Patterns

- **Coordinate clicks** - Use refs from snapshots
- **Assuming download succeeded** - Always verify file exists and has content
- **Saving outside project** - Keep artifacts under `artifacts/browser-downloads/`
- **Not reporting paths** - User needs exact file locations
- **Stealth/bypass logic** - If blocked, report the blocker; do not add anti-detection
- **Hardcoded absolute paths** - Use relative paths from project root
- **Wildcards with `|| true`** - Hides failures; verify each download explicitly

## Verification Checklist

- [ ] Browser session closed after use
- [ ] All interactions use refs from snapshots (not coordinates)
- [ ] Downloads verified to exist with non-zero size
- [ ] Files saved under `artifacts/browser-downloads/`
- [ ] Exact relative paths reported to user
- [ ] No stealth/anti-bot logic added
