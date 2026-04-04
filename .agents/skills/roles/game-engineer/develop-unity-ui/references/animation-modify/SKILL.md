---
name: animation-modify
description: Modify Unity's AnimationClip asset. Apply an array of modifications including setting curves, clearing curves, setting properties, and managing animation events. Use 'animation-get-data' tool to get valid property names and existing curves for modifications.
---

# Animation / Modify

Modify Unity's AnimationClip asset. Apply an array of modifications including setting curves, clearing curves, setting properties, and managing animation events. Use 'animation-get-data' tool to get valid property names and existing curves for modifications.

## How to Call

### HTTP API (Direct Tool Execution)

Execute this tool directly via the MCP Plugin HTTP API:

```bash
curl -X POST http://localhost:51657/api/tools/animation-modify \
  -H "Content-Type: application/json" \
  -d '{
  "animRef": "string_value",
  "modifications": "string_value"
}'
```

#### With Authorization (if required)

```bash
curl -X POST http://localhost:51657/api/tools/animation-modify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
  "animRef": "string_value",
  "modifications": "string_value"
}'
```

> The token is stored in the file: `UserSettings/AI-Game-Developer-Config.json`
> Using the format: `"token": "YOUR_TOKEN"`

## Input

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `animRef` | `any` | Yes | Reference to the AnimationClip asset to modify. |
| `modifications` | `any` | Yes | Array of modifications to apply to the clip. |

### Input JSON Schema

```json
{
  "type": "object",
  "properties": {
    "animRef": {
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.AssetObjectRef",
      "description": "Reference to the AnimationClip asset to modify."
    },
    "modifications": {
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationModification[]",
      "description": "Array of modifications to apply to the clip."
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
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimationModification": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "SetCurve",
            "RemoveCurve",
            "ClearCurves",
            "SetFrameRate",
            "SetWrapMode",
            "SetLegacy",
            "AddEvent",
            "ClearEvents"
          ],
          "description": "Modification type. Properties below are used conditionally based on this value."
        },
        "relativePath": {
          "type": "string",
          "description": "Path to target GameObject relative to the root (empty for root). Used by: SetCurve, RemoveCurve."
        },
        "componentType": {
          "type": "string",
          "description": "Component type name (e.g., \u0027Transform\u0027, \u0027SpriteRenderer\u0027). Required for: SetCurve, RemoveCurve."
        },
        "propertyName": {
          "type": "string",
          "description": "Property to animate (e.g., \u0027localPosition.x\u0027, \u0027m_LocalScale.y\u0027). Required for: SetCurve, RemoveCurve."
        },
        "keyframes": {
          "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationKeyframe[]",
          "description": "Keyframes for the curve. Required for: SetCurve."
        },
        "frameRate": {
          "type": "number",
          "description": "Frames per second. Required for: SetFrameRate."
        },
        "wrapMode": {
          "type": "string",
          "enum": [
            "Default",
            "Clamp",
            "Clamp",
            "Loop",
            "PingPong",
            "ClampForever"
          ],
          "description": "How animation behaves at boundaries. Required for: SetWrapMode."
        },
        "legacy": {
          "type": "boolean",
          "description": "Use legacy animation system. Required for: SetLegacy."
        },
        "time": {
          "type": "number",
          "description": "Event trigger time in seconds. Required for: AddEvent."
        },
        "functionName": {
          "type": "string",
          "description": "Function to invoke. Required for: AddEvent."
        },
        "stringParameter": {
          "type": "string",
          "description": "String parameter passed to the function. Optional for: AddEvent."
        },
        "floatParameter": {
          "type": "number",
          "description": "Float parameter passed to the function. Optional for: AddEvent."
        },
        "intParameter": {
          "type": "integer",
          "description": "Integer parameter passed to the function. Optional for: AddEvent."
        }
      },
      "required": [
        "type"
      ]
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimationKeyframe[]": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationKeyframe"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimationKeyframe": {
      "type": "object",
      "properties": {
        "time": {
          "type": "number",
          "description": "Time in seconds."
        },
        "value": {
          "type": "number",
          "description": "Value at this keyframe."
        },
        "inTangent": {
          "type": "number",
          "description": "Incoming tangent (slope). Default: 0."
        },
        "outTangent": {
          "type": "number",
          "description": "Outgoing tangent (slope). Default: 0."
        },
        "weightedMode": {
          "type": "string",
          "enum": [
            "None",
            "In",
            "Out",
            "Both"
          ],
          "description": "Weighted mode: None (0), In (1), Out (2), Both (3). Default: None."
        },
        "inWeight": {
          "type": "number",
          "description": "Incoming weight. Default: 0.33."
        },
        "outWeight": {
          "type": "number",
          "description": "Outgoing weight. Default: 0.33."
        }
      },
      "required": [
        "time",
        "value"
      ]
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimationModification[]": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationModification"
      }
    }
  },
  "required": [
    "animRef",
    "modifications"
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
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BModifyAnimationResponse"
    }
  },
  "$defs": {
    "com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BModifyAnimationInfo": {
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
    "com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BModifyAnimationResponse": {
      "type": "object",
      "properties": {
        "modifiedAsset": {
          "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimationTools\u002BModifyAnimationInfo"
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

