# TextMeshPro Best Practices

Guidelines for high-quality, resolution-independent text rendering with TMPro.

## Component Selection

- **TextMeshProUGUI**: Use for all UI Canvas-based text elements.
- **TMP_Text**: Use as the serialized field type in scripts to support both UI and 3D text.

## Performance Optimization

### 1. Minimize GC Allocations
- **DO NOT** use string interpolation or `.ToString()` in `Update()`.
- **USE** `SetText()` for dynamic numeric values:
  ```csharp
  // Good: Zero-allocation for numbers
  mScoreText.SetText("Score: {0}", currentScore);
  ```

### 2. Update Only On Change
Always check if the value has changed before updating the text component:
```csharp
if (mLastScore != currentScore)
{
    mLastScore = currentScore;
    mScoreText.SetText("{0}", currentScore);
}
```

### 3. Font Assets
- **Static Fonts**: Use for standard UI elements and Western characters.
- **Dynamic Fonts**: Use for localization (CJK) and user-generated content.
- **Padding**: Use 5-9 padding for standard text, higher (12+) for heavy outlines/glow.

## Localization

- **LocalizeUIText**: Every `TextMeshProUGUI` component MUST have a `LocalizeUIText` sibling/child component to handle multi-language string resolution.
- **Rich Text**: Use `<sprite>` tags for icons inside text, following the mapping in the project constant classes.

## Styling

- **Material Presets**: Use predefined material presets for outlines, shadows, and glows instead of modifying properties directly on the component.
- **Vertical Alignment**: Set `Alignment` to `Capline` or `BaseLine` for consistent positioning across different font assets.
