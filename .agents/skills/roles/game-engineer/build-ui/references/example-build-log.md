# Example Build Log

Worked example showing a detection JSON being transformed into a sequence of MCP calls. Uses a simplified version of the level-complete popup from `unity-ui-analyzer/references/example-output.json`.

---

## Input: Detection JSON (abbreviated)

```json
{
    "schema": "5.0.0",
    "meta": {
        "source_image": "/tmp/level_complete_popup.png",
        "source_resolution": { "w": 1080, "h": 1920 },
        "to_canvas": { "scale_x": 1.0, "scale_y": 1.0 },
        "background": { "type": "dim_overlay" }
    },
    "canvas": { "w": 1080, "h": 1920, "scale_mode": "ScaleWithScreenSize", "match": 0.5 },
    "screens": [{
        "id": "screen_level_complete",
        "type": "level_complete",
        "root": {
            "id": "root",
            "rect": { "anchor": "stretch", "pivot": [0.5, 0.5], "pos": [0, 0], "size": [0, 0] },
            "components": [{ "type": "CanvasGroup", "unity_type_name": "UnityEngine.CanvasGroup", "alpha": 1.0 }],
            "children": [
                {
                    "id": "dim_overlay",
                    "rect": { "anchor": "stretch", "pivot": [0.5, 0.5], "pos": [0, 0], "size": [0, 0] },
                    "components": [{ "type": "Image", "unity_type_name": "UnityEngine.UI.Image", "sprite": null, "color": "#00000080", "raycast": true }],
                    "children": []
                },
                {
                    "id": "popup_card",
                    "rect": { "anchor": "middle_center", "pivot": [0.5, 0.5], "pos": [0, 0], "size": [900, 1100] },
                    "components": [{ "type": "Image", "unity_type_name": "UnityEngine.UI.Image", "sprite": "Assets/UI/Popup/bg_card.png", "image_type": "Sliced", "raycast": false }],
                    "children": [
                        {
                            "id": "lbl_title",
                            "rect": { "anchor": "top_center", "pivot": [0.5, 1], "pos": [0, -40], "size": [600, 90] },
                            "components": [{ "type": "TextMeshProUGUI", "unity_type_name": "TMPro.TextMeshProUGUI", "text": "LEVEL COMPLETE!", "font_size": 64, "font_style": "Bold", "alignment": "Center", "raycast": false }],
                            "children": []
                        },
                        {
                            "id": "btn_next",
                            "rect": { "anchor": "bottom_center", "pivot": [0.5, 0], "pos": [0, 120], "size": [500, 140] },
                            "components": [
                                { "type": "Image", "unity_type_name": "UnityEngine.UI.Image", "sprite": "Assets/UI/Buttons/btn_green.png", "image_type": "Sliced", "raycast": true },
                                { "type": "Button", "unity_type_name": "UnityEngine.UI.Button", "on_click": "navigate_next_level" }
                            ],
                            "children": [
                                {
                                    "id": "lbl_next",
                                    "rect": { "anchor": "stretch", "pivot": [0.5, 0.5], "pos": [0, 0], "size": [0, 0] },
                                    "components": [{ "type": "TextMeshProUGUI", "unity_type_name": "TMPro.TextMeshProUGUI", "text": "NEXT", "font_size": 48, "font_style": "Bold", "alignment": "Center", "raycast": false }],
                                    "children": []
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        "missing_assets": []
    }]
}
```

---

## Build Plan Output

```
Build Plan
----------
Screen:        screen_level_complete
Type:          level_complete
Total nodes:   5 (root, dim_overlay, popup_card, lbl_title, btn_next, lbl_next)
Missing assets: 0
Background:    dim_overlay (handled by tree node)
Prefab path:   Assets/Game/Prefabs/UI/screen_level_complete.prefab
```

---

## MCP Call Sequence

### Node 1: root

```
1. gameobject-create(name: "root")
   -> instanceID: 1001

2. gameobject-component-modify(
       target: { "instanceID": 1001 },
       component_type: "UnityEngine.RectTransform",
       properties: {
           "m_AnchorMin": { "x": 0, "y": 0 },
           "m_AnchorMax": { "x": 1, "y": 1 },
           "m_Pivot": { "x": 0.5, "y": 0.5 },
           "m_OffsetMin": { "x": 0, "y": 0 },
           "m_OffsetMax": { "x": 0, "y": 0 }
       })

3. gameobject-component-add(
       target: { "instanceID": 1001 },
       component_type: "UnityEngine.CanvasGroup")

4. gameobject-component-modify(
       target: { "instanceID": 1001 },
       component_type: "UnityEngine.CanvasGroup",
       properties: { "m_Alpha": 1.0, "m_Interactable": true, "m_BlocksRaycasts": true })
```

### Node 2: dim_overlay (child of root)

```
1. gameobject-create(name: "dim_overlay")
   -> instanceID: 1002

2. gameobject-set-parent(
       child: { "instanceID": 1002 },
       parent: { "instanceID": 1001 })

3. gameobject-component-modify(
       target: { "instanceID": 1002 },
       component_type: "UnityEngine.RectTransform",
       properties: {
           "m_AnchorMin": { "x": 0, "y": 0 },
           "m_AnchorMax": { "x": 1, "y": 1 },
           "m_Pivot": { "x": 0.5, "y": 0.5 },
           "m_OffsetMin": { "x": 0, "y": 0 },
           "m_OffsetMax": { "x": 0, "y": 0 }
       })

4. gameobject-component-add(
       target: { "instanceID": 1002 },
       component_type: "UnityEngine.UI.Image")

5. gameobject-component-modify(
       target: { "instanceID": 1002 },
       component_type: "UnityEngine.UI.Image",
       properties: {
           "m_Sprite": null,
           "m_Color": { "r": 0, "g": 0, "b": 0, "a": 0.502 },
           "m_RaycastTarget": true
       })
```

