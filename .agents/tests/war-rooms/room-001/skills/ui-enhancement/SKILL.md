---
name: ui-enhancement
description: Enhance existing Unity UI components"
tags: [engineer, implementation, ui]
trust_level: core
---

# Workflow: UI Enhancement
description: Improve UI aesthetics to "Premium" standards using PrimeTween and modern design.

## Preconditions
- `unity-ugui` skill and `ui-animation.md` reference read.
- Target UI screen is open in the Game View.

## Steps
1. **Audit**: Capture a baseline screenshot using `mcp_unity-editor_screenshot-game-view`. Analyze for alignment, contrast, and spacing issues.
2. **Redesign**: Apply modern aesthetics.
   - Use Google Fonts (Inter, Roboto, etc.) via TextMeshPro.
   - Implement smooth gradients and glassmorphism where appropriate.
   - Reference `../unity-ugui/references/ugui-components.md` for property names.
3. **Animate**: Add micro-animations using **PrimeTween**.
   - **Scale/Fade**: Use `Tween.Scale` and `Tween.Alpha` for interactive elements.
   - **Sequencing**: Chain animations for windows showing/hiding.
   - **Reference**: Follow `../unity-ugui/references/ui-animation.md`.
4. **Polish & Verify**: 
   - Take a follow-up screenshot to verify the improvement.
   - Run `mcp_unity-editor_console-get-logs` to ensure no tween-related errors.
   - Ensure 60 FPS performance on mobile targets.

## Output
- Visually stunning, high-performance UI with smooth micro-animations.
