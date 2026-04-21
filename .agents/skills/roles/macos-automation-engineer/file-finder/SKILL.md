---
name: file-finder
description: Search files via Spotlight (mdfind), manage extended attributes (xattr), copy with metadata (ditto), Quick Look, and Finder operations."
tags: [macos-automation-engineer, automation, macos, files, spotlight, finder]

platform: [macos]
requires_permissions: []
shell: bash
---

# file-finder

## Overview

Search, preview, and manage files on macOS using native tools: `mdfind` (Spotlight), `xattr` (extended attributes), `ditto` (metadata-preserving copy), `qlmanage` (Quick Look), and Finder AppleScript. No TCC permissions required for most operations.

## Commands

Invoke via `ostwin mac finder <cmd> [args]` or dispatch via daemon. Underlying script: `.agents/scripts/macos/finder.sh`

| Command | Arguments | Description |
|---------|-----------|-------------|
| `search` | `<query> [dir]` | Spotlight full-text search via `mdfind -onlyin`. |
| `search-name` | `<filename> [dir]` | Find files by name via `mdfind -name`. |
| `search-kind` | `<kind> [dir]` | Find files by Spotlight kind (`image`, `pdf`, `music`, `movie`, etc.). |
| `preview` | `<filepath>` | Open a Quick Look preview window (`qlmanage -p`). |
| `reveal` | `<filepath>` | Reveal file in Finder (`open -R`). |
| `xattr-list` | `<filepath>` | List all extended attributes on a file. |
| `xattr-get` | `<filepath> <attr>` | Read the value of a specific extended attribute. |
| `xattr-set` | `<filepath> <attr> <value>` | Write a value to an extended attribute. |
| `xattr-rm` | `<filepath> <attr>` | Remove an extended attribute. Silent if not present. |
| `copy` | `<src> <dst>` | Copy file or directory using `ditto` (preserves macOS metadata, resource forks, xattrs). |
| `trash` | `<filepath>` | Move file to Trash via Finder AppleScript (recoverable). |

**Argument constraints:**
- `<query>` — Spotlight query string (same syntax as Spotlight). Quote multi-word queries.
- `[dir]` — optional directory path to scope the search (default: `/` for `search`/`search-name`; `$HOME` for `search-kind`)
- `<kind>` — case-insensitive kind string matched against `kMDItemKind`. Values: `image`, `pdf`, `music`, `movie`, `text`, `folder`
- `<filepath>` — absolute or relative path; must exist (validated before each operation except `xattr-rm`)
- `<attr>` — extended attribute name, e.g., `com.apple.quarantine`
- `<src>`, `<dst>` — source and destination paths for copy

## Usage

```bash
# Spotlight full-text search
ostwin mac finder search "kind:pdf budget 2025"
ostwin mac finder search "machine learning" ~/Documents

# Find by filename
ostwin mac finder search-name "README.md" ~/Projects
ostwin mac finder search-name "*.xcodeproj"

# Find by file kind
ostwin mac finder search-kind image ~/Pictures
ostwin mac finder search-kind pdf ~/Downloads

# Quick Look preview
ostwin mac finder preview ~/Desktop/report.pdf

# Reveal in Finder
ostwin mac finder reveal /tmp/output.png

# Extended attributes
ostwin mac finder xattr-list ~/Downloads/app.dmg
ostwin mac finder xattr-get ~/Downloads/app.dmg com.apple.quarantine
ostwin mac finder xattr-set myfile.txt com.apple.metadata:tag "reviewed"
ostwin mac finder xattr-rm ~/Downloads/app.dmg com.apple.quarantine

# Copy preserving metadata
ostwin mac finder copy ~/src/ ~/dst/

# Move to Trash (recoverable)
ostwin mac finder trash /tmp/old-file.txt
```

## Daemon Dispatch

```bash
# Search files
printf '{"script":"finder","cmd":"search-name","args":"README.md /Users/me/Projects"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# Spotlight search
printf '{"script":"finder","cmd":"search","args":"kind:pdf budget"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# BSD nc fallback
printf '{"script":"finder","cmd":"search-kind","args":"image ~/Pictures"}' | /usr/bin/nc -U /tmp/ostwin-macos-host.sock
```

## Direct CLI Patterns

```bash
# Spotlight search
mdfind -onlyin ~/Documents "budget"
mdfind -name "*.pdf"
mdfind "kMDItemKind == 'PDF Document'"

# Extended attributes
xattr -l file.txt                              # list all with values
xattr -d com.apple.quarantine file.zip         # remove quarantine flag
xattr -w user.note "reviewed" file.txt         # write custom attribute

# Copy with full metadata preservation
ditto source/ dest/
ditto -c -k --sequesterRsrc src/ archive.zip   # create zip preserving metadata

# Quick Look
qlmanage -p file.pdf                           # preview
qlmanage -t file.pdf -o /tmp/                  # generate thumbnail
```

## Common Spotlight Attributes

| Attribute | Description |
|-----------|-------------|
| `kMDItemDisplayName` | File display name |
| `kMDItemKind` | e.g., `"PDF Document"`, `"JPEG image"` |
| `kMDItemContentType` | UTI, e.g., `"public.pdf"`, `"public.jpeg"` |
| `kMDItemFSSize` | File size in bytes |
| `kMDItemContentCreationDate` | Creation date |
| `kMDItemLastUsedDate` | Last opened date |

## Rules

- **Prefer `trash` over `rm`**: Trash is recoverable; `rm` is not.
- **Prefer `copy` (`ditto`) over `cp -r`**: `ditto` preserves resource forks, xattrs, and ACLs.
- `mdfind` relies on Spotlight indexing. If indexing is disabled or stale for a volume, results may be incomplete.
- Removing `com.apple.quarantine` lets a downloaded file bypass Gatekeeper — use with caution.