### Node 3: popup_card (child of root)

```
1. gameobject-create(name: "popup_card")
   -> instanceID: 1003

2. gameobject-set-parent(
       child: { "instanceID": 1003 },
       parent: { "instanceID": 1001 })

3. gameobject-component-modify(
       target: { "instanceID": 1003 },
       component_type: "UnityEngine.RectTransform",
       properties: {
           "m_AnchorMin": { "x": 0.5, "y": 0.5 },
           "m_AnchorMax": { "x": 0.5, "y": 0.5 },
           "m_Pivot": { "x": 0.5, "y": 0.5 },
           "m_AnchoredPosition": { "x": 0, "y": 0 },
           "m_SizeDelta": { "x": 900, "y": 1100 }
       })

4. gameobject-component-add(
       target: { "instanceID": 1003 },
       component_type: "UnityEngine.UI.Image")

5. gameobject-component-modify(
       target: { "instanceID": 1003 },
       component_type: "UnityEngine.UI.Image",
       properties: {
           "m_Sprite": { "instanceID": 0, "assetPath": "Assets/UI/Popup/bg_card.png" },
           "m_Type": 1,
           "m_RaycastTarget": false
       })
```

### Node 4: lbl_title (child of popup_card)

```
1. gameobject-create(name: "lbl_title")
   -> instanceID: 1004

2. gameobject-set-parent(
       child: { "instanceID": 1004 },
       parent: { "instanceID": 1003 })

3. gameobject-component-modify(
       target: { "instanceID": 1004 },
       component_type: "UnityEngine.RectTransform",
       properties: {
           "m_AnchorMin": { "x": 0.5, "y": 1 },
           "m_AnchorMax": { "x": 0.5, "y": 1 },
           "m_Pivot": { "x": 0.5, "y": 1 },
           "m_AnchoredPosition": { "x": 0, "y": -40 },
           "m_SizeDelta": { "x": 600, "y": 90 }
       })

4. gameobject-component-add(
       target: { "instanceID": 1004 },
       component_type: "TMPro.TextMeshProUGUI")

5. gameobject-component-modify(
       target: { "instanceID": 1004 },
       component_type: "TMPro.TextMeshProUGUI",
       properties: {
           "m_text": "LEVEL COMPLETE!",
           "m_fontSize": 64,
           "m_fontStyle": 1,
           "m_textAlignment": 514,
           "m_RaycastTarget": false
       })

6. gameobject-component-add(
       target: { "instanceID": 1004 },
       component_type: "Game.UI.LocalizeUIText")
```

### Node 5: btn_next (child of popup_card)

```
1. gameobject-create(name: "btn_next")
   -> instanceID: 1005

2. gameobject-set-parent(
       child: { "instanceID": 1005 },
       parent: { "instanceID": 1003 })

3. gameobject-component-modify(
       target: { "instanceID": 1005 },
       component_type: "UnityEngine.RectTransform",
       properties: {
           "m_AnchorMin": { "x": 0.5, "y": 0 },
           "m_AnchorMax": { "x": 0.5, "y": 0 },
           "m_Pivot": { "x": 0.5, "y": 0 },
           "m_AnchoredPosition": { "x": 0, "y": 120 },
           "m_SizeDelta": { "x": 500, "y": 140 }
       })

4. gameobject-component-add(
       target: { "instanceID": 1005 },
       component_type: "UnityEngine.UI.Image")

5. gameobject-component-modify(
       target: { "instanceID": 1005 },
       component_type: "UnityEngine.UI.Image",
       properties: {
           "m_Sprite": { "instanceID": 0, "assetPath": "Assets/UI/Buttons/btn_green.png" },
           "m_Type": 1,
           "m_RaycastTarget": true
       })

6. gameobject-component-add(
       target: { "instanceID": 1005 },
       component_type: "UnityEngine.UI.Button")
```

### Node 6: lbl_next (child of btn_next)

```
1. gameobject-create(name: "lbl_next")
   -> instanceID: 1006

2. gameobject-set-parent(
       child: { "instanceID": 1006 },
       parent: { "instanceID": 1005 })

3. gameobject-component-modify(
       target: { "instanceID": 1006 },
       component_type: "UnityEngine.RectTransform",
       properties: {
           "m_AnchorMin": { "x": 0, "y": 0 },
           "m_AnchorMax": { "x": 1, "y": 1 },
           "m_Pivot": { "x": 0.5, "y": 0.5 },
           "m_OffsetMin": { "x": 0, "y": 0 },
           "m_OffsetMax": { "x": 0, "y": 0 }
       })

4. gameobject-component-add(
       target: { "instanceID": 1006 },
       component_type: "TMPro.TextMeshProUGUI")

5. gameobject-component-modify(
       target: { "instanceID": 1006 },
       component_type: "TMPro.TextMeshProUGUI",
       properties: {
           "m_text": "NEXT",
           "m_fontSize": 48,
           "m_fontStyle": 1,
           "m_textAlignment": 514,
           "m_RaycastTarget": false
       })

6. gameobject-component-add(
       target: { "instanceID": 1006 },
       component_type: "Game.UI.LocalizeUIText")
```

---

## Post-Build: Apply Conventions

```
-- UIAnimationBehaviour (type = level_complete)
gameobject-component-add(
    target: { "instanceID": 1001 },
    component_type: "Game.UI.UIAnimationBehaviour")
```

---

## Validation Summary

```
Build Complete
--------------
GameObjects created: 6
Components added:    12
LocalizeUIText:      2 (lbl_title, lbl_next)
UIAnimationBehaviour: 1 (root -- type is level_complete)
Missing assets:      0
Console errors:      0
```
