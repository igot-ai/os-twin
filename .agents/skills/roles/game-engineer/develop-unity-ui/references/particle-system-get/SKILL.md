---
name: particle-system-get
description: Get detailed information about a ParticleSystem component on a GameObject. Returns particle system state and optionally serialized data for each module. Use the boolean flags to request specific modules. Use this to inspect ParticleSystem data before modifying it.
---

# ParticleSystem / Get

Get detailed information about a ParticleSystem component on a GameObject. Returns particle system state and optionally serialized data for each module. Use the boolean flags to request specific modules. Use this to inspect ParticleSystem data before modifying it.

## How to Call

### HTTP API (Direct Tool Execution)

Execute this tool directly via the MCP Plugin HTTP API:

```bash
curl -X POST http://localhost:51657/api/tools/particle-system-get \
  -H "Content-Type: application/json" \
  -d '{
  "gameObjectRef": "string_value",
  "componentRef": "string_value",
  "includeMain": false,
  "includeEmission": false,
  "includeShape": false,
  "includeVelocityOverLifetime": false,
  "includeLimitVelocityOverLifetime": false,
  "includeInheritVelocity": false,
  "includeLifetimeByEmitterSpeed": false,
  "includeForceOverLifetime": false,
  "includeColorOverLifetime": false,
  "includeColorBySpeed": false,
  "includeSizeOverLifetime": false,
  "includeSizeBySpeed": false,
  "includeRotationOverLifetime": false,
  "includeRotationBySpeed": false,
  "includeExternalForces": false,
  "includeNoise": false,
  "includeCollision": false,
  "includeTrigger": false,
  "includeSubEmitters": false,
  "includeTextureSheetAnimation": false,
  "includeLights": false,
  "includeTrails": false,
  "includeCustomData": false,
  "includeRenderer": false,
  "includeAll": false,
  "deepSerialization": false
}'
```

#### With Authorization (if required)

```bash
curl -X POST http://localhost:51657/api/tools/particle-system-get \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
  "gameObjectRef": "string_value",
  "componentRef": "string_value",
  "includeMain": false,
  "includeEmission": false,
  "includeShape": false,
  "includeVelocityOverLifetime": false,
  "includeLimitVelocityOverLifetime": false,
  "includeInheritVelocity": false,
  "includeLifetimeByEmitterSpeed": false,
  "includeForceOverLifetime": false,
  "includeColorOverLifetime": false,
  "includeColorBySpeed": false,
  "includeSizeOverLifetime": false,
  "includeSizeBySpeed": false,
  "includeRotationOverLifetime": false,
  "includeRotationBySpeed": false,
  "includeExternalForces": false,
  "includeNoise": false,
  "includeCollision": false,
  "includeTrigger": false,
  "includeSubEmitters": false,
  "includeTextureSheetAnimation": false,
  "includeLights": false,
  "includeTrails": false,
  "includeCustomData": false,
  "includeRenderer": false,
  "includeAll": false,
  "deepSerialization": false
}'
```

> The token is stored in the file: `UserSettings/AI-Game-Developer-Config.json`
> Using the format: `"token": "YOUR_TOKEN"`

