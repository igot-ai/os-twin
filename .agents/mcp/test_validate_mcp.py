#!/usr/bin/env python3
"""Unit tests for validate_mcp.py — MCP server config validation."""

import json
import os
import sys
import tempfile
import unittest

# Add mcp dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_mcp import (
    validate_mcp_server,
    validate_mcp_config,
    normalize_mcp_server,
    normalize_mcp_config,
    merge_mcp_configs,
    _convert_shell_vars,
)


# ─── _convert_shell_vars() ──────────────────────────────────────────────────


class TestConvertShellVars(unittest.TestCase):
    """Convert shell ${VAR} / ${VAR:-default} to OpenCode {env:VAR}."""

    def test_simple_var(self):
        self.assertEqual(_convert_shell_vars("${HOME}"), "{env:HOME}")

    def test_bare_dollar_var(self):
        self.assertEqual(_convert_shell_vars("$HOME"), "{env:HOME}")

    def test_var_in_path(self):
        self.assertEqual(
            _convert_shell_vars("${HOME}/.ostwin/.agents/mcp/server.py"),
            "{env:HOME}/.ostwin/.agents/mcp/server.py",
        )

    def test_var_with_default_uses_default(self):
        result = _convert_shell_vars("${OSTWIN_PYTHON:-python}")
        self.assertEqual(result, "python")

    def test_var_with_nested_default(self):
        """${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python} → resolve default."""
        result = _convert_shell_vars(
            "${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}"
        )
        self.assertEqual(result, "{env:HOME}/.ostwin/.venv/bin/python")

    def test_multiple_vars(self):
        result = _convert_shell_vars("${HOME}/${USER}/file")
        self.assertEqual(result, "{env:HOME}/{env:USER}/file")

    def test_no_vars(self):
        self.assertEqual(_convert_shell_vars("plain text"), "plain text")

    def test_non_string(self):
        self.assertEqual(_convert_shell_vars(42), 42)
        self.assertIsNone(_convert_shell_vars(None))

    def test_already_opencode_format(self):
        """Strings already in {env:*} format should pass through unchanged."""
        self.assertEqual(
            _convert_shell_vars("{env:GOOGLE_API_KEY}"), "{env:GOOGLE_API_KEY}"
        )


# ─── normalize_mcp_server() ─────────────────────────────────────────────────


