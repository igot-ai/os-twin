---
name: animator-modify
description: Modify Unity's AnimatorController asset. Apply an array of modifications including adding/removing parameters, layers, states, and transitions. Use 'animator-get-data' tool to get valid names and parameters for modifications.
---

# Animator / Modify

Modify Unity's AnimatorController asset. Apply an array of modifications including adding/removing parameters, layers, states, and transitions. Use 'animator-get-data' tool to get valid names and parameters for modifications.

## How to Call

### HTTP API (Direct Tool Execution)

Execute this tool directly via the MCP Plugin HTTP API:

```bash
curl -X POST http://localhost:51657/api/tools/animator-modify \
  -H "Content-Type: application/json" \
  -d '{
  "animatorRef": "string_value",
  "modifications": "string_value"
}'
```

#### With Authorization (if required)

```bash
curl -X POST http://localhost:51657/api/tools/animator-modify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
  "animatorRef": "string_value",
  "modifications": "string_value"
}'
```

> The token is stored in the file: `UserSettings/AI-Game-Developer-Config.json`
> Using the format: `"token": "YOUR_TOKEN"`

## Input

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `animatorRef` | `any` | Yes | Reference to the AnimatorController asset to modify. |
| `modifications` | `any` | Yes | Array of modifications to apply to the controller. |

### Input JSON Schema

```json
{
  "type": "object",
  "properties": {
    "animatorRef": {
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.AssetObjectRef",
      "description": "Reference to the AnimatorController asset to modify."
    },
    "modifications": {
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorModification[]",
      "description": "Array of modifications to apply to the controller."
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
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorModification": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "AddParameter",
            "RemoveParameter",
            "AddLayer",
            "RemoveLayer",
            "AddState",
            "RemoveState",
            "SetDefaultState",
            "AddTransition",
            "RemoveTransition",
            "AddAnyStateTransition",
            "SetStateMotion",
            "SetStateSpeed"
          ],
          "description": "Modification type. Properties below are used conditionally based on this value."
        },
        "parameterName": {
          "type": "string",
          "description": "Parameter name. Required for: AddParameter, RemoveParameter."
        },
        "parameterType": {
          "type": "string",
          "description": "Parameter type: Float, Int, Bool, Trigger. Required for: AddParameter."
        },
        "defaultFloat": {
          "type": "number",
          "description": "Default float value. Optional for: AddParameter (Float type)."
        },
        "defaultInt": {
          "type": "integer",
          "description": "Default int value. Optional for: AddParameter (Int type)."
        },
        "defaultBool": {
          "type": "boolean",
          "description": "Default bool value. Optional for: AddParameter (Bool type)."
        },
        "layerName": {
          "type": "string",
          "description": "Layer name. Required for: AddLayer, RemoveLayer, AddState, RemoveState, SetDefaultState, AddTransition, RemoveTransition, AddAnyStateTransition, SetStateMotion, SetStateSpeed."
        },
        "stateName": {
          "type": "string",
          "description": "State name. Required for: AddState, RemoveState, SetDefaultState, SetStateMotion, SetStateSpeed."
        },
        "motionAssetPath": {
          "type": "string",
          "description": "Asset path to AnimationClip. Optional for: AddState. Required for: SetStateMotion."
        },
        "speed": {
          "type": "number",
          "description": "Speed multiplier. Required for: SetStateSpeed."
        },
        "sourceStateName": {
          "type": "string",
          "description": "Source state name. Required for: AddTransition, RemoveTransition."
        },
        "destinationStateName": {
          "type": "string",
          "description": "Destination state name. Required for: AddTransition, RemoveTransition, AddAnyStateTransition."
        },
        "hasExitTime": {
          "type": "boolean",
          "description": "Whether transition waits for exit time. Optional for: AddTransition, AddAnyStateTransition."
        },
        "exitTime": {
          "type": "number",
          "description": "Normalized exit time (0-1). Optional for: AddTransition, AddAnyStateTransition."
        },
        "duration": {
          "type": "number",
          "description": "Transition blend duration. Optional for: AddTransition, AddAnyStateTransition."
        },
        "hasFixedDuration": {
          "type": "boolean",
          "description": "Whether duration is in seconds (true) or normalized (false). Optional for: AddTransition, AddAnyStateTransition."
        },
        "conditions": {
          "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorConditionData[]",
          "description": "Transition conditions. Optional for: AddTransition, AddAnyStateTransition."
        }
      },
      "required": [
        "type"
      ]
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorConditionData[]": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorConditionData"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorConditionData": {
      "type": "object",
      "properties": {
        "parameter": {
          "type": "string",
          "description": "Parameter name for the condition."
        },
        "mode": {
          "type": "string",
          "description": "Condition mode: If, IfNot, Greater, Less, Equals, NotEqual."
        },
        "threshold": {
          "type": "number",
          "description": "Threshold value for the condition."
        }
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorModification[]": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorModification"
      }
    }
  },
  "required": [
    "animatorRef",
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
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorTools\u002BModifyAnimatorResponse"
    }
  },
  "$defs": {
    "com.IvanMurzak.Unity.MCP.Animation.ModifyAnimatorInfo": {
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
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorTools\u002BModifyAnimatorResponse": {
      "type": "object",
      "properties": {
        "modifiedAsset": {
          "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.ModifyAnimatorInfo"
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

