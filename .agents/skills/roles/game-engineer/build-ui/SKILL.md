---
name: build-ui
description: Read a _detection.json (output of /detect-ui) and write a Unity C# EditorScript that builds the full UI hierarchy — GameObjects, RectTransforms, Images, TextMeshPro, Buttons, CanvasGroups, LayoutGroups — from the detected data. Run this after /detect-ui to get production-ready scene-builder code.
argument-hint: <detection_json_path> [output_cs_path]
allowed-tools: Read, Write, Glob, Grep
---

Read the detection JSON at `$ARGUMENTS` and generate a Unity C# editor script that
builds the complete UI hierarchy for that screen.

Parse `$ARGUMENTS` as:
- `$0` — path to the `*_detection.json` file (required)
- `$1` — output `.cs` path (optional; default: derive from JSON path, e.g. `RevivePopupSceneBuilder.cs`)

---

## What you must produce

A single **static C# class** placed in `Assets/Editor/` with:
- A `[MenuItem("GameObject/UI/<ScreenName> (from detection)")]` entry point
- One `Build()` method that creates every `objects[]` entry as a real Unity `GameObject`
- All helper methods at the bottom (no external dependencies beyond Unity + TMPro)
- The output is standalone — copy-paste compilable without any extra files

---

## Step 1 — Read the JSON

Use the Read tool on `$0`. Extract:
- `meta.to_canvas` → `SRC_W`, `SRC_H`, `SRC_CX`, `SRC_CY`, `scale_x` (SX), `scale_y` (SY)
- `meta.target_canvas` → `CW`, `CH`
- `meta.scene_background` → background type and asset (see Step 2a)
- `screens[0].objects[]` → sorted by `z_index` ascending
- `screens[0].screen_id` → derive class name, e.g. `RevivePopupSceneBuilder`
- `screens[0].variant_background_override` → if non-null, use instead of `meta.scene_background`

---

## Step 2a — Handle the background layer FIRST

Read `meta.scene_background` (or `screens[0].variant_background_override` if non-null).
The `type` field drives a code pattern emitted **before** all objects:

### `type: "gameplay_scene_passthrough"`
```csharp
// ── Background ─────────────────────────────────────────────────────────────
// <builder_note>
// The popup overlays the existing gameplay scene. No Background object is created.
// DimOverlay (lowest z-index object) dims whatever the gameplay scene renders.
```
→ No `Child("Background")` call. Proceed directly to Canvas creation then objects.

### `type: "full_screen_sprite"`
```csharp
// ── Background ─────────────────────────────────────────────────────────────
// <builder_note>
const string BG_PATH = "<scene_background.asset_path>";

// ... (inside Build(), after Canvas setup, before any popup objects):
var bgRT = Child("Background", root.transform);
Stretch(bgRT);
var bgImg = Img(bgRT, LoadSprite(BG_PATH));
bgImg.raycastTarget = false;
// fit_mode = "preserve_aspect"  → bgImg.preserveAspect = true;
// fit_mode = "stretch"          → bgImg.preserveAspect = false; (default)
```
→ Add `const string BG_PATH` to the constants section.
→ Create `Background` GO as the FIRST child of the Canvas root (before dim overlay).

### `type: "render_texture"`
```csharp
// ── Background ─────────────────────────────────────────────────────────────
// <builder_note>
// Background is a live RenderTexture — no file asset.
// Set canvas.renderMode = RenderMode.ScreenSpaceCamera and assign the render camera.
// No Background GameObject is created by this builder.
```
→ No `Child("Background")` call. Add a code comment only.

### `type: "none"`
```csharp
// ── Background ─────────────────────────────────────────────────────────────
// <builder_note>
// This screen fills the full display. No background layer.
```
→ No `Child("Background")` call.

---

## Step 2b — Plan the object hierarchy

After handling the background, read the `parent_id` chain for every object and resolve the
build order: parents must be created before children. Objects with `parent_id: null`
are direct children of the root Canvas.

Build a dependency-ordered list:
```
Background (if full_screen_sprite)   → Canvas root child (z: before all objects)
z:0  dim_overlay         parent: null  → Canvas root child
z:1  popup_border_red    parent: null  → Canvas root child
z:2  popup_base_cream    parent: popup_border_red
z:3  popup_content_area  parent: popup_base_cream
...
```

