#!/usr/bin/env bash
# mcp-server.sh — MCP stdio server wrapping the macOS automation scripts.
#
# Implements the Model Context Protocol (MCP) over stdin/stdout using JSON-RPC 2.0.
# Each macOS script becomes an MCP tool with typed parameters.
#
# Usage (stdio mode — launched by an MCP client):
#   bash .agents/daemons/macos-host/mcp-server.sh
#
# MCP client config (~/.ostwin/mcp/mcp-config.json):
#   {
#     "mcpServers": {
#       "macos-host": {
#         "command": "bash",
#         "args": [".agents/daemons/macos-host/mcp-server.sh"],
#         "type": "stdio"
#       }
#     }
#   }
#
# Requires: macOS bash 3.2+, scripts in .agents/scripts/macos/
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OSTWIN_HOME="${OSTWIN_HOME:-$HOME/.ostwin}"
# Resolve scripts dir: prefer installed location, fall back to repo
if [ -d "$OSTWIN_HOME/.agents/scripts/macos" ]; then
  SCRIPTS_DIR="$OSTWIN_HOME/.agents/scripts/macos"
elif [ -d "$SCRIPT_DIR/../../scripts/macos" ]; then
  SCRIPTS_DIR="$(cd "$SCRIPT_DIR/../../scripts/macos" && pwd)"
else
  echo '{"jsonrpc":"2.0","error":{"code":-32603,"message":"scripts/macos dir not found"}}' >&2
  exit 1
fi

# ── JSON helpers (bash 3.2 safe — no jq dependency) ─────────────────────────

json_get() {
  local json="$1" key="$2"
  local pair
  pair=$(printf '%s' "$json" | grep -o "\"$key\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" 2>/dev/null | head -1) || { echo ""; return; }
  printf '%s' "$pair" | rev | cut -d'"' -f2 | rev
}

json_get_raw() {
  # Extract a raw value (string, number, object, array) for a key
  local json="$1" key="$2"
  printf '%s' "$json" | grep -o "\"$key\"[[:space:]]*:[[:space:]]*[^,}]*" 2>/dev/null | head -1 | sed "s/\"$key\"[[:space:]]*:[[:space:]]*//"
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ' | tr '\t' ' '
}

# ── Tool definitions ────────────────────────────────────────────────────────

TOOLS_JSON='{
  "tools": [
    {
      "name": "macos_app",
      "description": "Control macOS application lifecycle: launch, kill, frontmost, list, is-running",
      "inputSchema": {
        "type": "object",
        "properties": {
          "cmd": {"type": "string", "enum": ["launch","kill","frontmost","list","is-running"]},
          "app_name": {"type": "string", "description": "Application name (for launch, kill, is-running)"}
        },
        "required": ["cmd"]
      }
    },
    {
      "name": "macos_window",
      "description": "Control macOS window geometry: move, resize, set-bounds, minimize, restore, fullscreen, get-bounds",
      "inputSchema": {
        "type": "object",
        "properties": {
          "cmd": {"type": "string", "enum": ["move","resize","set-bounds","minimize","restore","fullscreen","get-bounds"]},
          "app_name": {"type": "string"},
          "x": {"type": "integer"}, "y": {"type": "integer"},
          "w": {"type": "integer"}, "h": {"type": "integer"}
        },
        "required": ["cmd","app_name"]
      }
    },
    {
      "name": "macos_click",
      "description": "Simulate mouse clicks: click, double-click, right-click, move cursor",
      "inputSchema": {
        "type": "object",
        "properties": {
          "cmd": {"type": "string", "enum": ["click","double-click","right-click","move"]},
          "x": {"type": "integer"}, "y": {"type": "integer"}
        },
        "required": ["cmd","x","y"]
      }
    },
    {
      "name": "macos_type",
      "description": "Simulate keyboard input: type text, key codes, modifier combos",
      "inputSchema": {
        "type": "object",
        "properties": {
          "cmd": {"type": "string", "enum": ["text","key","combo","hold"]},
          "text": {"type": "string", "description": "Text to type (for text cmd)"},
          "keycode": {"type": "integer", "description": "Key code (for key/hold cmd)"},
          "key": {"type": "string", "description": "Key character (for combo cmd)"},
          "modifiers": {"type": "string", "description": "Space-separated modifiers: command option control shift"},
          "ms": {"type": "integer", "description": "Hold duration in ms (for hold cmd)"}
        },
        "required": ["cmd"]
      }
    },
    {
      "name": "macos_capture",
      "description": "Take screenshots: full screen, region, window, clipboard",
      "inputSchema": {
        "type": "object",
        "properties": {
          "cmd": {"type": "string", "enum": ["full","region","window","clipboard"]},
          "app_name": {"type": "string", "description": "App name (for window capture)"},
          "x": {"type": "integer"}, "y": {"type": "integer"},
          "w": {"type": "integer"}, "h": {"type": "integer"},
          "outfile": {"type": "string"}
        },
        "required": ["cmd"]
      }
    },
    {
      "name": "macos_system",
      "description": "Control system settings: volume, wifi, dark-mode, clipboard, notify, defaults",
      "inputSchema": {
        "type": "object",
        "properties": {
          "cmd": {"type": "string", "enum": ["volume","volume-get","mute","wifi","wifi-status","dark-mode","dark-mode-get","clipboard-get","clipboard-set","notify","sleep","display-sleep","default-read","default-write"]},
          "value": {"type": "string", "description": "Value for the command"},
          "value2": {"type": "string", "description": "Second value (e.g. message for notify, key for default-read)"},
          "value3": {"type": "string", "description": "Third value (e.g. type for default-write)"},
          "value4": {"type": "string", "description": "Fourth value (e.g. value for default-write)"}
        },
        "required": ["cmd"]
      }
    },
    {
      "name": "macos_finder",
      "description": "File operations: Spotlight search, xattr, copy (ditto), trash, preview, reveal",
      "inputSchema": {
        "type": "object",
        "properties": {
          "cmd": {"type": "string", "enum": ["search","search-name","search-kind","preview","reveal","xattr-list","xattr-get","xattr-set","xattr-rm","copy","trash"]},
          "path": {"type": "string"}, "path2": {"type": "string"},
          "query": {"type": "string"}, "attr": {"type": "string"}, "value": {"type": "string"}
        },
        "required": ["cmd"]
      }
    },
    {
      "name": "macos_axbridge",
      "description": "Accessibility API bridge: inspect UI trees, read text, find/click buttons, menu clicks",
      "inputSchema": {
        "type": "object",
        "properties": {
          "cmd": {"type": "string", "enum": ["ui-tree","read-text","find-button","click-button","read-focused","menu-click","window-list"]},
          "app_name": {"type": "string"}, "role": {"type": "string"},
          "label": {"type": "string"}, "menu": {"type": "string"}, "item": {"type": "string"},
          "depth": {"type": "integer"}
        },
        "required": ["cmd"]
      }
    }
  ]
}'

