---
name: particle-system-modify
description: Modify a ParticleSystem component on a GameObject. Provide the data model with only the modules you want to change. Use 'particle-system-get' first to inspect the ParticleSystem structure before modifying. Only include the modules and properties you want to change.
---

# ParticleSystem / Modify

Modify a ParticleSystem component on a GameObject. Provide the data model with only the modules you want to change. Use 'particle-system-get' first to inspect the ParticleSystem structure before modifying. Only include the modules and properties you want to change.

## How to Call

### HTTP API (Direct Tool Execution)

Execute this tool directly via the MCP Plugin HTTP API:

```bash
curl -X POST http://localhost:51657/api/tools/particle-system-modify \
  -H "Content-Type: application/json" \
  -d '{
  "gameObjectRef": "string_value",
  "componentRef": "string_value",
  "main": "string_value",
  "emission": "string_value",
  "shape": "string_value",
  "velocityOverLifetime": "string_value",
  "limitVelocityOverLifetime": "string_value",
  "inheritVelocity": "string_value",
  "lifetimeByEmitterSpeed": "string_value",
  "forceOverLifetime": "string_value",
  "colorOverLifetime": "string_value",
  "colorBySpeed": "string_value",
  "sizeOverLifetime": "string_value",
  "sizeBySpeed": "string_value",
  "rotationOverLifetime": "string_value",
  "rotationBySpeed": "string_value",
  "externalForces": "string_value",
  "noise": "string_value",
  "collision": "string_value",
  "trigger": "string_value",
  "subEmitters": "string_value",
  "textureSheetAnimation": "string_value",
  "lights": "string_value",
  "trails": "string_value",
  "customData": "string_value",
  "renderer": "string_value"
}'
```

#### With Authorization (if required)

```bash
curl -X POST http://localhost:51657/api/tools/particle-system-modify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
  "gameObjectRef": "string_value",
  "componentRef": "string_value",
  "main": "string_value",
  "emission": "string_value",
  "shape": "string_value",
  "velocityOverLifetime": "string_value",
  "limitVelocityOverLifetime": "string_value",
  "inheritVelocity": "string_value",
  "lifetimeByEmitterSpeed": "string_value",
  "forceOverLifetime": "string_value",
  "colorOverLifetime": "string_value",
  "colorBySpeed": "string_value",
  "sizeOverLifetime": "string_value",
  "sizeBySpeed": "string_value",
  "rotationOverLifetime": "string_value",
  "rotationBySpeed": "string_value",
  "externalForces": "string_value",
  "noise": "string_value",
  "collision": "string_value",
  "trigger": "string_value",
  "subEmitters": "string_value",
  "textureSheetAnimation": "string_value",
  "lights": "string_value",
  "trails": "string_value",
  "customData": "string_value",
  "renderer": "string_value"
}'
```

> The token is stored in the file: `UserSettings/AI-Game-Developer-Config.json`
> Using the format: `"token": "YOUR_TOKEN"`

## Input

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `gameObjectRef` | `any` | Yes | Reference to the GameObject containing the ParticleSystem component. |
| `componentRef` | `any` | No | Optional reference to a specific ParticleSystem component if the GameObject has multiple. If not provided, uses the first ParticleSystem found. |
| `main` | `any` | No | Main module data to apply. Only include properties you want to change. |
| `emission` | `any` | No | Emission module data to apply. Only include properties you want to change. |
| `shape` | `any` | No | Shape module data to apply. Only include properties you want to change. |
| `velocityOverLifetime` | `any` | No | Velocity over Lifetime module data to apply. Only include properties you want to change. |
| `limitVelocityOverLifetime` | `any` | No | Limit Velocity over Lifetime module data to apply. Only include properties you want to change. |
| `inheritVelocity` | `any` | No | Inherit Velocity module data to apply. Only include properties you want to change. |
| `lifetimeByEmitterSpeed` | `any` | No | Lifetime by Emitter Speed module data to apply. Only include properties you want to change. |
| `forceOverLifetime` | `any` | No | Force over Lifetime module data to apply. Only include properties you want to change. |
| `colorOverLifetime` | `any` | No | Color over Lifetime module data to apply. Only include properties you want to change. |
| `colorBySpeed` | `any` | No | Color by Speed module data to apply. Only include properties you want to change. |
| `sizeOverLifetime` | `any` | No | Size over Lifetime module data to apply. Only include properties you want to change. |
| `sizeBySpeed` | `any` | No | Size by Speed module data to apply. Only include properties you want to change. |
| `rotationOverLifetime` | `any` | No | Rotation over Lifetime module data to apply. Only include properties you want to change. |
| `rotationBySpeed` | `any` | No | Rotation by Speed module data to apply. Only include properties you want to change. |
| `externalForces` | `any` | No | External Forces module data to apply. Only include properties you want to change. |
| `noise` | `any` | No | Noise module data to apply. Only include properties you want to change. |
| `collision` | `any` | No | Collision module data to apply. Only include properties you want to change. |
| `trigger` | `any` | No | Trigger module data to apply. Only include properties you want to change. |
| `subEmitters` | `any` | No | Sub Emitters module data to apply. Only include properties you want to change. |
| `textureSheetAnimation` | `any` | No | Texture Sheet Animation module data to apply. Only include properties you want to change. |
| `lights` | `any` | No | Lights module data to apply. Only include properties you want to change. |
| `trails` | `any` | No | Trails module data to apply. Only include properties you want to change. |
| `customData` | `any` | No | Custom Data module data to apply. Only include properties you want to change. |
| `renderer` | `any` | No | Renderer module data to apply. Only include properties you want to change. |

