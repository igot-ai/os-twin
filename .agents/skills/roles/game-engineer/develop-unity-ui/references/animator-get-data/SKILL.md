---
name: animator-get-data
description: Get data about a Unity AnimatorController asset file. Returns information such as name, layers, parameters, and states.
---

# Animator / Get Data

Get data about a Unity AnimatorController asset file. Returns information such as name, layers, parameters, and states.

## How to Call

### HTTP API (Direct Tool Execution)

Execute this tool directly via the MCP Plugin HTTP API:

```bash
curl -X POST http://localhost:51657/api/tools/animator-get-data \
  -H "Content-Type: application/json" \
  -d '{
  "animatorRef": "string_value"
}'
```

#### With Authorization (if required)

```bash
curl -X POST http://localhost:51657/api/tools/animator-get-data \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
  "animatorRef": "string_value"
}'
```

> The token is stored in the file: `UserSettings/AI-Game-Developer-Config.json`
> Using the format: `"token": "YOUR_TOKEN"`

## Input

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `animatorRef` | `any` | Yes | Reference to the AnimatorController asset. The path should start with 'Assets/' and end with '.controller'. |

### Input JSON Schema

```json
{
  "type": "object",
  "properties": {
    "animatorRef": {
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.AssetObjectRef",
      "description": "Reference to the AnimatorController asset. The path should start with \u0027Assets/\u0027 and end with \u0027.controller\u0027."
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
    "animatorRef"
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
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorTools\u002BGetAnimatorDataResponse"
    }
  },
  "$defs": {
    "System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorParameterInfo\u003E": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorParameterInfo"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorParameterInfo": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "type": {
          "type": "string"
        },
        "defaultFloat": {
          "type": "number"
        },
        "defaultInt": {
          "type": "integer"
        },
        "defaultBool": {
          "type": "boolean"
        }
      },
      "required": [
        "defaultFloat",
        "defaultInt",
        "defaultBool"
      ]
    },
    "System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorLayerInfo\u003E": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorLayerInfo"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorLayerInfo": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "defaultWeight": {
          "type": "number"
        },
        "blendingMode": {
          "type": "string"
        },
        "syncedLayerIndex": {
          "type": "integer"
        },
        "iKPass": {
          "type": "boolean"
        },
        "defaultStateName": {
          "type": "string"
        },
        "states": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorStateInfo\u003E"
        },
        "subStateMachines": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003CSystem.String\u003E"
        },
        "anyStateTransitions": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorTransitionInfo\u003E"
        }
      },
      "required": [
        "defaultWeight",
        "syncedLayerIndex",
        "iKPass"
      ]
    },
    "System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorStateInfo\u003E": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorStateInfo"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorStateInfo": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "tag": {
          "type": "string"
        },
        "speed": {
          "type": "number"
        },
        "speedParameterActive": {
          "type": "boolean"
        },
        "speedParameter": {
          "type": "string"
        },
        "cycleOffset": {
          "type": "number"
        },
        "cycleOffsetParameterActive": {
          "type": "boolean"
        },
        "cycleOffsetParameter": {
          "type": "string"
        },
        "mirror": {
          "type": "boolean"
        },
        "mirrorParameterActive": {
          "type": "boolean"
        },
        "mirrorParameter": {
          "type": "string"
        },
        "writeDefaultValues": {
          "type": "boolean"
        },
        "motionName": {
          "type": "string"
        },
        "transitions": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorTransitionInfo\u003E"
        }
      },
      "required": [
        "speed",
        "speedParameterActive",
        "cycleOffset",
        "cycleOffsetParameterActive",
        "mirror",
        "mirrorParameterActive",
        "writeDefaultValues"
      ]
    },
    "System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorTransitionInfo\u003E": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorTransitionInfo"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorTransitionInfo": {
      "type": "object",
      "properties": {
        "destinationStateName": {
          "type": "string"
        },
        "hasExitTime": {
          "type": "boolean"
        },
        "exitTime": {
          "type": "number"
        },
        "hasFixedDuration": {
          "type": "boolean"
        },
        "duration": {
          "type": "number"
        },
        "offset": {
          "type": "number"
        },
        "canTransitionToSelf": {
          "type": "boolean"
        },
        "conditions": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorConditionInfo\u003E"
        }
      },
      "required": [
        "hasExitTime",
        "exitTime",
        "hasFixedDuration",
        "duration",
        "offset",
        "canTransitionToSelf"
      ]
    },
    "System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorConditionInfo\u003E": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Animation.AnimatorConditionInfo"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorConditionInfo": {
      "type": "object",
      "properties": {
        "parameter": {
          "type": "string"
        },
        "mode": {
          "type": "string"
        },
        "threshold": {
          "type": "number"
        }
      },
      "required": [
        "threshold"
      ]
    },
    "System.Collections.Generic.List\u003CSystem.String\u003E": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "com.IvanMurzak.Unity.MCP.Animation.AnimatorTools\u002BGetAnimatorDataResponse": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "parameters": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorParameterInfo\u003E"
        },
        "layers": {
          "$ref": "#/$defs/System.Collections.Generic.List\u003Ccom.IvanMurzak.Unity.MCP.Animation.AnimatorLayerInfo\u003E"
        }
      }
    }
  },
  "required": [
    "result"
  ]
}
```

