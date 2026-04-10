---
name: Get Animation Data
description: Get details about a Unity AnimationClip, such as name, length, and events.
version: 1.0.0
category: Unity Logic
applicable_roles: [game-engineer, engineer]
tags: [engineer, implementation, unity, animation, discovery]
author: Agent OS Core
---

# Animation / Get Data

Get data about a Unity AnimationClip asset file. Returns information such as name, length, frame rate, wrap mode, animation curves, and events.

## How to Call

### HTTP API (Direct Tool Execution)

Execute this tool directly via the MCP Plugin HTTP API:

```bash
curl -X POST http://localhost:51657/api/tools/animation-get-data \
  -H "Content-Type: application/json" \
  -d '{
  "animRef": "string_value"
}'
```

#### With Authorization (if required)

```bash
curl -X POST http://localhost:51657/api/tools/animation-get-data \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
  "animRef": "string_value"
}'
```

> The token is stored in the file: `UserSettings/AI-Game-Developer-Config.json`
> Using the format: `"token": "YOUR_TOKEN"`

## Input

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `animRef` | `any` | Yes | Reference to the animation asset. The path should start with 'Assets/' and end with '.anim'. |

### Input JSON Schema

```json
{
  "type": "object",
  "properties": {
    "animRef": {
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.AssetObjectRef",
      "description": "Reference to the animation asset. The path should start with \u0027Assets/\u0027 and end with \u0027.anim\u0027."
    }
  },
  "$defs": {
    "System.Type": {
      "type": "string"
    },
    "com.IvanMurzak.Unity.MCP.Runtime.Data.AssetObjectRef": {
      "type": "object",
      "properties": {
        "instanceID": {
          "type": "integer",
          "description": "instanceID of the UnityEngine.Object. If this is \u00270\u0027 and \u0027assetPath\u0027 and \u0027assetGuid\u0027 is not provided, empty or null, then it will be used as \u0027null\u0027."
        },
        "assetType": {
          "$ref": "#/$defs/System.Type",
          "description": "Type of the asset."
        },
        "assetPath": {
          "type": "string",
          "description": "Path to the asset within the project. Starts with \u0027Assets/\u0027"
        },
        "assetGuid": {
          "type": "string",
          "description": "Unique identifier for the asset."
        }
      },
      "required": [
        "instanceID"
      ],
      "description": "Reference to UnityEngine.Object asset instance. It could be Material, ScriptableObject, Prefab, and any other Asset. Anything located in the Assets and Packages folders."
    }
  },
  "required": [
    "animRef"
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
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BGetDataResponse"
    }
  },
  "$defs": {
    "System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCurveBindingInfo\u003E": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCurveBindingInfo"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCurveBindingInfo": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string"
        },
        "propertyName": {
          "type": "string"
        },
        "type": {
          "type": "string"
        },
        "isPPtrCurve": {
          "type": "boolean"
        },
        "isDiscreteCurve": {
          "type": "boolean"
        },
        "keyframeCount": {
          "type": "integer"
        }
      },
      "required": [
        "isPPtrCurve",
        "isDiscreteCurve",
        "keyframeCount"
      ]
    },
    "System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BAnimationEventInfo\u003E": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BAnimationEventInfo"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BAnimationEventInfo": {
      "type": "object",
      "properties": {
        "time": {
          "type": "number"
        },
        "functionName": {
          "type": "string"
        },
        "intParameter": {
          "type": "integer"
        },
        "floatParameter": {
          "type": "number"
        },
        "stringParameter": {
          "type": "string"
        }
      },
      "required": [
        "time",
        "intParameter",
        "floatParameter"
      ]
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BGetDataResponse": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "length": {
          "type": "number"
        },
        "frameRate": {
          "type": "number"
        },
        "wrapMode": {
          "type": "string"
        },
        "isLooping": {
          "type": "boolean"
        },
        "hasGenericRootTransform": {
          "type": "boolean"
        },
        "hasMotionCurves": {
          "type": "boolean"
        },
        "hasMotionFloatCurves": {
          "type": "boolean"
        },
        "hasRootCurves": {
          "type": "boolean"
        },
        "humanMotion": {
          "type": "boolean"
        },
        "legacy": {
          "type": "boolean"
        },
        "localBounds": {
          "type": "string"
        },
        "empty": {
          "type": "boolean"
        },
        "curveBindings": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCurveBindingInfo\u003E"
        },
        "objectReferenceBindings": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BCurveBindingInfo\u003E"
        },
        "events": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BAnimationEventInfo\u003E"
        }
      },
      "required": [
        "length",
        "frameRate",
        "isLooping",
        "hasGenericRootTransform",
        "hasMotionCurves",
        "hasMotionFloatCurves",
        "hasRootCurves",
        "humanMotion",
        "legacy",
        "empty"
      ]
    }
  },
  "required": [
    "result"
  ]
}
```