### Input JSON Schema

```json
{
  "type": "object",
  "properties": {
    "gameObjectRef": {
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.GameObjectRef",
      "description": "Reference to the GameObject containing the ParticleSystem component."
    },
    "componentRef": {
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.ComponentRef",
      "description": "Optional reference to a specific ParticleSystem component if the GameObject has multiple. If not provided, uses the first ParticleSystem found."
    },
    "main": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Main module data to apply. Only include properties you want to change."
    },
    "emission": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Emission module data to apply. Only include properties you want to change."
    },
    "shape": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Shape module data to apply. Only include properties you want to change."
    },
    "velocityOverLifetime": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Velocity over Lifetime module data to apply. Only include properties you want to change."
    },
    "limitVelocityOverLifetime": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Limit Velocity over Lifetime module data to apply. Only include properties you want to change."
    },
    "inheritVelocity": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Inherit Velocity module data to apply. Only include properties you want to change."
    },
    "lifetimeByEmitterSpeed": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Lifetime by Emitter Speed module data to apply. Only include properties you want to change."
    },
    "forceOverLifetime": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Force over Lifetime module data to apply. Only include properties you want to change."
    },
    "colorOverLifetime": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Color over Lifetime module data to apply. Only include properties you want to change."
    },
    "colorBySpeed": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Color by Speed module data to apply. Only include properties you want to change."
    },
    "sizeOverLifetime": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Size over Lifetime module data to apply. Only include properties you want to change."
    },
    "sizeBySpeed": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Size by Speed module data to apply. Only include properties you want to change."
    },
    "rotationOverLifetime": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Rotation over Lifetime module data to apply. Only include properties you want to change."
    },
    "rotationBySpeed": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Rotation by Speed module data to apply. Only include properties you want to change."
    },
    "externalForces": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "External Forces module data to apply. Only include properties you want to change."
    },
    "noise": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Noise module data to apply. Only include properties you want to change."
    },
    "collision": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Collision module data to apply. Only include properties you want to change."
    },
    "trigger": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Trigger module data to apply. Only include properties you want to change."
    },
    "subEmitters": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Sub Emitters module data to apply. Only include properties you want to change."
    },
    "textureSheetAnimation": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Texture Sheet Animation module data to apply. Only include properties you want to change."
    },
    "lights": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Lights module data to apply. Only include properties you want to change."
    },
    "trails": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Trails module data to apply. Only include properties you want to change."
    },
    "customData": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Custom Data module data to apply. Only include properties you want to change."
    },
    "renderer": {
      "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
      "description": "Renderer module data to apply. Only include properties you want to change."
    }
  },
  "$defs": {
    "System.Type": {
      "type": "string"
    },
    "com.IvanMurzak.Unity.MCP.Runtime.Data.GameObjectRef": {
      "type": "object",
      "properties": {
        "instanceID": {
          "type": "integer",
          "description": "instanceID of the UnityEngine.Object. If it is \u00270\u0027 and \u0027path\u0027, \u0027name\u0027, \u0027assetPath\u0027 and \u0027assetGuid\u0027 is not provided, empty or null, then it will be used as \u0027null\u0027. Priority: 1 (Recommended)"
        },
        "path": {
          "type": "string",
          "description": "Path of a GameObject in the hierarchy Sample \u0027character/hand/finger/particle\u0027. Priority: 2."
        },
        "name": {
          "type": "string",
          "description": "Name of a GameObject in hierarchy. Priority: 3."
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
      "description": "Find GameObject in opened Prefab or in the active Scene."
    },
    "com.IvanMurzak.Unity.MCP.Runtime.Data.ComponentRef": {
      "type": "object",
      "properties": {
        "index": {
          "type": "integer",
          "description": "Component \u0027index\u0027 attached to a gameObject. The first index is \u00270\u0027 and that is usually Transform or RectTransform. Priority: 2. Default value is -1."
        },
        "typeName": {
          "type": "string",
          "description": "Component type full name. Sample \u0027UnityEngine.Transform\u0027. If the gameObject has two components of the same type, the output component is unpredictable. Priority: 3. Default value is null."
        },
        "instanceID": {
          "type": "integer",
          "description": "instanceID of the UnityEngine.Object. If this is \u00270\u0027, then it will be used as \u0027null\u0027."
        }
      },
      "required": [
        "index",
        "instanceID"
      ],
      "description": "Component reference. Used to find a Component at GameObject."
    },
    "com.IvanMurzak.ReflectorNet.Model.SerializedMemberList": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember"
      }
    },
    "com.IvanMurzak.ReflectorNet.Model.SerializedMember": {
      "type": "object",
      "properties": {
        "typeName": {
          "type": "string",
          "description": "Full type name. Eg: \u0027System.String\u0027, \u0027System.Int32\u0027, \u0027UnityEngine.Vector3\u0027, etc."
        },
        "name": {
          "type": "string",
          "description": "Object name."
        },
        "value": {
          "description": "Value of the object, serialized as a non stringified JSON element. Can be null if the value is not set. Can be default value if the value is an empty object or array json."
        },
        "fields": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
            "description": "Nested field value."
          },
          "description": "Fields of the object, serialized as a list of \u0027SerializedMember\u0027."
        },
        "props": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
            "description": "Nested property value."
          },
          "description": "Properties of the object, serialized as a list of \u0027SerializedMember\u0027."
        }
      },
      "required": [
        "typeName"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "gameObjectRef"
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
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.ParticleSystem.Editor.ModifyParticleSystemResponse",
      "description": "Response containing the result of modifying a ParticleSystem."
    }
  },
  "$defs": {
    "com.IvanMurzak.Unity.MCP.Runtime.Data.GameObjectRef": {
      "type": "object",
      "properties": {
        "instanceID": {
          "type": "integer",
          "description": "instanceID of the UnityEngine.Object. If it is \u00270\u0027 and \u0027path\u0027, \u0027name\u0027, \u0027assetPath\u0027 and \u0027assetGuid\u0027 is not provided, empty or null, then it will be used as \u0027null\u0027. Priority: 1 (Recommended)"
        },
        "path": {
          "type": "string",
          "description": "Path of a GameObject in the hierarchy Sample \u0027character/hand/finger/particle\u0027. Priority: 2."
        },
        "name": {
          "type": "string",
          "description": "Name of a GameObject in hierarchy. Priority: 3."
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
      "description": "Find GameObject in opened Prefab or in the active Scene."
    },
    "System.Type": {
      "type": "string"
    },
    "com.IvanMurzak.Unity.MCP.Runtime.Data.ComponentRef": {
      "type": "object",
      "properties": {
        "index": {
          "type": "integer",
          "description": "Component \u0027index\u0027 attached to a gameObject. The first index is \u00270\u0027 and that is usually Transform or RectTransform. Priority: 2. Default value is -1."
        },
        "typeName": {
          "type": "string",
          "description": "Component type full name. Sample \u0027UnityEngine.Transform\u0027. If the gameObject has two components of the same type, the output component is unpredictable. Priority: 3. Default value is null."
        },
        "instanceID": {
          "type": "integer",
          "description": "instanceID of the UnityEngine.Object. If this is \u00270\u0027, then it will be used as \u0027null\u0027."
        }
      },
      "required": [
        "index",
        "instanceID"
      ],
      "description": "Component reference. Used to find a Component at GameObject."
    },
    "System.String[]": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "com.IvanMurzak.Unity.MCP.ParticleSystem.Editor.ModifyParticleSystemResponse": {
      "type": "object",
      "properties": {
        "success": {
          "type": "boolean",
          "description": "Whether the modification was successful."
        },
        "gameObjectRef": {
          "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.GameObjectRef",
          "description": "Reference to the GameObject containing the ParticleSystem component."
        },
        "componentRef": {
          "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.ComponentRef",
          "description": "Reference to the modified ParticleSystem component."
        },
        "componentIndex": {
          "type": "integer",
          "description": "Index of the ParticleSystem component in the GameObject\u0027s component list."
        },
        "logs": {
          "$ref": "#/$defs/System.String[]",
          "description": "Log of modifications made and any warnings/errors encountered."
        }
      },
      "required": [
        "success",
        "componentIndex"
      ],
      "description": "Response containing the result of modifying a ParticleSystem."
    }
  },
  "required": [
    "result"
  ]
}
```

