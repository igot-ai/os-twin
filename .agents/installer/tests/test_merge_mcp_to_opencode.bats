#!/usr/bin/env bats
# Tests for merge_mcp_to_opencode.py and inject_env_to_mcp.py

INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
SCRIPTS_DIR="$INSTALLER_DIR/scripts"
MCP_MODULE_DIR="$INSTALLER_DIR/../mcp"

setup() {
  TEST_DIR=$(mktemp -d)
  export PYTHON="${PYTHON:-python3}"
}

teardown() {
  rm -rf "$TEST_DIR"
}

# ─── inject_env_to_mcp.py tests ──────────────────────────────────────────────

@test "inject_env_to_mcp resolves {env:VAR} placeholders" {
  # Create MCP config with placeholders
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "test": {
      "type": "local",
      "command": ["{env:OSTWIN_PYTHON}", "-m", "server"],
      "environment": {
        "AGENT_DIR": "{env:AGENT_DIR}",
        "OSTWIN_PYTHON": "{env:OSTWIN_PYTHON}"
      }
    }
  }
}
JSONEOF

  # Create .env file
  cat > "$TEST_DIR/.env" <<'ENVEOF'
AGENT_DIR=/home/user/.ostwin
OSTWIN_PYTHON=/home/user/.ostwin/.venv/bin/python
ENVEOF

  # Run injection
  "$PYTHON" "$SCRIPTS_DIR/inject_env_to_mcp.py" "$TEST_DIR/mcp.json" "$TEST_DIR/.env"

  # Verify placeholders were resolved
  grep -q '"AGENT_DIR": "/home/user/.ostwin"' "$TEST_DIR/mcp.json"
  grep -q '"OSTWIN_PYTHON": "/home/user/.ostwin/.venv/bin/python"' "$TEST_DIR/mcp.json"
}

@test "inject_env_to_mcp resolves shell dollar-var syntax" {
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "test": {
      "type": "local",
      "command": ["${OSTWIN_PYTHON}", "server.py"],
      "environment": {
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}"
      }
    }
  }
}
JSONEOF

  cat > "$TEST_DIR/.env" <<'ENVEOF'
GOOGLE_API_KEY=test-api-key-123
OSTWIN_PYTHON=/opt/ostwin/.venv/bin/python
ENVEOF

  "$PYTHON" "$SCRIPTS_DIR/inject_env_to_mcp.py" "$TEST_DIR/mcp.json" "$TEST_DIR/.env"

  grep -q '"GOOGLE_API_KEY": "test-api-key-123"' "$TEST_DIR/mcp.json"
}

@test "inject_env_to_mcp handles multiple servers" {
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "channel": {
      "type": "local",
      "command": ["python", "channel.py"],
      "environment": {
        "GOOGLE_API_KEY": "{env:GOOGLE_API_KEY}"
      }
    },
    "warroom": {
      "type": "local",
      "command": ["python", "warroom.py"],
      "environment": {
        "GOOGLE_API_KEY": "{env:GOOGLE_API_KEY}"
      }
    }
  }
}
JSONEOF

  cat > "$TEST_DIR/.env" <<'ENVEOF'
GOOGLE_API_KEY=shared-key
ENVEOF

  "$PYTHON" "$SCRIPTS_DIR/inject_env_to_mcp.py" "$TEST_DIR/mcp.json" "$TEST_DIR/.env"

  # Both servers should have the same key resolved
  grep -q '"GOOGLE_API_KEY": "shared-key"' "$TEST_DIR/mcp.json"
  
  # Count occurrences - should be 2
  COUNT=$(grep -c '"GOOGLE_API_KEY": "shared-key"' "$TEST_DIR/mcp.json" || echo 0)
  [[ "$COUNT" -eq 2 ]]
}

