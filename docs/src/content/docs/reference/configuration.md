---
title: Configuration
description: Complete schema reference for the .agents/config.json configuration file.
sidebar:
  order: 2
---

The `.agents/config.json` file is the central configuration for an OSTwin project. It controls role behavior, model selection, concurrency, memory, channels, and release policy.

## Top-Level Fields

```json
{
  "version": "0.1.0",
  "project_name": "my-project"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `version` | `string` | Config schema version |
| `project_name` | `string` | Human-readable project identifier |

## Role Overrides

Each role can be configured at the top level using its name as the key. Common fields:

```json
{
  "engineer": {
    "cli": "agent",
    "default_model": "google-vertex-anthropic/claude-opus-4-6@default",
    "shell_allow_list": "all",
    "auto_approve": true,
    "timeout_seconds": 1200,
    "max_prompt_bytes": 102400,
    "no_mcp": false,
    "skill_refs": ["web-research"]
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cli` | `string` | `"agent"` | CLI tool to spawn for this role |
| `default_model` | `string` | — | Model identifier (see Model Resolution) |
| `shell_allow_list` | `string\|array` | `"all"` | Allowed shell commands, or `"all"` |
| `auto_approve` | `bool` | `false` | Auto-approve tool calls |
| `approval_mode` | `string` | — | Alternative to `auto_approve`: `"auto-approve"` |
| `timeout_seconds` | `int` | `1200` | Max seconds per agent invocation |
| `max_prompt_bytes` | `int` | `102400` | Max prompt size before truncation |
| `no_mcp` | `bool` | `false` | Disable MCP tools for this role |
| `skill_refs` | `array` | `[]` | Skills to inject into role prompt |

## Manager Configuration

The `manager` key has additional orchestration fields:

```json
{
  "manager": {
    "default_model": "google-vertex-anthropic/claude-opus-4-6@default",
    "poll_interval_seconds": 5,
    "max_concurrent_rooms": 50,
    "max_engineer_retries": 10,
    "auto_approve_tools": true,
    "state_timeout_seconds": 2400,
    "auto_expand_plan": false,
    "preflight_skill_check": "warn",
    "smart_assignment": false,
    "dynamic_pipelines": true,
    "capability_matching": true,
    "external_roles_dirs": [],
    "skill_refs": ["risk-decision", "war-room-communication"]
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `poll_interval_seconds` | `int` | `5` | How often the manager polls room states |
| `max_concurrent_rooms` | `int` | `50` | Maximum parallel war-rooms |
| `max_engineer_retries` | `int` | `10` | Retry cap before `failed-final` |
| `auto_expand_plan` | `bool` | `false` | Auto-generate sub-tasks from epics |
| `preflight_skill_check` | `string` | `"warn"` | `"warn"`, `"error"`, or `"skip"` |
| `smart_assignment` | `bool` | `false` | Use capability matching for assignment |
| `dynamic_pipelines` | `bool` | `true` | Allow dynamic lifecycle creation |
| `capability_matching` | `bool` | `true` | Match roles by capabilities |
| `external_roles_dirs` | `array` | `[]` | Additional directories to search for roles |

## Instances

Roles that support `instance_support: true` in the registry can define named instances:

```json
{
  "engineer": {
    "instances": {
      "fe": {
        "display_name": "Frontend Engineer",
        "default_model": "google-vertex-anthropic/claude-opus-4-6@default",
        "timeout_seconds": 2400,
        "working_dir": "dashboard",
        "skills": ["javascript", "typescript", "css"]
      },
      "be": {
        "display_name": "Backend Engineer",
        "default_model": "google-vertex-anthropic/claude-opus-4-6@default",
        "working_dir": "api",
        "skills": ["python", "sql", "docker"]
      }
    }
  }
}
```

Each instance inherits from the parent role config and can override any field.

## Model Resolution

Model identifiers follow this format:

```
provider/model-name@variant
```

Resolution order:
1. Room `config.json` override
2. Role-specific `default_model` in `.agents/config.json`
3. Role definition `model` field in `role.json`
4. Registry `default_model`

Examples:
- `google-vertex-anthropic/claude-opus-4-6@default`
- `google-vertex/gemini-3.1-pro-preview`
- `openai:seed-2-0-pro-260328`

## Memory Configuration

```json
{
  "memory": {
    "enabled": true,
    "max_summary_bytes": 4096,
    "max_detail_bytes": 16384,
    "max_context_entries": 15,
    "auto_publish_on_done": true
  }
}
```

## Channel Configuration

```json
{
  "channel": {
    "format": "jsonl",
    "max_message_size_bytes": 65536
  }
}
```

## Release Configuration

```json
{
  "release": {
    "require_signoffs": ["engineer", "qa", "manager"],
    "auto_draft": true
  }
}
```

## Runtime Configuration

```json
{
  "runtime": {
    "max_concurrent_rooms": 9999
  }
}
```

:::caution
The `runtime.max_concurrent_rooms` overrides `manager.max_concurrent_rooms`. Use one or the other to avoid confusion.
:::

## Autonomy Configuration

```json
{
  "autonomy": {
    "idle_explore_enabled": true,
    "interval": 3600
  }
}
```

Enables autonomous exploration when no plan is running.
