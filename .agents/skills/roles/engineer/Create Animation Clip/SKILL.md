---
name: Create Animation Clip
description: Create Unity's Animation asset files (AnimationClip). Creates folders recursively if they do not exist.
version: 1.0.0
category: Unity Logic
applicable_roles: [game-engineer, engineer]
tags: [engineer, implementation, unity, animation]
author: Agent OS Core
---

# Animation / Create

Create Unity's Animation asset files (AnimationClip). Creates folders recursively if they do not exist. Each path should start with 'Assets/' and end with '.anim'.

## How to Call

### HTTP API (Direct Tool Execution)

Execute this tool directly via the MCP Plugin HTTP API:

```bash
curl -X POST http://localhost:51657/api/tools/animation-create \
  -H "Content-Type: application/json" \
  -d '{
  "sourcePaths": "string_value"
}'
```

#### With Authorization (if required)

```bash
curl -X POST http://localhost:51657/api/tools/animation-create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
  "sourcePaths": "string_value"
}'
```

> The token is stored in the file: `UserSettings/AI-Game-Developer-Config.json`
> Using the format: `"token": "YOUR_TOKEN"`

## Input

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `sourcePaths` | `any` | Yes | The paths of the animation assets to create. Each path should start with 'Assets/' and end with '.anim'. |

### Input JSON Schema

```json
{
  "type": "object",
  "properties": {
    "sourcePaths": {
      "$ref": "#/$defs/System.String[]",
      "description": "The paths of the animation assets to create. Each path should start with \u0027Assets/\u0027 and end with \u0027.anim\u0027."
    }
  },
  "$defs": {
    "System.String[]": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "sourcePaths"
  ]
}
```

## Output

### Output JSON Schema

```json
{
  "type": "object",
  "properties": {
    "result": {
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCreateAnimationResponse"
    }
  },
  "$defs": {
    "System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCreatedAnimationInfo\u003E": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCreatedAnimationInfo"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCreatedAnimationInfo": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string"
        },
        "instanceId": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        }
      },
      "required": [
        "instanceId"
      ]
    },
    "System.Collections.Generic.List\u003CSystem.String\u003E": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCreateAnimationResponse": {
      "type": "object",
      "properties": {
        "createdAssets": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCreatedAnimationInfo\u003E"
        },
        "errors": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003CSystem.String\u003E"
        }
      }
    }
  },
  "required": [
    "result"
  ]
}
```