## Input

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `gameObjectRef` | `any` | Yes | Reference to the GameObject containing the ParticleSystem component. |
| `componentRef` | `any` | No | Optional reference to a specific ParticleSystem component if the GameObject has multiple. If not provided, uses the first ParticleSystem found. |
| `includeMain` | `boolean` | No | Include Main module data (duration, looping, prewarm, startDelay, startLifetime, startSpeed, startSize, startRotation, startColor, gravityModifier, simulationSpace, scalingMode, playOnAwake, maxParticles, etc.). |
| `includeEmission` | `boolean` | No | Include Emission module data (rateOverTime, rateOverDistance, bursts). |
| `includeShape` | `boolean` | No | Include Shape module data (shapeType, radius, angle, arc, position, rotation, scale, mesh, texture, etc.). |
| `includeVelocityOverLifetime` | `boolean` | No | Include Velocity over Lifetime module data (x, y, z, space, orbital, radial, speedModifier). |
| `includeLimitVelocityOverLifetime` | `boolean` | No | Include Limit Velocity over Lifetime module data (limit, dampen, separateAxes, drag). |
| `includeInheritVelocity` | `boolean` | No | Include Inherit Velocity module data (mode, curve). |
| `includeLifetimeByEmitterSpeed` | `boolean` | No | Include Lifetime by Emitter Speed module data (curve, range). |
| `includeForceOverLifetime` | `boolean` | No | Include Force over Lifetime module data (x, y, z, space, randomized). |
| `includeColorOverLifetime` | `boolean` | No | Include Color over Lifetime module data (color gradient). |
| `includeColorBySpeed` | `boolean` | No | Include Color by Speed module data (color, range). |
| `includeSizeOverLifetime` | `boolean` | No | Include Size over Lifetime module data (size curve, separateAxes). |
| `includeSizeBySpeed` | `boolean` | No | Include Size by Speed module data (size, range). |
| `includeRotationOverLifetime` | `boolean` | No | Include Rotation over Lifetime module data (angular velocity, separateAxes). |
| `includeRotationBySpeed` | `boolean` | No | Include Rotation by Speed module data (angular velocity, range). |
| `includeExternalForces` | `boolean` | No | Include External Forces module data (multiplier, influenceFilter). |
| `includeNoise` | `boolean` | No | Include Noise module data (strength, frequency, scrollSpeed, damping, octaves, quality, remap). |
| `includeCollision` | `boolean` | No | Include Collision module data (type, mode, planes, dampen, bounce, lifetimeLoss). |
| `includeTrigger` | `boolean` | No | Include Trigger module data (inside, outside, enter, exit actions). |
| `includeSubEmitters` | `boolean` | No | Include Sub Emitters module data (birth, collision, death, trigger, manual emitters). |
| `includeTextureSheetAnimation` | `boolean` | No | Include Texture Sheet Animation module data (mode, tiles, animation, frameOverTime). |
| `includeLights` | `boolean` | No | Include Lights module data (ratio, light, color, range, intensity). |
| `includeTrails` | `boolean` | No | Include Trails module data (mode, ratio, lifetime, width, color). |
| `includeCustomData` | `boolean` | No | Include Custom Data module data (modes, vectors, colors). |
| `includeRenderer` | `boolean` | No | Include Renderer module data (renderMode, material, sortMode, alignment, shadows). |
| `includeAll` | `boolean` | No | Include ALL modules data. Overrides individual flags. |
| `deepSerialization` | `boolean` | No | Performs deep serialization including all nested objects. Otherwise, only serializes top-level members. |

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
    "includeMain": {
      "type": "boolean",
      "description": "Include Main module data (duration, looping, prewarm, startDelay, startLifetime, startSpeed, startSize, startRotation, startColor, gravityModifier, simulationSpace, scalingMode, playOnAwake, maxParticles, etc.)."
    },
    "includeEmission": {
      "type": "boolean",
      "description": "Include Emission module data (rateOverTime, rateOverDistance, bursts)."
    },
    "includeShape": {
      "type": "boolean",
      "description": "Include Shape module data (shapeType, radius, angle, arc, position, rotation, scale, mesh, texture, etc.)."
    },
    "includeVelocityOverLifetime": {
      "type": "boolean",
      "description": "Include Velocity over Lifetime module data (x, y, z, space, orbital, radial, speedModifier)."
    },
    "includeLimitVelocityOverLifetime": {
      "type": "boolean",
      "description": "Include Limit Velocity over Lifetime module data (limit, dampen, separateAxes, drag)."
    },
    "includeInheritVelocity": {
      "type": "boolean",
      "description": "Include Inherit Velocity module data (mode, curve)."
    },
    "includeLifetimeByEmitterSpeed": {
      "type": "boolean",
      "description": "Include Lifetime by Emitter Speed module data (curve, range)."
    },
    "includeForceOverLifetime": {
      "type": "boolean",
      "description": "Include Force over Lifetime module data (x, y, z, space, randomized)."
    },
    "includeColorOverLifetime": {
      "type": "boolean",
      "description": "Include Color over Lifetime module data (color gradient)."
    },
    "includeColorBySpeed": {
      "type": "boolean",
      "description": "Include Color by Speed module data (color, range)."
    },
    "includeSizeOverLifetime": {
      "type": "boolean",
      "description": "Include Size over Lifetime module data (size curve, separateAxes)."
    },
    "includeSizeBySpeed": {
      "type": "boolean",
      "description": "Include Size by Speed module data (size, range)."
    },
    "includeRotationOverLifetime": {
      "type": "boolean",
      "description": "Include Rotation over Lifetime module data (angular velocity, separateAxes)."
    },
    "includeRotationBySpeed": {
      "type": "boolean",
      "description": "Include Rotation by Speed module data (angular velocity, range)."
    },
    "includeExternalForces": {
      "type": "boolean",
      "description": "Include External Forces module data (multiplier, influenceFilter)."
    },
    "includeNoise": {
      "type": "boolean",
      "description": "Include Noise module data (strength, frequency, scrollSpeed, damping, octaves, quality, remap)."
    },
    "includeCollision": {
      "type": "boolean",
      "description": "Include Collision module data (type, mode, planes, dampen, bounce, lifetimeLoss)."
    },
    "includeTrigger": {
      "type": "boolean",
      "description": "Include Trigger module data (inside, outside, enter, exit actions)."
    },
    "includeSubEmitters": {
      "type": "boolean",
      "description": "Include Sub Emitters module data (birth, collision, death, trigger, manual emitters)."
    },
    "includeTextureSheetAnimation": {
      "type": "boolean",
      "description": "Include Texture Sheet Animation module data (mode, tiles, animation, frameOverTime)."
    },
    "includeLights": {
      "type": "boolean",
      "description": "Include Lights module data (ratio, light, color, range, intensity)."
    },
    "includeTrails": {
      "type": "boolean",
      "description": "Include Trails module data (mode, ratio, lifetime, width, color)."
    },
    "includeCustomData": {
      "type": "boolean",
      "description": "Include Custom Data module data (modes, vectors, colors)."
    },
    "includeRenderer": {
      "type": "boolean",
      "description": "Include Renderer module data (renderMode, material, sortMode, alignment, shadows)."
    },
    "includeAll": {
      "type": "boolean",
      "description": "Include ALL modules data. Overrides individual flags."
    },
    "deepSerialization": {
      "type": "boolean",
      "description": "Performs deep serialization including all nested objects. Otherwise, only serializes top-level members."
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
      "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.ParticleSystem.Editor.GetParticleSystemResponse",
      "description": "Response containing ParticleSystem data with requested modules."
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
    },
    "com.IvanMurzak.ReflectorNet.Model.SerializedMemberList": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember"
      }
    },
    "com.IvanMurzak.Unity.MCP.ParticleSystem.Editor.GetParticleSystemResponse": {
      "type": "object",
      "properties": {
        "gameObjectRef": {
          "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.GameObjectRef",
          "description": "Reference to the GameObject containing the ParticleSystem component."
        },
        "componentRef": {
          "$ref": "#/$defs/com.IvanMurzak.Unity.MCP.Runtime.Data.ComponentRef",
          "description": "Reference to the ParticleSystem component."
        },
        "componentIndex": {
          "type": "integer",
          "description": "Index of the ParticleSystem component in the GameObject\u0027s component list."
        },
        "isPlaying": {
          "type": "boolean",
          "description": "Whether the ParticleSystem is currently playing."
        },
        "isPaused": {
          "type": "boolean",
          "description": "Whether the ParticleSystem is currently paused."
        },
        "isEmitting": {
          "type": "boolean",
          "description": "Whether the ParticleSystem is currently emitting."
        },
        "isStopped": {
          "type": "boolean",
          "description": "Whether the ParticleSystem is currently stopped."
        },
        "particleCount": {
          "type": "integer",
          "description": "Current particle count."
        },
        "time": {
          "type": "number",
          "description": "Current simulation time."
        },
        "main": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Main module data."
        },
        "emission": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Emission module data."
        },
        "shape": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Shape module data."
        },
        "velocityOverLifetime": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Velocity over Lifetime module data."
        },
        "limitVelocityOverLifetime": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Limit Velocity over Lifetime module data."
        },
        "inheritVelocity": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Inherit Velocity module data."
        },
        "lifetimeByEmitterSpeed": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Lifetime by Emitter Speed module data."
        },
        "forceOverLifetime": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Force over Lifetime module data."
        },
        "colorOverLifetime": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Color over Lifetime module data."
        },
        "colorBySpeed": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Color by Speed module data."
        },
        "sizeOverLifetime": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Size over Lifetime module data."
        },
        "sizeBySpeed": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Size by Speed module data."
        },
        "rotationOverLifetime": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Rotation over Lifetime module data."
        },
        "rotationBySpeed": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Rotation by Speed module data."
        },
        "externalForces": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "External Forces module data."
        },
        "noise": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Noise module data."
        },
        "collision": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Collision module data."
        },
        "trigger": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Trigger module data."
        },
        "subEmitters": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Sub Emitters module data."
        },
        "textureSheetAnimation": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Texture Sheet Animation module data."
        },
        "lights": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Lights module data."
        },
        "trails": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Trails module data."
        },
        "customData": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Custom Data module data."
        },
        "renderer": {
          "$ref": "#/$defs/com.IvanMurzak.ReflectorNet.Model.SerializedMember",
          "description": "Renderer module data."
        }
      },
      "required": [
        "componentIndex",
        "isPlaying",
        "isPaused",
        "isEmitting",
        "isStopped",
        "particleCount",
        "time"
      ],
      "description": "Response containing ParticleSystem data with requested modules."
    }
  },
  "required": [
    "result"
  ]
}
```