---

## Step 3 — Write the C# script

Follow this exact structure and code style (matches the project's existing builders):

```csharp
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEditor;
using TMPro;
// Add "using Game.UI;" only if wiring Game.UI MonoBehaviours

/// <summary>
/// Editor tool: GameObject > UI > <ScreenName> (from detection)
///
/// Auto-generated from <detection_json_filename>
/// Source: <source_resolution.width>x<source_resolution.height>
/// Canvas: <target_canvas.width>x<target_canvas.height>
///
/// Background layer : <scene_background.type> — <asset_path or "none">
///   <scene_background.builder_note>
///
/// Hierarchy:
///   <RootName>
///   ├── Background  (only when scene_background.type = "full_screen_sprite")
///   ├── <object.id>  (z:<z_index>)  — <object.name>
///   │   └── <child.id>  (z:<z_index>)
///   ...
/// </summary>
public static class <ClassName>SceneBuilder
{
    // ── Sprite folder ────────────────────────────────────────────────────────
    const string SPRITES    = "<common sprite folder prefix>";
    const string PREFAB_PATH = "Assets/Prefabs/<ScreenName>.prefab";

    // ── Background asset (only when scene_background.type = "full_screen_sprite") ─
    // const string BG_PATH = "<scene_background.asset_path>";
    // Remove this line entirely when scene_background.type is NOT "full_screen_sprite".

    // ── Source reference resolution (<meta.source_image>) ───────────────────
    const float SRC_W  = <source_resolution.width>f;
    const float SRC_H  = <source_resolution.height>f;
    const float SRC_CX = <to_canvas.origin_x>f;   // SRC_W / 2
    const float SRC_CY = <to_canvas.origin_y>f;   // SRC_H / 2

    // ── Target canvas ────────────────────────────────────────────────────────
    const float CW = <target_canvas.width>f;
    const float CH = <target_canvas.height>f;

    // ── Conversion scale factors ─────────────────────────────────────────────
    const float SX = CW / SRC_W;   // <to_canvas.scale_x>
    const float SY = CH / SRC_H;   // <to_canvas.scale_y>

    [MenuItem("GameObject/UI/<ScreenName> (from detection)", false, 13)]
    public static void Build()
    {
        // ... (see object rules below)
    }

    // ── Helpers ──────────────────────────────────────────────────────────────
    // ... (see helper section below)
}
```

---

## Step 4 — Object creation rules

For **every** object in `objects[]` apply the rules below based on its fields.
Write them in `z_index` ascending order (back → front) inside `Build()`.

---

### Rule A — Canvas root (first object, usually the screen container)

Create the Canvas + CanvasScaler + GraphicRaycaster once at the top of `Build()`:

```csharp
var root = new GameObject("<screen_id>");
Undo.RegisterCreatedObjectUndo(root, "Create <ScreenName>");

var canvas = root.AddComponent<Canvas>();
canvas.renderMode   = RenderMode.ScreenSpaceOverlay;
canvas.sortingOrder = 100;

var scaler = root.AddComponent<CanvasScaler>();
scaler.uiScaleMode         = CanvasScaler.ScaleMode.ScaleWithScreenSize;
scaler.referenceResolution = new Vector2(CW, CH);
scaler.screenMatchMode     = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
scaler.matchWidthOrHeight  = 0.5f;

root.AddComponent<GraphicRaycaster>();
```

---

### Rule B — Every object becomes a `Child()` call

```csharp
var <varName> = Child("<object.id>", <parentVar>);
```

- `<varName>` = camelCase version of `object.id` (e.g. `dimOverlay`, `popupBorderRed`)
- `<parentVar>` = the variable of the object whose `id` matches `parent_id`,
  or `root.transform` / `popupRoot` if `parent_id` is null

---

### Rule C — Positioning

**Objects with `parent_id: null`** (direct canvas children) → use `PlaceFromSource()`:
```csharp
PlaceFromSource(<varName>, <center.x>f, <center.y>f, <bounding_box.width>f, <bounding_box.height>f);
```

**Objects with a parent** → use `PlaceRelative()`:
```csharp
PlaceRelative(<varName>, <center.x>f, <center.y>f,
              <bounding_box.width>f, <bounding_box.height>f,
              <parentVarName>);
```

**Full-screen overlays** (`category:"UI/Overlay"`) → use `Stretch()` instead:
```csharp
Stretch(<varName>);
```

---

### Rule D — Image component (`type:"sprite"` or `category` contains "Container"/"Banner"/"Button"/"Badge"/"Icon")

```csharp
// Load sprite (do this at the top of Build(), not inline)
var sp<VarName> = Spr("<filename_without_extension>");   // from sprite_source path

// Add Image
var <varName>Img = Img(<varName>, sp<VarName>);

// 9-slice
if (<object.nine_slice>) <varName>Img.type = Image.Type.Sliced;

// Non-interactive icons and containers
<varName>Img.raycastTarget = <category contains "Button"> ? true : false;

// Preserve aspect for icons / non-resizable sprites
if (!<object.nine_slice>) <varName>Img.preserveAspect = true;

// Tinted color (when color.primary_hex is not white)
if (<object.color.primary_hex> != "#FFFFFF")
    <varName>Img.color = HexColor("<object.color.primary_hex>");
```

---

### Rule E — Generated solid overlay (`type:"generated"`, `category:"UI/Overlay"`)

```csharp
Img(<varName>, null, new Color(0, 0, 0, <color.opacity>f));
```

No sprite is loaded. A plain black rectangle provides the dim effect.

---

### Rule F — CanvasGroup (`canvas_group: true`)

```csharp
var <varName>CG = <varName>.gameObject.AddComponent<CanvasGroup>();
<varName>CG.alpha = <color.opacity>f;   // starting alpha from detection
```

---

### Rule G — Text (`type:"text"`, `unity_component:"TextMeshProUGUI"`)

```csharp
TMP(<varName>, "<text_content>", <font_size_approx * SY>f,
    FontStyles.<Bold|Normal|Black>,
    HexColor("<color.primary_hex>"));
```

Font size in canvas units = `font_size_approx * SY` (scales from source px to canvas).
Use `FontStyles.Bold` when `font_weight` is `"bold"` or `"black"`, else `FontStyles.Normal`.

---

### Rule H — Button (`category:"UI/Button"`, `interaction` is not `"none"`)

```csharp
var <varName>Btn = <varName>.gameObject.AddComponent<Button>();
<varName>Btn.targetGraphic = <varName>Img;
// Comment: wire onClick to <object.interaction> handler
```

---

### Rule I — HorizontalLayoutGroup (`layout_group.type:"HorizontalLayoutGroup"`)

```csharp
var <varName>HLG = <varName>.gameObject.AddComponent<HorizontalLayoutGroup>();
<varName>HLG.spacing              = <layout_group.spacing_px * SX>f;
<varName>HLG.childAlignment       = TextAnchor.MiddleCenter;
<varName>HLG.childControlWidth    = true;
<varName>HLG.childControlHeight   = true;
<varName>HLG.childForceExpandWidth  = true;
<varName>HLG.childForceExpandHeight = true;
```

Add a `// NOTE: HorizontalLayoutGroup overrides m_AnchoredPosition at runtime.` comment
immediately after — the anim builder needs to know to disable it before fly animations.

---

### Rule J — Sprite states (`sprite_states` present)

Load all state sprites at the top of `Build()`:
```csharp
var sp<VarName>Empty  = Spr("<sprite_states.empty filename>");
var sp<VarName>Filled = Spr("<sprite_states.filled filename>");
```

Assign the initial state sprite to the Image:
```csharp
<varName>Img.sprite = sp<VarName>Empty;   // initial state — empty at rest
```

Store both sprites in comments so the anim script can reference them:
```csharp
// Sprites: empty=sp<VarName>Empty  filled=sp<VarName>Filled
```

---

### Rule K — Sibling z-order

After creating all objects, set sibling indices to match `z_index`:
```csharp
// ── Enforce z-order (sibling index = z_index) ─────────────────────────────
<varName0>.SetSiblingIndex(0);
<varName1>.SetSiblingIndex(1);
// ... for every object under the same parent, in z_index order
```

---

### Rule L — fly_target objects (`category:"UI/HUD"`, `animation_role` is fly destination)

These already exist in the gameplay scene — the builder should NOT create them.
Instead, leave a comment:
```csharp
// NOTE: <object.id> ("<object.name>") is a HUD element that exists in the
// gameplay scene. It is the fly destination for <fly sources>.
// The anim script locates it at runtime via FindFirstObjectByType<GameplayHUD>()
// or by name search.
```

---

### Rule M — EventSystem (add once, at the end of Build())

```csharp
// ── Ensure EventSystem exists ─────────────────────────────────────────────
if (Object.FindFirstObjectByType<EventSystem>() == null)
{
    var es = new GameObject("EventSystem");
    es.AddComponent<EventSystem>();
    es.AddComponent<InputSystemUIInputModule>();
    Undo.RegisterCreatedObjectUndo(es, "Create EventSystem");
}
```

---

### Rule N — Save as prefab (always the last line)

```csharp
// ── Save prefab ───────────────────────────────────────────────────────────
EnsureFolder("Assets/Prefabs");
PrefabUtility.SaveAsPrefabAssetAndConnect(root, PREFAB_PATH,
    InteractionMode.UserAction);
Selection.activeGameObject = root;
Debug.Log($"[<ClassName>SceneBuilder] Created → {PREFAB_PATH}");
```

---

## Step 5 — Required helper methods

Copy these verbatim into every generated script. They are the same across all builders.

```csharp
// ── Helpers ───────────────────────────────────────────────────────────────

/// Places a canvas-root-level element from source image coordinates.
/// canvas_x = (srcCX - SRC_CX) * SX
/// canvas_y = (SRC_CY - srcCY) * SY      ← y-axis flip
static void PlaceFromSource(RectTransform rt,
    float srcCX, float srcCY, float srcW, float srcH)
{
    rt.anchorMin = new Vector2(0.5f, 0.5f);
    rt.anchorMax = new Vector2(0.5f, 0.5f);
    rt.pivot     = new Vector2(0.5f, 0.5f);
    rt.anchoredPosition = new Vector2(
        (srcCX - SRC_CX) * SX,
        (SRC_CY - srcCY) * SY);
    rt.sizeDelta = new Vector2(srcW * SX, srcH * SY);
}

/// Places a child element relative to an already-placed parent.
/// Both positions are in source-image pixel space.
static void PlaceRelative(RectTransform rt,
    float srcCX, float srcCY, float srcW, float srcH,
    RectTransform parent)
{
    rt.anchorMin = new Vector2(0.5f, 0.5f);
    rt.anchorMax = new Vector2(0.5f, 0.5f);
    rt.pivot     = new Vector2(0.5f, 0.5f);
    // Recover parent source-center from its canvas position
    float parentSrcCX = parent.anchoredPosition.x / SX + SRC_CX;
    float parentSrcCY = SRC_CY - parent.anchoredPosition.y / SY;
    rt.anchoredPosition = new Vector2(
        (srcCX - parentSrcCX) * SX,
        (parentSrcCY - srcCY) * SY);
    rt.sizeDelta = new Vector2(srcW * SX, srcH * SY);
}

/// Stretches a RectTransform to fill its parent completely.
static void Stretch(RectTransform rt)
{
    rt.anchorMin = Vector2.zero;
    rt.anchorMax = Vector2.one;
    rt.offsetMin = Vector2.zero;
    rt.offsetMax = Vector2.zero;
}

/// Creates a new child GameObject with a RectTransform on the UI layer.
static RectTransform Child(string name, Transform parent)
{
    var go = new GameObject(name, typeof(RectTransform));
    go.layer = LayerMask.NameToLayer("UI");
    go.transform.SetParent(parent, false);
    var rt = go.GetComponent<RectTransform>();
    rt.localScale = Vector3.one;
    return rt;
}
static RectTransform Child(string name, RectTransform parent)
    => Child(name, (Transform)parent);

/// Adds an Image component, optionally with a sprite and colour tint.
static Image Img(RectTransform rt, Sprite sprite, Color? color = null)
{
    var img = rt.gameObject.AddComponent<Image>();
    img.sprite = sprite;
    img.color  = color ?? Color.white;
    img.type   = Image.Type.Simple;
    return img;
}

/// Adds a TextMeshProUGUI component.
static TextMeshProUGUI TMP(RectTransform rt, string text, float size,
    FontStyles style, Color color)
{
    var t = rt.gameObject.AddComponent<TextMeshProUGUI>();
    t.text             = text;
    t.fontSize         = size;
    t.fontStyle        = style;
    t.color            = color;
    t.alignment        = TextAlignmentOptions.Center;
    t.enableAutoSizing = false;
    t.raycastTarget    = false;
    return t;
}

/// Parses a "#RRGGBB" or "#RRGGBBAA" hex string to a Unity Color.
static Color HexColor(string hex)
{
    ColorUtility.TryParseHtmlString(hex, out Color c);
    return c;
}

/// Loads a Sprite sub-asset from a PNG in the sprites folder.
static Sprite Spr(string name)
{
    string p = SPRITES + name + ".png";
    foreach (var o in AssetDatabase.LoadAllAssetsAtPath(p))
        if (o is Sprite s) return s;
    Debug.LogWarning($"[{nameof(<ClassName>SceneBuilder)}] Missing sprite: {p}");
    return null;
}

/// Creates all intermediate folders in a path.
static void EnsureFolder(string path)
{
    if (AssetDatabase.IsValidFolder(path)) return;
    var parts  = path.Split('/');
    string cur = parts[0];
    for (int i = 1; i < parts.Length; i++)
    {
        string next = $"{cur}/{parts[i]}";
        if (!AssetDatabase.IsValidFolder(next))
            AssetDatabase.CreateFolder(cur, parts[i]);
        cur = next;
    }
}
```

---

## Step 6 — Missing assets

For every entry in `missing_assets[]` add a `Debug.LogWarning` at the top of `Build()`
and a `TODO` comment at the point where the sprite would be used:

```csharp
// TODO: Missing asset '<asset_id>' — <description>
// Suggested: <suggested_size.width>x<suggested_size.height>, <suggested_color>
// Priority: <priority>
Debug.LogWarning("[<ClassName>SceneBuilder] Missing asset: <asset_id> — <description>");
```

---

## Step 7 — Validate before writing

- [ ] `meta.scene_background.type` is handled — one of the four code patterns was emitted
- [ ] When `type: "full_screen_sprite"` → `const string BG_PATH` constant exists and `Child("Background")` is the FIRST child after Canvas setup
- [ ] When `type` is NOT `"full_screen_sprite"` → no `BG_PATH` constant and no `Background` object exist
- [ ] When `screens[0].variant_background_override` is non-null → its values were used instead of `meta.scene_background`
- [ ] Class name matches the screen: `<ScreenId>SceneBuilder` (PascalCase)
- [ ] Every `object.id` in `objects[]` has a corresponding variable in `Build()`
- [ ] `PlaceFromSource` used for `parent_id: null` objects (except full-screen overlays)
- [ ] `PlaceRelative` used for all nested children
- [ ] `Stretch` used for any `category:"UI/Overlay"` that fills the screen
- [ ] `Image.Type.Sliced` set for every object where `nine_slice: true`
- [ ] `Button` component added for every `category:"UI/Button"` object
- [ ] `HorizontalLayoutGroup` added where `layout_group.type:"HorizontalLayoutGroup"`
- [ ] `CanvasGroup` added where `canvas_group: true`
- [ ] Fly-target HUD objects are **comments only** — not created as GameObjects
- [ ] All `missing_assets` have `Debug.LogWarning` entries
- [ ] `EnsureFolder` + `SaveAsPrefabAssetAndConnect` at the end
- [ ] File path is `Assets/Editor/<ClassName>SceneBuilder.cs`

---

## Output Summary (print after writing)

```
✅ Saved: Assets/Editor/<ClassName>SceneBuilder.cs

GameObjects to create : <N>  (from objects[])
Sprites loaded        : <N>  (Spr() calls)
Missing assets warned : <N>  (Debug.LogWarning)
HUD fly-targets skipped: <N> (comment-only)

Menu path: GameObject > UI > <ScreenName> (from detection)
Prefab:    Assets/Prefabs/<ScreenName>.prefab
```