@test "inject_env_to_mcp handles quoted values" {
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "test": {
      "type": "local",
      "command": ["python"],
      "environment": {
        "QUOTED_KEY": "{env:QUOTED_KEY}",
        "SINGLE_QUOTED_KEY": "{env:SINGLE_QUOTED_KEY}"
      }
    }
  }
}
JSONEOF

  cat > "$TEST_DIR/.env" <<'ENVEOF'
QUOTED_KEY="value with spaces"
SINGLE_QUOTED_KEY='another value'
ENVEOF

  "$PYTHON" "$SCRIPTS_DIR/inject_env_to_mcp.py" "$TEST_DIR/mcp.json" "$TEST_DIR/.env"

  grep -q '"QUOTED_KEY": "value with spaces"' "$TEST_DIR/mcp.json"
  grep -q '"SINGLE_QUOTED_KEY": "another value"' "$TEST_DIR/mcp.json"
}

# ─── merge_mcp_to_opencode.py tests ──────────────────────────────────────────

@test "merge_mcp_to_opencode creates valid opencode.json" {
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "channel": {
      "type": "local",
      "command": ["python", "channel.py"],
      "environment": {
        "KEY": "val"
      }
    }
  }
}
JSONEOF

  "$PYTHON" "$SCRIPTS_DIR/merge_mcp_to_opencode.py" "$TEST_DIR/mcp.json" "$TEST_DIR/opencode.json" "$MCP_MODULE_DIR"

  # Check schema
  grep -q '"$schema": "https://opencode.ai/config.json"' "$TEST_DIR/opencode.json"
  
  # Check enabled flag added
  grep -q '"enabled": true' "$TEST_DIR/opencode.json"
}

@test "merge_mcp_to_opencode drops unresolved {env:VAR} in environment" {
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "test": {
      "type": "local",
      "command": ["python", "server.py"],
      "environment": {
        "RESOLVED_KEY": "actual-value",
        "UNRESOLVED_KEY": "{env:NONEXISTENT_VAR}"
      }
    }
  }
}
JSONEOF

  "$PYTHON" "$SCRIPTS_DIR/merge_mcp_to_opencode.py" "$TEST_DIR/mcp.json" "$TEST_DIR/opencode.json" "$MCP_MODULE_DIR"

  # Resolved key should remain
  grep -q '"RESOLVED_KEY": "actual-value"' "$TEST_DIR/opencode.json"
  
  # Unresolved key should be dropped
  ! grep -q "UNRESOLVED_KEY" "$TEST_DIR/opencode.json"
}

@test "merge_mcp_to_opencode preserves existing user settings" {
  # Create existing opencode.json with user settings
  cat > "$TEST_DIR/opencode.json" <<'JSONEOF'
{
  "$schema": "https://opencode.ai/config.json",
  "theme": "dracula",
  "keybinds": {
    "ctrl+p": "palette"
  }
}
JSONEOF

  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "channel": {
      "type": "local",
      "command": ["python", "channel.py"],
      "environment": {
        "KEY": "val"
      }
    }
  }
}
JSONEOF

  "$PYTHON" "$SCRIPTS_DIR/merge_mcp_to_opencode.py" "$TEST_DIR/mcp.json" "$TEST_DIR/opencode.json" "$MCP_MODULE_DIR"

  # User settings preserved
  grep -q '"theme": "dracula"' "$TEST_DIR/opencode.json"
  grep -q '"ctrl+p": "palette"' "$TEST_DIR/opencode.json"
}

