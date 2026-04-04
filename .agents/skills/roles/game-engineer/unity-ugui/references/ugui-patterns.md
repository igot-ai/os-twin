# uGUI Patterns & Structure

Standard structural rules for building UI screens in the Snake Escape project.

## Standard Hierarchy

Every primary screen or popup MUST follow this hierarchical organization:

- **UI_{ScreenName}** (Root: `RectTransform`, `Canvas`, `CanvasScaler`, `GraphicRaycaster`, `UIAnimationBehaviour`)
  - **Background** (Visual base: `Image`, `CanvasGroup` for fading)
    - **Anchors** (Layout containers)
      - **LeftAnchor** (e.g., Back buttons, side panels)
      - **RightAnchor** (e.g., Settings, currency displays)
      - **UpperAnchor** (e.g., Title, status bars)
      - **LowerAnchor** (e.g., Navigation, action buttons)
      - **PopupAnchor** (For centered content if the screen is a popup)

## Canvas Scaler Configuration

Always use the "Scale With Screen Size" mode:
- **UI Scale Mode**: `ScaleWithScreenSize`
- **Reference Resolution**: `1080 x 1920` (Portrait) or `1920 x 1080` (Landscape)
- **Screen Match Mode**: `Match Width Or Height`
- **Match**: `0.5` (Balances scaling for various aspect ratios)

## Mandatory Components

- **UIAnimationBehaviour**: Must be on any root or panel that requires transitions/animations.
- **LocalizeUIText**: Must be attached to any GameObject that has a `TMP_Text` or `Text` component.
- **UIParticle**: Required for any `ParticleSystem` inside a Canvas to ensure proper rendering layers.

## Layout Best Practices

1.  **Anchors and Pivots**: Set anchors and pivots correctly BEFORE using LayoutGroups.
2.  **LayoutGroups**: Use `VerticalLayoutGroup` and `HorizontalLayoutGroup` sparingly. Prefer manual positioning or the `RectTransform` anchor system for static structures.
3.  **ContentSizeFitter**: Avoid nesting multiple `ContentSizeFitter` components as it causes layout "jitter" and performance spikes.
4.  **SafeArea**: For mobile builds, ensure the root container respects the device notch (Safe Area).
