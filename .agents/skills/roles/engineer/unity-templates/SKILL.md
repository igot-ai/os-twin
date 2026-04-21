---
name: unity-templates
description: C# code templates for standard Unity feature structure (GameLogic, Events, Controller, Model, View, UI, Config, Installer)"
tags: [engineer, unity, templates, scaffolding]
: core
---

# Unity Feature Templates

## Overview

Standard C# file templates for scaffolding new Unity features. Each template follows the project's Pure C# + VContainer + UniTask + UniRx architecture.

## When to Use

- Creating a new feature from scratch
- Engineer needs to scaffold the standard class set for a feature
- Ensuring consistent code structure across all features

## Template Files

| Template | Generated File | Purpose |
|---|---|---|
| FeatureGameLogic.cs.txt | {Feature}GameLogic.cs | Pure logic with ReactiveProperty, Subject |
| FeatureEvents.cs.txt | {Feature}Events.cs | readonly struct events |
| FeatureModel.cs.txt | {Feature}Model.cs | ViewModel with state |
| FeatureController.cs.txt | {Feature}Controller.cs | MonoBehaviour orchestrator |
| FeatureController.Debug.cs.txt | {Feature}Controller.Debug.cs | Debug-only partial class |
| FeatureView.cs.txt | {Feature}View.cs | View subscription handler |
| FeatureUI.cs.txt | {Feature}UI.cs | MainView<T> screen |
| FeatureUIModel.cs.txt | {Feature}UIModel.cs | UI ViewModel |
| FeatureConfig.cs.txt | {Feature}Config.cs | ScriptableObject config |
| FeatureInstaller.cs.txt | {Feature}Installer.cs | VContainer registration |
| EFeatureState.cs.txt | E{Feature}State.cs | State enum |
| IFeatureService.cs.txt | I{Feature}Service.cs | Public interface |

## Instructions

1. Read the appropriate template file from this directory
2. Replace `{Feature}` / `Feature` with the actual feature name (PascalCase)
3. Place generated files in the correct Unity project directory
4. Register the Installer in the appropriate VContainer scope
5. Run unity-code-review after generation to validate