# ── Build script args from tool parameters ──────────────────────────────────

build_args() {
  local tool="$1" params="$2"
  local cmd app val val2 val3 val4 x y w h outfile text keycode key mods ms
  local path path2 query attr role label menu item depth
  cmd=$(json_get "$params" "cmd")

  case "$tool" in
    macos_app)
      app=$(json_get "$params" "app_name")
      echo "$cmd $app"
      ;;
    macos_window)
      app=$(json_get "$params" "app_name")
      x=$(json_get "$params" "x"); y=$(json_get "$params" "y")
      w=$(json_get "$params" "w"); h=$(json_get "$params" "h")
      case "$cmd" in
        move)       echo "$cmd $app $x $y" ;;
        resize)     echo "$cmd $app $w $h" ;;
        set-bounds) echo "$cmd $app $x $y $w $h" ;;
        *)          echo "$cmd $app" ;;
      esac
      ;;
    macos_click)
      x=$(json_get "$params" "x"); y=$(json_get "$params" "y")
      echo "$cmd $x $y"
      ;;
    macos_type)
      case "$cmd" in
        text)
          text=$(json_get "$params" "text")
          echo "text $text"
          ;;
        key)
          keycode=$(json_get "$params" "keycode")
          echo "key $keycode"
          ;;
        combo)
          key=$(json_get "$params" "key")
          mods=$(json_get "$params" "modifiers")
          echo "combo $key $mods"
          ;;
        hold)
          keycode=$(json_get "$params" "keycode")
          ms=$(json_get "$params" "ms")
          echo "hold $keycode $ms"
          ;;
      esac
      ;;
    macos_capture)
      app=$(json_get "$params" "app_name")
      x=$(json_get "$params" "x"); y=$(json_get "$params" "y")
      w=$(json_get "$params" "w"); h=$(json_get "$params" "h")
      outfile=$(json_get "$params" "outfile")
      case "$cmd" in
        full)     echo "full $outfile" ;;
        region)   echo "region $x $y $w $h $outfile" ;;
        window)   echo "window $app $outfile" ;;
        clipboard) echo "clipboard" ;;
      esac
      ;;
    macos_system)
      val=$(json_get "$params" "value")
      val2=$(json_get "$params" "value2")
      val3=$(json_get "$params" "value3")
      val4=$(json_get "$params" "value4")
      case "$cmd" in
        notify)         echo "notify $val $val2" ;;
        default-read)   echo "default-read $val $val2" ;;
        default-write)  echo "default-write $val $val2 $val3 $val4" ;;
        clipboard-set)  echo "clipboard-set $val" ;;
        *)              echo "$cmd $val" ;;
      esac
      ;;
    macos_finder)
      path=$(json_get "$params" "path")
      path2=$(json_get "$params" "path2")
      query=$(json_get "$params" "query")
      attr=$(json_get "$params" "attr")
      val=$(json_get "$params" "value")
      case "$cmd" in
        search)       echo "search $query $path" ;;
        search-name)  echo "search-name $query $path" ;;
        search-kind)  echo "search-kind $query $path" ;;
        xattr-get)    echo "xattr-get $path $attr" ;;
        xattr-set)    echo "xattr-set $path $attr $val" ;;
        xattr-rm)     echo "xattr-rm $path $attr" ;;
        copy)         echo "copy $path $path2" ;;
        *)            echo "$cmd $path" ;;
      esac
      ;;
    macos_axbridge)
      app=$(json_get "$params" "app_name")
      role=$(json_get "$params" "role")
      label=$(json_get "$params" "label")
      menu=$(json_get "$params" "menu")
      item=$(json_get "$params" "item")
      depth=$(json_get "$params" "depth")
      case "$cmd" in
        ui-tree)       echo "ui-tree $app ${depth:-3}" ;;
        read-text)     echo "read-text $app $role" ;;
        find-button)   echo "find-button $app $label" ;;
        click-button)  echo "click-button $app $label" ;;
        menu-click)    echo "menu-click $app $menu $item" ;;
        window-list)   echo "window-list $app" ;;
        read-focused)  echo "read-focused" ;;
      esac
      ;;
  esac
}

