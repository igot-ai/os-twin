#!/usr/bin/env bash
# finder.sh — macOS file and Finder operations via mdfind, xattr, ditto, qlmanage
# Usage: finder.sh <cmd> [args]
# Requires: macOS bash 3.2+, Spotlight enabled
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_lib.sh"

CMD="${1:-help}"
shift || true

usage() {
  cat <<EOF
Usage: finder.sh <cmd> [args]

Commands:
  search <query> [dir]              Spotlight search (mdfind)
  search-name <filename> [dir]      Find files by name
  search-kind <kind> [dir]          Find by kind (image, pdf, music, movie, etc.)
  preview <filepath>                Quick Look preview a file
  reveal <filepath>                 Reveal file in Finder
  xattr-list <filepath>             List extended attributes
  xattr-get <filepath> <attr>       Read an extended attribute
  xattr-set <filepath> <attr> <val> Write an extended attribute
  xattr-rm <filepath> <attr>        Remove an extended attribute
  copy <src> <dst>                  Copy file/dir preserving metadata (ditto)
  trash <filepath>                  Move file to Trash
  help                              Show this help

Examples:
  finder.sh search "kind:pdf budget"
  finder.sh search-name "README.md" ~/Projects
  finder.sh search-kind image ~/Pictures
  finder.sh preview report.pdf
  finder.sh reveal /tmp/output.png
  finder.sh copy src/ dst/
  finder.sh trash /tmp/old-file.txt
EOF
}

case "$CMD" in
  search)
    QUERY="${1:?Usage: finder.sh search <query> [dir]}"
    DIR="${2:-/}"
    mdfind -onlyin "$DIR" "$QUERY"
    ;;

  search-name)
    FILENAME="${1:?Usage: finder.sh search-name <filename> [dir]}"
    DIR="${2:-/}"
    mdfind -onlyin "$DIR" -name "$FILENAME"
    ;;

  search-kind)
    KIND="${1:?Usage: finder.sh search-kind <kind> [dir]}"
    DIR="${2:-$HOME}"
    mdfind -onlyin "$DIR" "kMDItemKind == '*$KIND*'cd"
    ;;

  preview)
    FILEPATH="${1:?Usage: finder.sh preview <filepath>}"
    [ -e "$FILEPATH" ] || { echo "Error: file not found: $FILEPATH" >&2; exit 1; }
    qlmanage -p "$FILEPATH" >/dev/null 2>&1 &
    echo "Preview opened: $FILEPATH"
    ;;

  reveal)
    FILEPATH="${1:?Usage: finder.sh reveal <filepath>}"
    [ -e "$FILEPATH" ] || { echo "Error: file not found: $FILEPATH" >&2; exit 1; }
    open -R "$FILEPATH"
    echo "Revealed in Finder: $FILEPATH"
    ;;

  xattr-list)
    FILEPATH="${1:?Usage: finder.sh xattr-list <filepath>}"
    [ -e "$FILEPATH" ] || { echo "Error: file not found: $FILEPATH" >&2; exit 1; }
    xattr "$FILEPATH"
    ;;

  xattr-get)
    FILEPATH="${1:?Usage: finder.sh xattr-get <filepath> <attr>}"
    ATTR="${2:?Missing attribute name}"
    [ -e "$FILEPATH" ] || { echo "Error: file not found: $FILEPATH" >&2; exit 1; }
    xattr -p "$ATTR" "$FILEPATH"
    ;;

  xattr-set)
    FILEPATH="${1:?Usage: finder.sh xattr-set <filepath> <attr> <value>}"
    ATTR="${2:?Missing attribute name}"
    VAL="${3:?Missing value}"
    [ -e "$FILEPATH" ] || { echo "Error: file not found: $FILEPATH" >&2; exit 1; }
    xattr -w "$ATTR" "$VAL" "$FILEPATH"
    echo "Set $ATTR on $FILEPATH"
    ;;

  xattr-rm)
    FILEPATH="${1:?Usage: finder.sh xattr-rm <filepath> <attr>}"
    ATTR="${2:?Missing attribute name}"
    [ -e "$FILEPATH" ] || { echo "Error: file not found: $FILEPATH" >&2; exit 1; }
    xattr -d "$ATTR" "$FILEPATH" 2>/dev/null || echo "Attribute not found: $ATTR"
    echo "Removed $ATTR from $FILEPATH"
    ;;

  copy)
    SRC="${1:?Usage: finder.sh copy <src> <dst>}"
    DST="${2:?Missing destination}"
    [ -e "$SRC" ] || { echo "Error: source not found: $SRC" >&2; exit 1; }
    ditto "$SRC" "$DST"
    echo "Copied: $SRC -> $DST"
    ;;

  trash)
    FILEPATH="${1:?Usage: finder.sh trash <filepath>}"
    [ -e "$FILEPATH" ] || { echo "Error: file not found: $FILEPATH" >&2; exit 1; }
    run_osascript "tell application \"Finder\" to delete POSIX file \"$(cd "$(dirname "$FILEPATH")" && pwd)/$(basename "$FILEPATH")\"" || exit $?
    echo "Trashed: $FILEPATH"
    ;;

  help|--help|-h)
    usage
    ;;

  *)
    echo "Unknown command: $CMD" >&2
    usage >&2
    exit 1
    ;;
esac