class TestNormalizeMcpServer(unittest.TestCase):
    """Normalize legacy server configs to OpenCode format."""

    def test_already_opencode_format(self):
        """Config already in OpenCode format should pass through unchanged."""
        cfg = {
            "type": "local",
            "command": ["npx", "-y", "my-mcp"],
            "environment": {"KEY": "val"},
        }
        result = normalize_mcp_server("test", cfg)
        self.assertEqual(result["type"], "local")
        self.assertEqual(result["command"], ["npx", "-y", "my-mcp"])
        self.assertEqual(result["environment"]["KEY"], "val")

    def test_command_string_to_array(self):
        """command as string → split into array."""
        cfg = {"command": "npx -y @modelcontextprotocol/server-github", "env": {"K": "v"}}
        result = normalize_mcp_server("github", cfg)
        self.assertEqual(result["command"], ["npx", "-y", "@modelcontextprotocol/server-github"])
        self.assertEqual(result["type"], "local")

    def test_command_plus_args_merged(self):
        """command + args → merged into single command array."""
        cfg = {
            "command": "${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}",
            "args": ["${HOME}/.ostwin/.agents/mcp/channel-server.py"],
            "env": {"AGENT_OS_ROOT": "."},
        }
        result = normalize_mcp_server("channel", cfg)
        self.assertIsInstance(result["command"], list)
        self.assertEqual(len(result["command"]), 2)
        # First element: ${OSTWIN_PYTHON:-...} resolves to the default
        self.assertIn(".ostwin/.venv/bin/python", result["command"][0])
        # Second element: args merged in, ${HOME} converted
        self.assertIn("{env:HOME}", result["command"][1])

    def test_env_to_environment(self):
        """'env' key → 'environment' key."""
        cfg = {
            "command": "npx my-mcp",
            "env": {"GOOGLE_API_KEY": "${GOOGLE_API_KEY}", "AGENT_OS_ROOT": "."},
        }
        result = normalize_mcp_server("test", cfg)
        self.assertIn("environment", result)
        self.assertNotIn("env", result)
        self.assertEqual(result["environment"]["GOOGLE_API_KEY"], "{env:GOOGLE_API_KEY}")
        self.assertEqual(result["environment"]["AGENT_OS_ROOT"], ".")

    def test_httpUrl_to_remote(self):
        """'httpUrl' → type: remote + url."""
        cfg = {
            "httpUrl": "https://stitch.googleapis.com/mcp",
            "headers": {"X-Goog-Api-Key": "${MCP_STITCH_API_KEY}"},
        }
        result = normalize_mcp_server("stitch", cfg)
        self.assertEqual(result["type"], "remote")
        self.assertEqual(result["url"], "https://stitch.googleapis.com/mcp")
        self.assertNotIn("httpUrl", result)
        self.assertEqual(
            result["headers"]["X-Goog-Api-Key"], "{env:MCP_STITCH_API_KEY}"
        )

    def test_shell_vars_in_env_values(self):
        """Shell ${VAR} in env values → {env:VAR}."""
        cfg = {
            "command": "python server.py",
            "env": {
                "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
            },
        }
        result = normalize_mcp_server("test", cfg)
        self.assertEqual(result["environment"]["GOOGLE_API_KEY"], "{env:GOOGLE_API_KEY}")
        self.assertEqual(result["environment"]["ANTHROPIC_API_KEY"], "{env:ANTHROPIC_API_KEY}")
        self.assertEqual(result["environment"]["OSTWIN_API_KEY"], "{env:OSTWIN_API_KEY}")

    def test_infer_type_local(self):
        """Type inferred as 'local' when command is present."""
        cfg = {"command": "npx my-mcp", "env": {"K": "v"}}
        result = normalize_mcp_server("test", cfg)
        self.assertEqual(result["type"], "local")

    def test_infer_type_remote_from_httpUrl(self):
        cfg = {"httpUrl": "https://example.com/mcp"}
        result = normalize_mcp_server("test", cfg)
        self.assertEqual(result["type"], "remote")

    def test_infer_type_remote_from_url(self):
        cfg = {"url": "https://example.com/mcp"}
        result = normalize_mcp_server("test", cfg)
        self.assertEqual(result["type"], "remote")

    def test_passthrough_oauth(self):
        cfg = {
            "type": "remote",
            "url": "https://example.com/mcp",
            "oauth": {"clientId": "abc"},
        }
        result = normalize_mcp_server("test", cfg)
        self.assertEqual(result["oauth"]["clientId"], "abc")

    def test_passthrough_timeout(self):
        cfg = {
            "type": "local",
            "command": ["npx", "mcp"],
            "environment": {"K": "v"},
            "timeout": 10000,
        }
        result = normalize_mcp_server("test", cfg)
        self.assertEqual(result["timeout"], 10000)

    def test_not_a_dict(self):
        self.assertEqual(normalize_mcp_server("test", "garbage"), "garbage")


# ─── normalize + validate full legacy config ────────────────────────────────