# Map tool name to script filename
tool_to_script() {
  case "$1" in
    macos_app)       echo "app" ;;
    macos_window)    echo "window" ;;
    macos_click)     echo "click" ;;
    macos_type)      echo "type" ;;
    macos_capture)   echo "capture" ;;
    macos_system)    echo "system" ;;
    macos_finder)    echo "finder" ;;
    macos_axbridge)  echo "axbridge" ;;
    *) echo "" ;;
  esac
}

# ── JSON-RPC request handler ────────────────────────────────────────────────

handle_jsonrpc() {
  local line="$1"
  local method id params tool_name

  method=$(json_get "$line" "method")
  id=$(json_get_raw "$line" "id")
  [ -z "$id" ] && id="null"

  case "$method" in
    initialize)
      printf '{"jsonrpc":"2.0","id":%s,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"ostwin-macos-host","version":"1.0.0"}}}\n' "$id"
      ;;

    notifications/initialized)
      # No response needed for notification
      ;;

    tools/list)
      printf '{"jsonrpc":"2.0","id":%s,"result":%s}\n' "$id" "$TOOLS_JSON"
      ;;

    tools/call)
      # Extract tool name and arguments
      tool_name=$(json_get "$line" "name")
      # Extract the params/arguments object (everything after "arguments":)
      local args_json
      args_json=$(printf '%s' "$line" | grep -o '"arguments"[[:space:]]*:[[:space:]]*{[^}]*}' | sed 's/"arguments"[[:space:]]*:[[:space:]]*//')
      [ -z "$args_json" ] && args_json='{}'

      local script_name
      script_name=$(tool_to_script "$tool_name")
      if [ -z "$script_name" ]; then
        printf '{"jsonrpc":"2.0","id":%s,"result":{"content":[{"type":"text","text":"Unknown tool: %s"}],"isError":true}}\n' "$id" "$tool_name"
        return
      fi

      local script_path="$SCRIPTS_DIR/${script_name}.sh"
      if [ ! -f "$script_path" ]; then
        printf '{"jsonrpc":"2.0","id":%s,"result":{"content":[{"type":"text","text":"Script not found: %s"}],"isError":true}}\n' "$id" "$script_name"
        return
      fi

      # Build the command arguments
      local cmd_args
      cmd_args=$(build_args "$tool_name" "$args_json")

      # Execute
      local output exit_code
      # shellcheck disable=SC2086
      output=$(bash "$script_path" $cmd_args 2>&1) && exit_code=0 || exit_code=$?
      local escaped_output
      escaped_output=$(json_escape "$output")

      if [ "$exit_code" -eq 0 ]; then
        printf '{"jsonrpc":"2.0","id":%s,"result":{"content":[{"type":"text","text":"%s"}]}}\n' "$id" "$escaped_output"
      else
        printf '{"jsonrpc":"2.0","id":%s,"result":{"content":[{"type":"text","text":"%s"}],"isError":true}}\n' "$id" "$escaped_output"
      fi
      ;;

    *)
      printf '{"jsonrpc":"2.0","id":%s,"error":{"code":-32601,"message":"Method not found: %s"}}\n' "$id" "$method"
      ;;
  esac
}

# ── Main loop: read JSON-RPC from stdin, write responses to stdout ──────────

while IFS= read -r line; do
  [ -z "$line" ] && continue
  handle_jsonrpc "$line"
done
