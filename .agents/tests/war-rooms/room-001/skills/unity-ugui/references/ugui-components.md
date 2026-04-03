# UGUI 2.0 Component Reference

Quick reference for all uGUI components, their key properties, and the `unity-editor` tools to manipulate them.

## Canvas Components

### Canvas
- **Render Mode**: Overlay, Camera, World Space
- **Sorting Order**: Controls draw order between multiple canvases
- **Additional Shader Channels**: TexCoord1, Normal, Tangent (enable for TMP effects)
- **Tool**: `gameobject-component-add` → `UnityEngine.Canvas`

### CanvasScaler
- **UI Scale Mode**: ConstantPixelSize, ScaleWithScreenSize, ConstantPhysicalSize
- **Reference Resolution**: Design target (e.g., 1080×1920)
- **Screen Match Mode**: MatchWidthOrHeight (use Match=0.5)
- **Reference Pixels Per Unit**: 100 (default)
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.CanvasScaler`

### GraphicRaycaster
- **Ignore Reversed Graphics**: true (default)
- **Blocking Objects**: None, Two-D, Three-D, All
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.GraphicRaycaster`

### CanvasGroup
- **Alpha**: 0–1 (use for fade transitions)
- **Interactable**: Enable/disable all children
- **Blocks Raycasts**: Enable/disable touch for all children
- **Ignore Parent Groups**: Override parent CanvasGroup settings
- **Tool**: `gameobject-component-add` → `UnityEngine.CanvasGroup`

## Visual Components

### Image
- **Source Image**: Sprite reference
- **Color**: Tint color
- **Material**: Optional custom material
- **Image Type**: Simple, Sliced, Tiled, Filled
- **Raycast Target**: Disable for non-interactive images (performance)
- **Preserve Aspect**: Keep sprite aspect ratio
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.Image`

### RawImage
- **Texture**: Raw texture reference (not Sprite)
- **UV Rect**: Control which portion of texture to display
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.RawImage`

### TextMeshProUGUI (TMP)
- **Text**: Content string (supports rich text tags)
- **Font Asset**: TMP_FontAsset reference
- **Font Size**: Size in points
- **Alignment**: Horizontal + Vertical
- **Color**: Text color
- **Raycast Target**: Disable for labels (performance)
- **Tool**: `gameobject-component-add` → `TMPro.TextMeshProUGUI`

### Mask
- **Show Mask Graphic**: Whether the mask Image is visible
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.Mask`

### RectMask2D
- Efficient rectangular clipping (no stencil buffer)
- **Softness**: Feathered edge softness
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.RectMask2D`

## Interaction Components

### Button
- **Transition**: None, ColorTint, SpriteSwap, Animation
- **Target Graphic**: Image to apply transition to
- **OnClick()**: UnityEvent callback
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.Button`

### Toggle
- **Is On**: Current state (bool)
- **Toggle Group**: Assign for radio-button behavior
- **Graphic**: Checkmark or indicator
- **OnValueChanged(bool)**: Callback
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.Toggle`

### Slider
- **Min Value / Max Value**: Range
- **Whole Numbers**: Snap to integers
- **Direction**: LeftToRight, RightToLeft, BottomToTop, TopToBottom
- **OnValueChanged(float)**: Callback
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.Slider`

### Scrollbar
- **Value**: 0–1
- **Size**: Handle size fraction (0–1)
- **Number Of Steps**: Snap points (0 = continuous)
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.Scrollbar`

### ScrollRect
- **Content**: RectTransform of scrollable content
- **Horizontal / Vertical**: Enable scroll axes
- **Movement Type**: Unrestricted, Elastic, Clamped
- **Inertia**: Enable momentum after drag
- **Viewport**: RectTransform with Mask/RectMask2D
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.ScrollRect`

### TMP_Dropdown
- **Options**: List of text+sprite entries
- **OnValueChanged(int)**: Callback with selected index
- **Tool**: `gameobject-component-add` → `TMPro.TMP_Dropdown`

### TMP_InputField
- **Content Type**: Standard, Autocorrected, Integer, Decimal, Alphanumeric, Name, Email, Password, Pin, Custom
- **Character Limit**: Max input length (0 = unlimited)
- **OnValueChanged(string)**: Callback per keystroke
- **OnEndEdit(string)**: Callback on submit/deselect
- **Tool**: `gameobject-component-add` → `TMPro.TMP_InputField`

## Layout Components

### HorizontalLayoutGroup
- **Padding**: Left, Right, Top, Bottom
- **Spacing**: Space between children
- **Child Alignment**: Upper/Middle/Lower × Left/Center/Right
- **Control Child Size**: Width, Height
- **Child Force Expand**: Width, Height
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.HorizontalLayoutGroup`

### VerticalLayoutGroup
- Same properties as HorizontalLayoutGroup, but vertical axis.
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.VerticalLayoutGroup`

### GridLayoutGroup
- **Cell Size**: Fixed width × height per cell
- **Spacing**: X, Y between cells
- **Start Corner**: UpperLeft, UpperRight, LowerLeft, LowerRight
- **Start Axis**: Horizontal, Vertical
- **Constraint**: Flexible, FixedColumnCount, FixedRowCount
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.GridLayoutGroup`

### LayoutElement
- **Min Width/Height**: Minimum allocation
- **Preferred Width/Height**: Ideal size
- **Flexible Width/Height**: Proportion of remaining space
- **Ignore Layout**: Exclude from parent layout calculations
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.LayoutElement`

### ContentSizeFitter
- **Horizontal Fit**: Unconstrained, MinSize, PreferredSize
- **Vertical Fit**: Unconstrained, MinSize, PreferredSize
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.ContentSizeFitter`

### AspectRatioFitter
- **Aspect Mode**: None, WidthControlsHeight, HeightControlsWidth, FitInParent, EnvelopeParent
- **Aspect Ratio**: Width / Height ratio
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.AspectRatioFitter`

## Event System Components

### EventSystem
- **First Selected**: Initially selected GameObject
- **Send Navigation Events**: Enable keyboard/gamepad navigation
- **Tool**: `gameobject-component-add` → `UnityEngine.EventSystems.EventSystem`

### StandaloneInputModule
- **Horizontal/Vertical Axis**: Input axis names
- **Submit/Cancel Button**: Input button names
- **Tool**: `gameobject-component-add` → `UnityEngine.EventSystems.StandaloneInputModule`

## Effects

### Shadow
- **Effect Color**: Shadow color
- **Effect Distance**: Offset (X, Y)
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.Shadow`

### Outline
- **Effect Color**: Outline color
- **Effect Distance**: Thickness (X, Y)
- **Tool**: `gameobject-component-add` → `UnityEngine.UI.Outline`