class TestNormalizeLegacyConfig(unittest.TestCase):
    """End-to-end: legacy mcpServers format → normalized → validated."""

    LEGACY_CONFIG = {
        "mcpServers": {
            "channel": {
                "command": "${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}",
                "args": ["${HOME}/.ostwin/.agents/mcp/channel-server.py"],
                "env": {
                    "AGENT_OS_ROOT": ".",
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
            "warroom": {
                "command": "${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}",
                "args": ["${HOME}/.ostwin/.agents/mcp/warroom-server.py"],
                "env": {
                    "AGENT_OS_ROOT": ".",
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
            "memory": {
                "command": "${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}",
                "args": ["${HOME}/.ostwin/.agents/mcp/memory-server.py"],
                "env": {
                    "AGENT_OS_ROOT": "${AGENT_OS_PROJECT_DIR:-.}",
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
            "stitch": {
                "httpUrl": "https://stitch.googleapis.com/mcp",
                "headers": {"X-Goog-Api-Key": "${MCP_STITCH_API_KEY}"},
                "env": {
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
            "github": {
                "command": "npx -y @modelcontextprotocol/server-github",
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": "${MCP_GITHUB_GITHUB_PERSONAL_ACCESS_TOKEN}",
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
        }
    }

    def test_normalize_produces_all_servers(self):
        normalized = normalize_mcp_config(self.LEGACY_CONFIG)
        self.assertEqual(len(normalized), 5)
        for name in ("channel", "warroom", "memory", "stitch", "github"):
            self.assertIn(name, normalized)

    def test_all_normalized_servers_pass_validation(self):
        normalized = normalize_mcp_config(self.LEGACY_CONFIG)
        validated, skipped, results = validate_mcp_config(normalized)
        self.assertEqual(len(skipped), 0, f"Unexpected failures: {skipped}")
        self.assertEqual(len(validated), 5)

    def test_channel_format(self):
        normalized = normalize_mcp_config(self.LEGACY_CONFIG)
        ch = normalized["channel"]
        self.assertEqual(ch["type"], "local")
        self.assertIsInstance(ch["command"], list)
        self.assertEqual(len(ch["command"]), 2)
        self.assertIn("environment", ch)
        self.assertEqual(ch["environment"]["GOOGLE_API_KEY"], "{env:GOOGLE_API_KEY}")
        self.assertEqual(ch["environment"]["AGENT_OS_ROOT"], ".")

    def test_stitch_format(self):
        normalized = normalize_mcp_config(self.LEGACY_CONFIG)
        st = normalized["stitch"]
        self.assertEqual(st["type"], "remote")
        self.assertEqual(st["url"], "https://stitch.googleapis.com/mcp")
        self.assertNotIn("httpUrl", st)
        self.assertEqual(
            st["headers"]["X-Goog-Api-Key"], "{env:MCP_STITCH_API_KEY}"
        )

    def test_github_command_split(self):
        normalized = normalize_mcp_config(self.LEGACY_CONFIG)
        gh = normalized["github"]
        self.assertEqual(gh["type"], "local")
        self.assertEqual(gh["command"], ["npx", "-y", "@modelcontextprotocol/server-github"])
        self.assertEqual(
            gh["environment"]["GITHUB_PERSONAL_ACCESS_TOKEN"],
            "{env:MCP_GITHUB_GITHUB_PERSONAL_ACCESS_TOKEN}",
        )

    def test_memory_default_var_resolved(self):
        """${AGENT_OS_PROJECT_DIR:-.} → the default '.'"""
        normalized = normalize_mcp_config(self.LEGACY_CONFIG)
        mem = normalized["memory"]
        self.assertEqual(mem["environment"]["AGENT_OS_ROOT"], ".")

    def test_full_opencode_json_output(self):
        """Full pipeline: legacy → normalize → validate → opencode.json format."""
        normalized = normalize_mcp_config(self.LEGACY_CONFIG)
        validated, _, _ = validate_mcp_config(normalized)
        tools_deny = {f"{name}*": False for name in validated}

        opencode = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": validated,
            "tools": tools_deny,
        }

        # Schema
        self.assertEqual(opencode["$schema"], "https://opencode.ai/config.json")

        # All 5 servers present with enabled: true
        self.assertEqual(len(opencode["mcp"]), 5)
        for name, cfg in opencode["mcp"].items():
            self.assertTrue(cfg["enabled"], f"{name} missing enabled")

        # All 5 tools deny entries
        self.assertEqual(len(opencode["tools"]), 5)
        for key, val in opencode["tools"].items():
            self.assertTrue(key.endswith("*"))
            self.assertFalse(val)

        # No shell ${VAR} syntax left anywhere
        raw = json.dumps(opencode)
        self.assertNotIn("${", raw, "Shell ${VAR} syntax found in output")

        # Only {env:VAR} format (or plain values)
        import re
        env_refs = re.findall(r'\{env:\w+\}', raw)
        self.assertGreater(len(env_refs), 0, "Expected {env:*} placeholders")


# ─── merge_mcp_configs() ────────────────────────────────────────────────────


class TestMergeMcpConfigs(unittest.TestCase):
    """Merge multiple MCP configs from different formats."""

    def test_merge_legacy_and_opencode(self):
        """Merge a legacy mcpServers config with an OpenCode mcp config."""
        legacy = {
            "mcpServers": {
                "channel": {
                    "command": "python server.py",
                    "env": {"KEY": "${API_KEY}"},
                },
            }
        }
        opencode = {
            "mcp": {
                "github": {
                    "type": "local",
                    "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
                    "environment": {"TOKEN": "{env:GITHUB_TOKEN}"},
                },
            }
        }
        merged = merge_mcp_configs(legacy, opencode)
        self.assertEqual(len(merged), 2)
        self.assertIn("channel", merged)
        self.assertIn("github", merged)

        # channel was normalized from legacy
        self.assertEqual(merged["channel"]["type"], "local")
        self.assertEqual(merged["channel"]["command"], ["python", "server.py"])
        self.assertEqual(merged["channel"]["environment"]["KEY"], "{env:API_KEY}")

        # github passed through from OpenCode format
        self.assertEqual(merged["github"]["command"], ["npx", "-y", "@modelcontextprotocol/server-github"])

    def test_later_config_overrides_earlier(self):
        """When the same server name exists in multiple configs, later wins."""
        config_a = {
            "mcp": {
                "channel": {
                    "type": "local",
                    "command": ["python", "old-server.py"],
                    "environment": {"KEY": "old"},
                },
            }
        }
        config_b = {
            "mcp": {
                "channel": {
                    "type": "local",
                    "command": ["python", "new-server.py"],
                    "environment": {"KEY": "new"},
                },
            }
        }
        merged = merge_mcp_configs(config_a, config_b)
        self.assertEqual(merged["channel"]["command"], ["python", "new-server.py"])
        self.assertEqual(merged["channel"]["environment"]["KEY"], "new")

    def test_merge_three_configs(self):
        """Merge builtin + legacy deploy + user extensions."""
        builtin = {
            "mcp": {
                "channel": {
                    "type": "local",
                    "command": ["python", "channel.py"],
                    "environment": {"KEY": "builtin"},
                },
                "memory": {
                    "type": "local",
                    "command": ["python", "memory.py"],
                    "environment": {"KEY": "builtin"},
                },
            }
        }
        legacy_deploy = {
            "mcpServers": {
                "channel": {
                    "command": "python ${HOME}/channel-v2.py",
                    "env": {"KEY": "${API_KEY}"},
                },
            }
        }
        user_extension = {
            "mcp": {
                "sentry": {
                    "type": "remote",
                    "url": "https://mcp.sentry.dev/mcp",
                    "oauth": {},
                },
            }
        }

        merged = merge_mcp_configs(builtin, legacy_deploy, user_extension)

        # 3 servers total
        self.assertEqual(len(merged), 3)

        # channel overridden by legacy deploy (later wins)
        self.assertEqual(merged["channel"]["command"], ["python", "{env:HOME}/channel-v2.py"])
        self.assertEqual(merged["channel"]["environment"]["KEY"], "{env:API_KEY}")

        # memory kept from builtin (not overridden)
        self.assertEqual(merged["memory"]["command"], ["python", "memory.py"])

        # sentry added from user extension
        self.assertEqual(merged["sentry"]["type"], "remote")
        self.assertEqual(merged["sentry"]["url"], "https://mcp.sentry.dev/mcp")

    def test_merge_validates_cleanly(self):
        """Merged output should pass validation after normalization."""
        legacy = self.FULL_LEGACY_CONFIG
        extension = {
            "mcp": {
                "context7": {
                    "type": "remote",
                    "url": "https://mcp.context7.com/mcp",
                },
            }
        }
        merged = merge_mcp_configs(legacy, extension)
        validated, skipped, _ = validate_mcp_config(merged)

        # All 6 servers should pass (5 from legacy + 1 extension)
        self.assertEqual(len(validated), 6)
        self.assertEqual(len(skipped), 0)

    # The full legacy config from the user's example
    FULL_LEGACY_CONFIG = {
        "mcpServers": {
            "channel": {
                "command": "${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}",
                "args": ["${HOME}/.ostwin/.agents/mcp/channel-server.py"],
                "env": {
                    "AGENT_OS_ROOT": ".",
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
            "warroom": {
                "command": "${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}",
                "args": ["${HOME}/.ostwin/.agents/mcp/warroom-server.py"],
                "env": {
                    "AGENT_OS_ROOT": ".",
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
            "memory": {
                "command": "${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}",
                "args": ["${HOME}/.ostwin/.agents/mcp/memory-server.py"],
                "env": {
                    "AGENT_OS_ROOT": "${AGENT_OS_PROJECT_DIR:-.}",
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
            "stitch": {
                "httpUrl": "https://stitch.googleapis.com/mcp",
                "headers": {"X-Goog-Api-Key": "${MCP_STITCH_API_KEY}"},
                "env": {
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
            "github": {
                "command": "npx -y @modelcontextprotocol/server-github",
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": "${MCP_GITHUB_GITHUB_PERSONAL_ACCESS_TOKEN}",
                    "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
                    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
                    "OSTWIN_API_KEY": "${OSTWIN_API_KEY}",
                },
            },
        }
    }


# ─── validate_mcp_server() ───────────────────────────────────────────────────


class TestValidateLocalServer(unittest.TestCase):
    """Local MCP servers require type, command, and environment."""

    def test_valid_local_server(self):
        cfg = {
            "type": "local",
            "command": ["npx", "-y", "my-mcp-command"],
            "environment": {"API_KEY": "test-key"},
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_valid_local_with_env_placeholders(self):
        """OpenCode {env:*} placeholders in values are valid."""
        cfg = {
            "type": "local",
            "command": ["python", "{env:HOME}/.ostwin/.agents/mcp/server.py"],
            "environment": {
                "GOOGLE_API_KEY": "{env:GOOGLE_API_KEY}",
                "OSTWIN_API_KEY": "{env:OSTWIN_API_KEY}",
            },
        }
        is_valid, errors, warnings = validate_mcp_server("channel", cfg)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_valid_local_with_optional_fields(self):
        cfg = {
            "type": "local",
            "command": ["bun", "x", "my-mcp"],
            "environment": {"KEY": "val"},
            "enabled": True,
            "timeout": 5000,
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(is_valid)
        self.assertEqual(warnings, [])

    def test_missing_command(self):
        cfg = {
            "type": "local",
            "environment": {"API_KEY": "test"},
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("command" in e for e in errors))

    def test_missing_environment(self):
        cfg = {
            "type": "local",
            "command": ["npx", "-y", "my-mcp"],
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("environment" in e for e in errors))

    def test_missing_both_command_and_environment(self):
        cfg = {"type": "local"}
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertEqual(len(errors), 2)

    def test_command_not_array(self):
        cfg = {
            "type": "local",
            "command": "npx -y my-mcp",
            "environment": {"KEY": "val"},
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("non-empty array" in e for e in errors))

    def test_command_empty_array(self):
        cfg = {
            "type": "local",
            "command": [],
            "environment": {"KEY": "val"},
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("non-empty array" in e for e in errors))

    def test_command_contains_non_string(self):
        cfg = {
            "type": "local",
            "command": ["npx", 42],
            "environment": {"KEY": "val"},
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("only strings" in e for e in errors))

    def test_environment_not_dict(self):
        cfg = {
            "type": "local",
            "command": ["npx", "-y", "my-mcp"],
            "environment": "API_KEY=test",
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("must be a dict" in e for e in errors))


class TestValidateRemoteServer(unittest.TestCase):
    """Remote MCP servers require type and url; auth is warned if missing."""

    def test_valid_remote_with_headers(self):
        cfg = {
            "type": "remote",
            "url": "https://mcp.example.com/mcp",
            "headers": {"Authorization": "Bearer {env:MY_API_KEY}"},
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_valid_remote_with_oauth(self):
        cfg = {
            "type": "remote",
            "url": "https://mcp.sentry.dev/mcp",
            "oauth": {},
        }
        is_valid, errors, warnings = validate_mcp_server("sentry", cfg)
        self.assertTrue(is_valid)
        self.assertEqual(warnings, [])

    def test_valid_remote_with_oauth_credentials(self):
        cfg = {
            "type": "remote",
            "url": "https://mcp.example.com/mcp",
            "oauth": {
                "clientId": "{env:MY_CLIENT_ID}",
                "clientSecret": "{env:MY_CLIENT_SECRET}",
                "scope": "tools:read tools:execute",
            },
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(is_valid)
        self.assertEqual(warnings, [])

    def test_remote_without_auth_warns(self):
        cfg = {
            "type": "remote",
            "url": "https://mcp.context7.com/mcp",
        }
        is_valid, errors, warnings = validate_mcp_server("context7", cfg)
        self.assertTrue(is_valid)  # still valid, just warned
        self.assertTrue(any("authentication" in w for w in warnings))

    def test_remote_oauth_false_with_headers(self):
        """oauth: false is valid when using API key headers instead."""
        cfg = {
            "type": "remote",
            "url": "https://mcp.example.com/mcp",
            "oauth": False,
            "headers": {"Authorization": "Bearer {env:MY_API_KEY}"},
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(is_valid)
        self.assertEqual(warnings, [])

    def test_remote_oauth_false_without_headers_warns(self):
        cfg = {
            "type": "remote",
            "url": "https://mcp.example.com/mcp",
            "oauth": False,
        }
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(is_valid)
        self.assertTrue(any("authentication" in w for w in warnings))

    def test_missing_url(self):
        cfg = {"type": "remote"}
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("url" in e for e in errors))

    def test_url_empty_string(self):
        cfg = {"type": "remote", "url": ""}
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("non-empty string" in e for e in errors))

    def test_url_not_string(self):
        cfg = {"type": "remote", "url": 42}
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)


class TestValidateTypeField(unittest.TestCase):
    """The type field must be 'local' or 'remote'."""

    def test_missing_type(self):
        cfg = {"command": ["npx", "my-mcp"]}
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("type" in e for e in errors))

    def test_invalid_type(self):
        cfg = {"type": "stdio", "command": ["npx", "my-mcp"]}
        is_valid, errors, warnings = validate_mcp_server("test", cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("'local' or 'remote'" in e for e in errors))

    def test_not_a_dict(self):
        is_valid, errors, warnings = validate_mcp_server("test", "not a dict")
        self.assertFalse(is_valid)
        self.assertTrue(any("expected dict" in e for e in errors))

    def test_none_value(self):
        is_valid, errors, warnings = validate_mcp_server("test", None)
        self.assertFalse(is_valid)


class TestValidateOptionalFields(unittest.TestCase):
    """Optional fields are type-checked but not required."""

    def _valid_local(self, **extra):
        cfg = {
            "type": "local",
            "command": ["npx", "my-mcp"],
            "environment": {"KEY": "val"},
        }
        cfg.update(extra)
        return cfg

    def test_timeout_valid(self):
        cfg = self._valid_local(timeout=5000)
        _, _, warnings = validate_mcp_server("test", cfg)
        self.assertEqual(warnings, [])

    def test_timeout_zero(self):
        cfg = self._valid_local(timeout=0)
        _, _, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(any("timeout" in w for w in warnings))

    def test_timeout_negative(self):
        cfg = self._valid_local(timeout=-1)
        _, _, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(any("timeout" in w for w in warnings))

    def test_timeout_string(self):
        cfg = self._valid_local(timeout="5000")
        _, _, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(any("timeout" in w for w in warnings))

    def test_enabled_not_bool(self):
        cfg = self._valid_local(enabled="true")
        _, _, warnings = validate_mcp_server("test", cfg)
        self.assertTrue(any("enabled" in w for w in warnings))


# ─── validate_mcp_config() ──────────────────────────────────────────────────


class TestValidateMcpConfig(unittest.TestCase):
    """Batch validation of a full MCP config block."""

    def test_all_valid(self):
        mcp = {
            "channel": {
                "type": "local",
                "command": ["python", "channel-server.py"],
                "environment": {"KEY": "val"},
            },
            "github": {
                "type": "local",
                "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
                "environment": {"TOKEN": "{env:GITHUB_TOKEN}"},
            },
        }
        validated, skipped, results = validate_mcp_config(mcp)
        self.assertEqual(len(validated), 2)
        self.assertEqual(len(skipped), 0)
        # enabled: true should be added
        self.assertTrue(validated["channel"]["enabled"])
        self.assertTrue(validated["github"]["enabled"])

    def test_mixed_valid_and_invalid(self):
        mcp = {
            "good": {
                "type": "local",
                "command": ["npx", "good-mcp"],
                "environment": {"KEY": "val"},
            },
            "bad-no-cmd": {
                "type": "local",
                "environment": {"KEY": "val"},
            },
            "bad-no-type": {
                "command": ["npx", "bad-mcp"],
            },
        }
        validated, skipped, results = validate_mcp_config(mcp)
        self.assertEqual(len(validated), 1)
        self.assertIn("good", validated)
        self.assertEqual(len(skipped), 2)
        self.assertIn("bad-no-cmd", skipped)
        self.assertIn("bad-no-type", skipped)

    def test_empty_config(self):
        validated, skipped, results = validate_mcp_config({})
        self.assertEqual(len(validated), 0)
        self.assertEqual(len(skipped), 0)
        self.assertEqual(len(results), 0)

    def test_validates_real_mcp_config(self):
        """Validate the actual config.json from the repo."""
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config.json"
        )
        if not os.path.exists(config_path):
            self.skipTest("config.json not found")

        with open(config_path) as f:
            source = json.load(f)
        mcp = source.get("mcp", {})

        validated, skipped, results = validate_mcp_config(mcp)

        # All 5 servers should pass validation
        self.assertEqual(len(skipped), 0, f"Unexpected failures: {skipped}")
        self.assertEqual(len(validated), len(mcp))

        # Each should have enabled: true
        for name, cfg in validated.items():
            self.assertTrue(cfg.get("enabled"), f"{name} missing enabled: true")


# ─── Integration: opencode.json output format ────────────────────────────────


class TestOpencodeJsonFormat(unittest.TestCase):
    """Test the full pipeline: validate → build tools deny → write opencode.json."""

    def test_opencode_json_output(self):
        """Simulates what install.sh does: validate, add tools deny, write."""
        mcp_source = {
            "mcp": {
                "channel": {
                    "type": "local",
                    "command": ["python", "{env:HOME}/.ostwin/.agents/mcp/channel-server.py"],
                    "environment": {
                        "AGENT_OS_ROOT": ".",
                        "GOOGLE_API_KEY": "{env:GOOGLE_API_KEY}",
                    },
                },
                "stitch": {
                    "type": "remote",
                    "url": "https://stitch.googleapis.com/mcp",
                    "headers": {"X-Goog-Api-Key": "{env:MCP_STITCH_API_KEY}"},
                },
            }
        }

        validated, skipped, _ = validate_mcp_config(mcp_source["mcp"])

        # Build tools deny block
        tools_deny = {f"{name}*": False for name in validated}

        # Build opencode.json
        opencode = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": validated,
            "tools": tools_deny,
        }

        # --- Assertions ---

        # Schema
        self.assertEqual(opencode["$schema"], "https://opencode.ai/config.json")

        # MCP servers preserved with correct format
        self.assertIn("channel", opencode["mcp"])
        self.assertIn("stitch", opencode["mcp"])
        ch = opencode["mcp"]["channel"]
        self.assertEqual(ch["type"], "local")
        self.assertEqual(ch["command"][0], "python")
        self.assertIn("{env:HOME}", ch["command"][1])
        self.assertEqual(ch["environment"]["GOOGLE_API_KEY"], "{env:GOOGLE_API_KEY}")
        self.assertTrue(ch["enabled"])

        st = opencode["mcp"]["stitch"]
        self.assertEqual(st["type"], "remote")
        self.assertEqual(st["url"], "https://stitch.googleapis.com/mcp")
        self.assertTrue(st["enabled"])

        # Tools deny block
        self.assertIn("channel*", opencode["tools"])
        self.assertIn("stitch*", opencode["tools"])
        self.assertFalse(opencode["tools"]["channel*"])
        self.assertFalse(opencode["tools"]["stitch*"])

    def test_opencode_json_merge_preserves_user_settings(self):
        """Existing user settings (theme, keybinds) are not clobbered."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "$schema": "https://opencode.ai/config.json",
                    "theme": "dracula",
                    "keybinds": {"ctrl+p": "palette"},
                    "mcp": {"old-server": {"type": "local", "command": ["old"]}},
                    "tools": {"old-server*": False},
                },
                f,
            )
            existing_path = f.name

        try:
            # Load existing
            with open(existing_path) as f:
                existing = json.load(f)

            # New MCP config
            new_mcp = {
                "new-server": {
                    "type": "local",
                    "command": ["npx", "new-mcp"],
                    "environment": {"KEY": "val"},
                }
            }
            validated, _, _ = validate_mcp_config(new_mcp)
            tools_deny = {f"{name}*": False for name in validated}

            # Merge (same logic as install.sh)
            existing["$schema"] = "https://opencode.ai/config.json"
            existing["mcp"] = validated
            existing["tools"] = tools_deny

            # User settings preserved
            self.assertEqual(existing["theme"], "dracula")
            self.assertEqual(existing["keybinds"]["ctrl+p"], "palette")

            # Old MCP replaced
            self.assertNotIn("old-server", existing["mcp"])
            self.assertIn("new-server", existing["mcp"])
            self.assertNotIn("old-server*", existing["tools"])
            self.assertIn("new-server*", existing["tools"])
        finally:
            os.unlink(existing_path)

    def test_invalid_servers_excluded_from_output(self):
        """Invalid servers should not appear in mcp or tools blocks."""
        mcp = {
            "good": {
                "type": "local",
                "command": ["npx", "good"],
                "environment": {"KEY": "val"},
            },
            "bad": {
                "type": "local",
                # missing command and environment
            },
        }
        validated, skipped, _ = validate_mcp_config(mcp)
        tools_deny = {f"{name}*": False for name in validated}

        self.assertIn("good", validated)
        self.assertNotIn("bad", validated)
        self.assertIn("good*", tools_deny)
        self.assertNotIn("bad*", tools_deny)


# ─── CLI entrypoint ──────────────────────────────────────────────────────────


class TestValidateMcpCli(unittest.TestCase):
    """Test the CLI interface of validate_mcp.py."""

    def test_cli_config_file(self):
        """CLI validates a config file and exits 0 on success."""
        import subprocess

        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config.json"
        )
        if not os.path.exists(config_path):
            self.skipTest("config.json not found")

        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "validate_mcp.py"), config_path],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("passed", result.stdout)

    def test_cli_inline_valid(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "validate_mcp.py"),
                "--server",
                '{"type":"local","command":["npx","my-mcp"],"environment":{"K":"v"}}',
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("OK", result.stdout)

    def test_cli_inline_invalid(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "validate_mcp.py"),
                "--server",
                '{"type":"local"}',
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR", result.stdout)

    def test_cli_output_file(self):
        """--output writes only valid servers to a file."""
        import subprocess

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as src:
            json.dump({
                "mcp": {
                    "good": {
                        "type": "local",
                        "command": ["npx", "good"],
                        "environment": {"K": "v"},
                    },
                    "bad": {"type": "local"},
                }
            }, src)
            src_path = src.name

        out_path = src_path + ".out"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    os.path.join(os.path.dirname(__file__), "validate_mcp.py"),
                    src_path,
                    "--output", out_path,
                ],
                capture_output=True, text=True,
            )
            # Exit 1 because of the bad server
            self.assertEqual(result.returncode, 1)

            with open(out_path) as f:
                output = json.load(f)
            self.assertIn("good", output["mcp"])
            self.assertNotIn("bad", output["mcp"])
            self.assertTrue(output["mcp"]["good"]["enabled"])
        finally:
            os.unlink(src_path)
            if os.path.exists(out_path):
                os.unlink(out_path)


if __name__ == "__main__":
    unittest.main()
