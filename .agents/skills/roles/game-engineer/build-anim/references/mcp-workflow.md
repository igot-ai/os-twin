# MCP Animation Tool Workflows

Step-by-step workflows for creating AnimationClips and Animator Controllers via Unity Editor MCP tools.

---

## When to Use MCP Animation Tools vs PrimeTween

| Criterion | Use PrimeTween (default) | Use Animator via MCP |
|---|---|---|
| One-shot feedback (tap, punch, pop) | Yes | No |
| Data-driven timing (from JSON keyframes) | Yes | No |
| Runtime-computed values (fly to position X) | Yes | No |
| Simple show/hide (fade in/out) | Yes | No |
| Designer-editable curves in Inspector | No | Yes |
| Complex state machine (Open/Close/Disabled) | No | Yes |
| Screen transitions with multiple states | No | Yes |
| Animation that non-programmers need to edit | No | Yes |

**Default to PrimeTween.** Only use Animator when the animation needs a state machine or designer-editable curves.

**Never use**: Legacy `Animation` component or manual `while(elapsed < duration)` loops.

---

## Workflow A: Create AnimationClips

### Step 1: Create the clip asset

```
Tool: animation-create
Args:
  assetPath: "Assets/Game/Animations/{FeatureName}/Open.anim"
```

### Step 2: Add keyframe curves

```
Tool: animation-modify
Args:
  assetPath: "Assets/Game/Animations/{FeatureName}/Open.anim"
  modifications:
    - type: "SetCurve"
      relativePath: ""
      componentType: "CanvasGroup"
      propertyName: "m_Alpha"
      keyframes:
        - { time: 0.0, value: 0.0 }
        - { time: 0.3, value: 1.0 }

    - type: "SetCurve"
      relativePath: ""
      componentType: "UnityEngine.RectTransform"
      propertyName: "m_AnchoredPosition.y"
      keyframes:
        - { time: 0.0, value: -50.0 }
        - { time: 0.3, value: 0.0 }
```

### Common curve patterns

**Fade in:**
```json
{ "componentType": "CanvasGroup", "propertyName": "m_Alpha",
  "keyframes": [{ "time": 0, "value": 0 }, { "time": 0.3, "value": 1 }] }
```

**Scale pop:**
```json
{ "componentType": "UnityEngine.RectTransform", "propertyName": "localScale.x",
  "keyframes": [{ "time": 0, "value": 0 }, { "time": 0.2, "value": 1.1 }, { "time": 0.35, "value": 1 }] }
```

**Slide up:**
```json
{ "componentType": "UnityEngine.RectTransform", "propertyName": "m_AnchoredPosition.y",
  "keyframes": [{ "time": 0, "value": -100 }, { "time": 0.3, "value": 0 }] }
```

---

## Workflow B: Create Animator Controller

### Step 1: Create clip assets first (Workflow A)

Create all needed .anim files before building the state machine.

### Step 2: Create the Animator Controller

```
Tool: animator-create
Args:
  assetPath: "Assets/Game/Animations/{FeatureName}/{Screen}Animator.controller"
```

### Step 3: Build the state machine

```
Tool: animator-modify
Args:
  assetPath: "Assets/Game/Animations/{FeatureName}/{Screen}Animator.controller"
  modifications:
    # Add parameters
    - type: "AddParameter"
      parameterName: "Open"
      parameterType: "Bool"

    # Add states with motions
    - type: "AddState"
      layerName: "Base Layer"
      stateName: "Closed"
      motionAssetPath: "Assets/Game/Animations/{FeatureName}/Closed.anim"

    - type: "AddState"
      layerName: "Base Layer"
      stateName: "Open"
      motionAssetPath: "Assets/Game/Animations/{FeatureName}/Open.anim"

    # Set default state
    - type: "SetDefaultState"
      layerName: "Base Layer"
      stateName: "Closed"

    # Add transitions
    - type: "AddTransition"
      sourceStateName: "Closed"
      destinationStateName: "Open"
      hasExitTime: false
      duration: 0.1
      conditions:
        - parameter: "Open"
          mode: "If"

    - type: "AddTransition"
      sourceStateName: "Open"
      destinationStateName: "Closed"
      hasExitTime: false
      duration: 0.1
      conditions:
        - parameter: "Open"
          mode: "IfNot"
```

### Step 4: Assign to GameObject

Use `gameobject-component-add` to add an Animator component, then `gameobject-component-modify` to assign the controller:

```
Tool: gameobject-component-add
Args:
  gameObjectPath: "UI_Root/PopupCard"
  componentType: "Animator"

Tool: gameobject-component-modify
Args:
  gameObjectPath: "UI_Root/PopupCard"
  componentType: "Animator"
  properties:
    runtimeAnimatorController: "Assets/Game/Animations/{FeatureName}/{Screen}Animator.controller"
```

---

## Workflow C: Scene Inspection

Use these tools to understand the current scene before wiring:

### List opened scenes
```
Tool: scene-list-opened
```

### Get scene hierarchy
```
Tool: scene-get-data
Args:
  sceneName: "<scene name from scene-list-opened>"
```

### Find specific GameObjects
```
Tool: gameobject-find
Args:
  searchPattern: "BtnRefill"
  searchType: "name"
```

### Inspect components on a GO
```
Tool: gameobject-component-list-all
Args:
  gameObjectPath: "UI_Root/PopupCard/BtnRefill"
```

### Get component property values
```
Tool: gameobject-component-get
Args:
  gameObjectPath: "UI_Root/PopupCard/BtnRefill"
  componentType: "RectTransform"
```

---

## Workflow D: Wire Scripts to Scene

### Add script component
```
Tool: gameobject-component-add
Args:
  gameObjectPath: "UI_Root/PopupCard"
  componentType: "Game.Features.Refill.Animation.RefillAnimationController"
```

### Set serialized field references

Use `script-execute` to wire inspector references:

```csharp
// script-execute code
var controller = GameObject.Find("UI_Root/PopupCard")
    .GetComponent<Game.Features.Refill.Animation.RefillAnimationController>();
var overlay = GameObject.Find("UI_Root/DimOverlay").GetComponent<CanvasGroup>();

var so = new UnityEditor.SerializedObject(controller);
so.FindProperty("_overlayCanvasGroup").objectReferenceValue = overlay;
so.ApplyModifiedProperties();
UnityEditor.EditorUtility.SetDirty(controller);
```

### Save scene after wiring
```
Tool: scene-save
```

---

## Workflow E: Play Mode Validation

### Enter Play Mode
```
Tool: script-execute
Code: UnityEditor.EditorApplication.isPlaying = true;
```

### Check for errors
```
Tool: console-get-logs
Args:
  lastMinutes: 1
  logTypeFilter: "Error"
```

### Capture screenshot
```
Tool: screenshot-game-view  (if available)
```

### Exit Play Mode
```
Tool: script-execute
Code: UnityEditor.EditorApplication.isPlaying = false;
```

---

## Common MCP Mistakes

| Mistake | Fix |
|---|---|
| Inspector refs not persisted | Always call `EditorUtility.SetDirty()` + `scene-save` after `script-execute` |
| Component type not found | Run `assets-refresh` first to compile new scripts |
| Wrong GameObjectPath | Use `gameobject-find` to verify path before adding components |
| Animator controller has no default state | Always call `SetDefaultState` after `AddState` |
| Missing EventSystem for Button clicks | Check with `gameobject-find` for EventSystem, add one if missing |