@test "merge_mcp_to_opencode does not rewrite unchanged config" {
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "channel": {
      "type": "local",
      "command": ["python", "channel.py"],
      "environment": {
        "KEY": "val"
      }
    }
  }
}
JSONEOF

  "$PYTHON" "$SCRIPTS_DIR/merge_mcp_to_opencode.py" "$TEST_DIR/mcp.json" "$TEST_DIR/opencode.json" "$MCP_MODULE_DIR"

  touch -t 200001010000 "$TEST_DIR/opencode.json"
  before_mtime="$("$PYTHON" -c 'import os,sys; print(os.stat(sys.argv[1]).st_mtime_ns)' "$TEST_DIR/opencode.json")"

  run "$PYTHON" "$SCRIPTS_DIR/merge_mcp_to_opencode.py" "$TEST_DIR/mcp.json" "$TEST_DIR/opencode.json" "$MCP_MODULE_DIR"

  [ "$status" -eq 0 ]
  [[ "$output" == *"already up to date"* ]]

  after_mtime="$("$PYTHON" -c 'import os,sys; print(os.stat(sys.argv[1]).st_mtime_ns)' "$TEST_DIR/opencode.json")"
  [ "$before_mtime" = "$after_mtime" ]
}

@test "merge_mcp_to_opencode skips invalid servers" {
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "good": {
      "type": "local",
      "command": ["python", "good.py"],
      "environment": {
        "KEY": "val"
      }
    },
    "bad": {
      "type": "local"
    }
  }
}
JSONEOF

  "$PYTHON" "$SCRIPTS_DIR/merge_mcp_to_opencode.py" "$TEST_DIR/mcp.json" "$TEST_DIR/opencode.json" "$MCP_MODULE_DIR"

  # Good server should be present
  grep -q '"good"' "$TEST_DIR/opencode.json"
  
  # Bad server should be skipped
  ! grep -q '"bad"' "$TEST_DIR/opencode.json"
}

@test "merge_mcp_to_opencode adds core servers to privileged agents" {
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "channel": {
      "type": "local",
      "command": ["python", "channel.py"],
      "environment": {
        "KEY": "val"
      }
    },
    "github": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
      "environment": {
        "TOKEN": "test"
      }
    }
  }
}
JSONEOF

  "$PYTHON" "$SCRIPTS_DIR/merge_mcp_to_opencode.py" "$TEST_DIR/mcp.json" "$TEST_DIR/opencode.json" "$MCP_MODULE_DIR"

  # Check tools deny - channel is core (not denied), github is denied
  # Note: the key is literally "github*" (with asterisk) — escape it for grep regex
  grep -q '"github\*": false' "$TEST_DIR/opencode.json"
  ! grep -q '"channel\*": false' "$TEST_DIR/opencode.json"
  
  # Check agent config exists
  grep -q '"agent"' "$TEST_DIR/opencode.json"
  grep -q '"manager"' "$TEST_DIR/opencode.json"
  grep -q '"architect"' "$TEST_DIR/opencode.json"
  grep -q '"qa"' "$TEST_DIR/opencode.json"
}

@test "merge_mcp_to_opencode resolves {env:VAR} placeholders in command arrays" {
  # Since commit 1d867a1 ("fix: resolve bare python to venv path"),
  # {env:OSTWIN_PYTHON} and {env:AGENT_DIR} are resolved to absolute paths
  # during merge. OpenCode needs real paths, not placeholders, in commands.
  # Unknown {env:VAR} refs that can't be resolved are kept as-is.
  cat > "$TEST_DIR/mcp.json" <<'JSONEOF'
{
  "mcp": {
    "channel": {
      "type": "local",
      "command": ["{env:OSTWIN_PYTHON}", "{env:AGENT_DIR}/mcp/channel-server.py"],
      "environment": {
        "KEY": "val"
      }
    }
  }
}
JSONEOF

  "$PYTHON" "$SCRIPTS_DIR/merge_mcp_to_opencode.py" "$TEST_DIR/mcp.json" "$TEST_DIR/opencode.json" "$MCP_MODULE_DIR"

  # Known {env:} refs should be resolved to absolute paths
  ! grep -q '"{env:OSTWIN_PYTHON}"' "$TEST_DIR/opencode.json"
  ! grep -q '"{env:AGENT_DIR}' "$TEST_DIR/opencode.json"

  # Command should contain resolved paths (python binary and script path)
  grep -q '"command"' "$TEST_DIR/opencode.json"
  grep -q 'channel-server.py' "$TEST_DIR/opencode.json"
}
