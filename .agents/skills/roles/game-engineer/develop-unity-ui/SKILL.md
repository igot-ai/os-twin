---
name: develop-unity-ui
description: >-
  Interact with Unity to develop UI and assets. Use this skill to manage assets,
  scenes, GameObjects, components, and animations. It guides you to use the 64
  specialized sub-skills found in `.agent/skills/unity-editor/`. Always trigger
  this skill when the user asks to "create a prefab", "modify the scene hierarchy",
  "setup animations", "add components", or "capture screenshots".
---

# Developing UI Orchestrator

This skill provides the logical framework for performing complex Unity Editor tasks by orchestrating 64 specialized sub-skills.

> [!IMPORTANT]
> Do not attempt to use "shell scripts" or "manual file edits" for Unity Scene or Prefab modifications. Always use these tools to ensure data integrity and proper serialization.

## Sub-Skill Categories

The Unity Editor tools are divided into functional areas. Each path below points to a local `SKILL.md` with detailed tool schemas.

### 📦 Asset Management
- **Find/Query**: [assets-find](references/assets-find/SKILL.md), [assets-find-built-in](references/assets-find-built-in/SKILL.md), [assets-get-data](references/assets-get-data/SKILL.md)
- **Lifecycle**: [assets-copy](references/assets-copy/SKILL.md), [assets-move](references/assets-move/SKILL.md), [assets-delete](references/assets-delete/SKILL.md), [assets-create-folder](references/assets-create-folder/SKILL.md)
- **Modify**: [assets-modify](references/assets-modify/SKILL.md), [assets-refresh](references/assets-refresh/SKILL.md)
- **Specialized Assets**: [assets-material-create](references/assets-material-create/SKILL.md), [assets-shader-list-all](references/assets-shader-list-all/SKILL.md)

### 🏗️ GameObject & Hierarchy
- **Lifecycle**: [gameobject-create](references/gameobject-create/SKILL.md), [gameobject-destroy](references/gameobject-destroy/SKILL.md), [gameobject-duplicate](references/gameobject-duplicate/SKILL.md)
- **Hierarchy**: [gameobject-find](references/gameobject-find/SKILL.md), [gameobject-set-parent](references/gameobject-set-parent/SKILL.md), [gameobject-modify](references/gameobject-modify/SKILL.md)
- **Components**: [gameobject-component-add](references/gameobject-component-add/SKILL.md), [gameobject-component-get](references/gameobject-component-get/SKILL.md), [gameobject-component-modify](references/gameobject-component-modify/SKILL.md), [gameobject-component-list-all](references/gameobject-component-list-all/SKILL.md)

### 🧩 Prefabs
- **Workflow**: [assets-prefab-open](references/assets-prefab-open/SKILL.md) → [Modify] → [assets-prefab-save](references/assets-prefab-save/SKILL.md) → [assets-prefab-close](references/assets-prefab-close/SKILL.md)
- **Create**: [assets-prefab-create](references/assets-prefab-create/SKILL.md)
- **Instantiate**: [assets-prefab-instantiate](references/assets-prefab-instantiate/SKILL.md)

### 🎬 Scenes
- **Lifecycle**: [scene-create](./scene-create/SKILL.md), [scene-open](./scene-open/SKILL.md), [scene-save](./scene-save/SKILL.md), [scene-unload](./scene-unload/SKILL.md)
- **Query**: [scene-get-data](./scene-get-data/SKILL.md), [scene-list-opened](./scene-list-opened/SKILL.md)

### 💃 Animation & Particle Systems
- **Animation**: [animation-create](references/animation-create/SKILL.md), [animation-modify](references/animation-modify/SKILL.md), [animation-get-data](references/animation-get-data/SKILL.md)
- **Animator**: [animator-create](references/animator-create/SKILL.md), [animator-modify](references/animator-modify/SKILL.md)
- **Particles**: [particle-system-get](references/particle-system-get/SKILL.md), [particle-system-modify](references/particle-system-modify/SKILL.md)

### 🛠️ Schemas & Reflection
- **Reflection**: [reflection-method-call](./reflection-method-call/SKILL.md), [reflection-method-find](./reflection-method-find/SKILL.md)
- **Schemas**: [type-get-json-schema](./type-get-json-schema/SKILL.md)

### 📦 Package Manager
- [package-list](references/package-list/SKILL.md), [package-add](references/package-add/SKILL.md), [package-search](references/package-search/SKILL.md)

### 📸 Visuals & Logs
- **Screenshots**: [screenshot-scene-view](./screenshot-scene-view/SKILL.md), [screenshot-game-view](./screenshot-game-view/SKILL.md), [screenshot-camera](./screenshot-camera/SKILL.md)
- **Console**: [console-get-logs](references/console-get-logs/SKILL.md)

---

## Standard Workflows

### 1. Modifying an Existing Prefab
1.  **Find the Prefab**: Use `assets-find` to get the `assetPath` or `assetGuid`.
2.  **Open for Editing**: Use `assets-prefab-open`.
3.  **Find target GameObject**: Use `gameobject-find` or `gameobject-component-list-all` inside the opened prefab.
4.  **Perform Modifications**: Add components or modify properties.
5.  **Save and Close**: Use `assets-prefab-save` followed by `assets-prefab-close`.

### 2. Creating high-level Scene Structure
1.  **Create Root GameObject**: Use `gameobject-create`.
2.  **Add Components**: Use `gameobject-component-add`.
3.  **Adjust Transform**: Use `gameobject-modify`.
4.  **Save Scene**: Use `scene-save`.

## Core Concepts

### Working with Object References
Tools usually accept an `AssetObjectRef` or `GameObjectRef`. 
- **instanceID**: The most reliable way to reference an object *during a session*. 
- **assetGuid**: Persistent across sessions for Assets.
- **Hierarchy Path**: Use `Parent/Child/Grandchild` for GameObjects.

### Data Manipulation Strategies
- Use `type-get-json-schema` to understand the data structure of a specific Component type before calling `modify` tools.

---

## Mandatory Execution Checklist

- [ ] **Inventory**: Identify which sub-skills (Assets, Scenes, GameObjects) are needed.
- [ ] **Context**: Verify if you are working in a **Scene** or a **Prefab Stage**.
- [ ] **Save Often**: Call `scene-save` or `assets-prefab-save` after logical batches of work.
- [ ] **Refresh**: Call `assets-refresh` after creating new files (Textures, Materials, Prefabs) to ensure the Editor notices them.
- [ ] **Cleanup**: Close prefabs when editing is finished.
- [ ] **Verification**: Check logs (`console-get-logs`) for compiler issues and capture a screenshot (`screenshot-game-view` or `screenshot-scene-view`) and to PROVE the change worked.
