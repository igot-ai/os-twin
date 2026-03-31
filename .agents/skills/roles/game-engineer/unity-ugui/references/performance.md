# UI Performance Optimization

Guidelines for maintaining 60+ FPS on mobile devices with complex UI.

## Canvas Management

### 1. Canvas Splitting
- **Static Canvas**: Elements that never change (borders, background).
- **Dynamic Canvas**: Elements that update frequently (timers, health bars, inventory counts).
- **Rationale**: When one element in a Canvas changes, Unity rebuilds the entire Canvas mesh. Splitting reduces the mesh complexity for each rebuild.

### 2. Nested Canvases
- Use `Canvas` components on child objects to create sub-canvases for specific UI modules like a "Minimap" or "Skill Bar".

## Draw Call Minimization

- **Sprite Atlas**: Group all UI sprites for a single screen into one atlas.
- **Z-Position**: Keep all UI elements at `Z = 0`. Non-zero Z-values can break draw call batching.
- **Texture Packing**: Use the 2D Sprite Packer (Sprite Atlas) to ensure multiple UI images are drawn in a single call.

## Raycast Target Management

- **Disable Raycast Target**: Uncheck `Raycast Target` on all non-interactive images, backgrounds, and text.
- **Why**: Every interactive element is added to the "Graphic Raycaster" list. Reducing this list speeds up input processing.

## UI Scripting Performance

- **Disable UI during transitions**: Set the root `GraphicRaycaster.enabled = false` while a window is opening or closing.
- **CanvasGroup Alpha**: For fading, use `CanvasGroup.alpha` instead of changing image color/alpha, as it performs better and avoids Canvas rebuilds.
- **Hide vs Destroy**: Prefer `gameObject.SetActive(false)` or `CanvasGroup.alpha = 0` for frequently toggled UI instead of `Instantiate/Destroy`.

## Mobile Heat & Battery

- Minimize the number of `LayoutGroup` components. They are expensive to recalculate.
- Use `RectTransform` anchoring instead of `VerticalLayoutGroup` whenever possible.
- Optimize TextMeshPro updates as described in [TextMeshPro.md](text-mesh-pro.md).