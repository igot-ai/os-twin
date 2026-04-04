# Mobile Performance Best Practices for Unity 6

A mobile-specific checklist for reviewing C# code and project configuration targeting iOS and Android.
This supplements `performance.md` (general) and `unity6.md` (Unity 6 APIs). Read all three when performing
a mobile-targeted review.

## Table of Contents
1. [Scripting & C# Hot-Path Patterns](#1-scripting--c-hot-path-patterns)
2. [Memory & GC on Mobile](#2-memory--gc-on-mobile)
3. [Burst Compiler & Job System](#3-burst-compiler--job-system)
4. [URP Mobile Settings (in-code)](#4-urp-mobile-settings-in-code)
5. [Thermal Management & Battery Awareness](#5-thermal-management--battery-awareness)
6. [Build & IL2CPP Configuration](#6-build--il2cpp-configuration)
7. [Mobile Rendering Checklist](#7-mobile-rendering-checklist)
8. [Mobile UI Pitfalls](#8-mobile-ui-pitfalls)
9. [Physics on Mobile](#9-physics-on-mobile)
10. [Mobile Audio](#10-mobile-audio)
11. [Profiling on Device](#11-profiling-on-device)
12. [Animation on Mobile](#12-animation-on-mobile)
13. [Asset Import Settings](#13-asset-import-settings)
14. [Project Configuration](#14-project-configuration)

---

## 1. Scripting & C# Hot-Path Patterns

### Update() budget
On low-end Android (e.g., Snapdragon 450), one frame at 30fps costs ~33ms. Profile on min-spec devices.
Allow ~65% of that budget for game logic; leave 35% headroom for thermal throttling.

```csharp
// BAD — per-frame distance check using Mathf.Sqrt
void Update() {
    if (Vector3.Distance(transform.position, target.position) < threshold) { ... }
}

// GOOD — use sqrMagnitude to skip the sqrt
void Update() {
    if ((transform.position - target.position).sqrMagnitude < threshold * threshold) { ... }
}
```

### Avoid per-frame string operations
String allocations trigger GC, which causes stutters visible on mobile.

```csharp
// BAD — allocates a new string every frame
void Update() {
    scoreLabel.text = "Score: " + score;
}

// GOOD — use StringBuilder or composite format with caching
private readonly System.Text.StringBuilder _sb = new(32);
void Update() {
    _sb.Clear();
    _sb.Append("Score: ").Append(score);
    scoreLabel.text = _sb.ToString();
}
```

### Animator hash caching
`Animator.StringToHash` must be called once and the result cached — never inside Update.

```csharp
// BAD — string lookup every frame
void Update() { _animator.SetBool("IsRunning", isMoving); }

// GOOD — hash cached at field level
private static readonly int IsRunningHash = Animator.StringToHash("IsRunning");
void Update() { _animator.SetBool(IsRunningHash, isMoving); }
```

### Camera.main caching
In Unity 6 `Camera.main` is no longer O(n) (it's cached internally), but it still involves a property call.
Cache it in Awake if called frequently in hot paths to be safe.

```csharp
private Camera _cam;
void Awake() => _cam = Camera.main;
```

### Avoid Coroutines for frequent, frame-accurate work
Coroutines allocate an enumerator object each time. On mobile, prefer UniTask or a simple timer field.

```csharp
// BAD — GC alloc each time
IEnumerator MoveRoutine() {
    while (true) { transform.Translate(..); yield return null; }
}

// GOOD — drive directly in Update or UniTask with Delay
```

---

## 2. Memory & GC on Mobile

Mobile GC pauses are more visible because mobile CPUs are slower and have tighter power constraints.

### Value types for small, frequently-created data
```csharp
// BAD — class allocates on heap
class HitResult { public Vector3 Point; public float Damage; }

// GOOD — struct stays on stack
struct HitResult { public Vector3 Point; public float Damage; }
```

### Reuse collections, don't recreate
```csharp
// BAD — new List every frame
void Update() {
    var hits = new List<Collider>();
    Physics.OverlapSphereNonAlloc(pos, radius, hits.ToArray()); // also wrong signature
}

// GOOD — pre-allocated array
private readonly Collider[] _hitBuffer = new Collider[16];
void Update() {
    int count = Physics.OverlapSphereNonAlloc(pos, radius, _hitBuffer);
}
```

### UnityEngine.Pool (Unity 6 built-in)
Use `ObjectPool<T>`, `ListPool<T>`, `DictionaryPool<TKey,TValue>` from `UnityEngine.Pool`
instead of `new List<T>()` for temporary collections in hot paths.

```csharp
using UnityEngine.Pool;

// Inside a method that doesn't need a persisting collection:
var list = ListPool<Transform>.Get();
try {
    // work with list
} finally {
    ListPool<Transform>.Release(list);
}
```

### Incremental GC
Enable **Edit > Project Settings > Player > Configuration > Use Incremental GC** (on by default in Unity 6).
Do NOT call `System.GC.Collect()` manually unless you're between scenes.

### WeakReference for optional callbacks
If you cache references to objects that might be destroyed (e.g., followers/observers), use `WeakReference<T>`
to avoid keeping destroyed Unity objects alive.

---

## 3. Burst Compiler & Job System

Use the Burst Compiler + C# Job System for CPU-intensive work (pathfinding, procedural generation, large physics queries).

### Basic Burst job pattern
```csharp
using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;

[BurstCompile]
struct MoveJob : IJobParallelFor {
    public NativeArray<float3> Positions;
    public float3 Direction;
    public float DeltaTime;

    public void Execute(int i) {
        Positions[i] += Direction * DeltaTime;
    }
}

// Scheduling (in MonoBehaviour)
private NativeArray<float3> _positions;
private JobHandle _moveHandle;

void Update() {
    var job = new MoveJob {
        Positions = _positions,
        Direction = moveDir,
        DeltaTime = Time.deltaTime
    };
    _moveHandle = job.Schedule(_positions.Length, 64);
}

void LateUpdate() {
    _moveHandle.Complete(); // wait for results before using them
}

void OnDestroy() {
    _moveHandle.Complete();
    _positions.Dispose();
}
```

**Rules:**
- Always `Complete()` or chain the handle before using results or calling `Dispose()`.
- Always `Dispose()` `NativeArray` and other native containers in `OnDestroy`.
- `[BurstCompile]` is most effective on tight numeric loops — don't use it for code that calls into managed C#.
- Avoid `NativeArray` allocations every frame; allocate once and reuse.

---

## 4. URP Mobile Settings (in-code)

These settings should be validated during review when the code touches rendering setup or quality management.

### Render scale
```csharp
// Lowering render scale trades resolution for significant GPU savings
// 0.75–0.85 is often imperceptible on OLED mobile screens
var data = UniversalRenderPipeline.asset;
data.renderScale = 0.8f; // set in config, not directly at runtime unless doing dynamic resolution
```

### Dynamic resolution (Unity 6 URP)
```csharp
// Trigger dynamic resolution scaling at runtime for GPU-heavy moments
// Requires Dynamic Resolution enabled in URP Asset
DynamicResolutionHandler.SetDynamicResScaler(() => targetScale, DynamicResScalePolicyType.ReturnsPercentage);
```

### HDR / MSAA
- Disable HDR for mobile unless you specifically need it for bloom/tonemapping quality.
- Prefer MSAA x2 or disabled (use FXAA post-process if needed).
- Both are set in the URP Renderer Asset — check them programmatically via `UniversalRenderPipelineAsset`.

```csharp
// Detecting and disabling MSAA at runtime for low-end devices
if (SystemInfo.graphicsMemorySize < 2048) {
    QualitySettings.antiAliasing = 0;
}
```

### Quality levels per device tier
```csharp
// BAD — single quality level for all devices
// GOOD — device-tier detection and switching
void Awake() {
    int tier = GetDeviceTier();
    QualitySettings.SetQualityLevel(tier, applyExpensiveChanges: true);
}

int GetDeviceTier() {
    // Use SystemInfo to classify
    if (SystemInfo.graphicsMemorySize >= 4096 && SystemInfo.processorFrequency >= 2500)
        return 2; // High
    if (SystemInfo.graphicsMemorySize >= 2048)
        return 1; // Medium
    return 0;     // Low
}
```

---

## 5. Thermal Management & Battery Awareness

Thermal throttling is the #1 silent killer of mobile frame rates. High-end phones (iPhone 15, Galaxy S24)
will cut CPU/GPU frequency by 30–50% within minutes of sustained load.

### Target frame rate
```csharp
// For most mobile games, 30fps is more battery-efficient and thermally safe
Application.targetFrameRate = 30;

// If you need 60fps (action/rhythm), limit post-processing and shadow resolution
// Never use -1 on mobile (burns battery, throttles within 2–3 minutes)
```

### Reduce GPU work on focus-loss
```csharp
void OnApplicationPause(bool paused) {
    if (paused) {
        Application.targetFrameRate = 10; // save battery in background
    } else {
        Application.targetFrameRate = targetFps; // restore
    }
}
```

### Reduce CPU work when the screen is off
```csharp
void OnApplicationFocus(bool hasFocus) {
    if (!hasFocus) Time.timeScale = 0; // pause all updates
    else Time.timeScale = 1;
}
```

### Screen brightness / display
```csharp
// Keep screen on during active play (user expects it for games)
Screen.sleepTimeout = SleepTimeout.NeverSleep; // set in scene init
// But restore default when going to menus/loading screens
Screen.sleepTimeout = SleepTimeout.SystemSetting;
```

### Avoid sustained 60fps when 30fps is acceptable
Review all scenes: does the game objectively require 60fps (rhythm, fighting) or is 30fps fine (puzzle, RPG)?
Unnecessary frame rate wastes battery and causes thermal throttling that makes the experience worse overall.

---

## 6. Build & IL2CPP Configuration

These are project-level settings, but reviewers should flag code patterns that conflict with them.

### Use IL2CPP (not Mono) for release
IL2CPP produces native code: typically 15–30% faster than Mono JIT on mobile CPUs.
- In **Player Settings > Other Settings > Scripting Backend**, select **IL2CPP**.
- Enable **Managed Stripping Level: High** to remove unused code (validate with the linker XML if needed).

### Code that breaks IL2CPP stripping
```csharp
// BAD — reflection without preservation attribute (gets stripped)
Type t = Type.GetType("MyNamespace.MyClass");
Activator.CreateInstance(t);

// GOOD — preserve via attribute or link.xml
[Preserve]
public class MyClass { }
```

### ARM64 only (2024+)
Google Play requires 64-bit (ARM64) support. iOS devices are all ARM64. Remove ARMv7 builds unless
you must support very old Android devices (pre-2016). This also reduces install size.

### .NET Standard 2.1 (not .NET Framework)
Set in **Player Settings > Other Settings > Api Compatibility Level**. .NET Standard is more portable,
has better tree-shaking, and avoids including large portions of System.dll.

### Strip Engine Code
Enable in **Player Settings > Publishing Settings (iOS) / Build (Android)**. Removes unused Unity engine
subsystems. Requires confirming nothing uses stripped systems at runtime.

### Shader compilation / PSO caching (Unity 6)
```csharp
// Unity 6 introduces Pipeline State Object (PSO) caching
// Use ShaderVariantCollection to pre-warm shaders at load time,
// avoiding hitches when new shader/material combos appear first
// Flag: any code that creates new Materials at runtime in hot paths
// is a candidate for PSO hitch investigation
```

---

## 7. Mobile Rendering Checklist

Check these when reviewing code that creates or configures renderers, cameras, or materials.

| Concern | Mobile Best Practice |
|---------|---------------------|
| Shadows | Disable real-time shadows on low-end. Use `LightShadows.None` or a fake blob shadow. |
| Transparency | Minimize alpha-blended objects. Use alpha-cutoff shaders where possible. |
| Overdraw | Use Unity's Rendering Debugger (Overdraw mode) in-editor and flag excessive layering. |
| Draw calls | Target <150 draw calls/frame for low-end mobile. SRP Batcher reduces GPU setup cost. |
| Texture compression | ASTC 6×6 or 8×8 for Android 2016+. PVRTC only for legacy iOS (A7 or older). |
| Render textures | Avoid `new RenderTexture(...)` at runtime. Pool or pre-create at startup. |
| Camera.clearFlags | Use `Depth` or `Skybox` only where needed. `SolidColor` is cheapest. |
| Post-processing | Each pass costs GPU time. On mobile: Bloom + Color Grading only; skip AO, SSR. |
| Shader features | Review `#pragma multi_compile` directives — each variant adds compile time and memory. |
| GPU Resident Drawer | Enable in URP Asset for Forward+ path to reduce CPU overhead via GPU-driven rendering. |

### Overdraw flag pattern
```csharp
// Flag: multiple CanvasGroup alphAnim stacked => overdraw
// Flag: particles with Transparent blend mode in large quantities
// Flag: SkinnedMeshRenderer with transparent materials on large character areas
```

---

## 8. Mobile UI Pitfalls

UI is often the biggest mobile perf offender because it's CPU-side (Canvas rebuilds) and GPU-side (overdraw).

### Canvas splitting
```csharp
// BAD — one Canvas for everything; one dirty element triggers full rebuild
// GOOD — separate Canvas for static HUD and dynamic score/timer

// Every time a UI element changes, split its Canvas:
// - StaticHUDCanvas (health bar background, map frame) — rarely redrawn
// - DynamicHUDCanvas (score counter, timer, combo text) — redrawn often
// - PopupCanvas — fullscreen overlays, dialog boxes
```

### Disable raycasts on non-interactive elements
```csharp
// BAD — all Image/Text components have Raycast Target ON (Unity default)
// GOOD — disable on anything decorative
// In code, detect via:
if (graphic.raycastTarget && !isInteractable) {
    Debug.LogWarning($"{graphic.name} has unnecessary raycastTarget — disable it.");
}
```

### Avoid Layout Groups in hot paths
`HorizontalLayoutGroup`, `VerticalLayoutGroup`, `GridLayoutGroup` trigger expensive `LayoutRebuilder.ForceRebuildLayoutImmediate`
on every child change. For dynamic lists: use a pooled scroll view or fixed anchors.

### RectTransform.anchoredPosition vs position
Setting `.position` (world space) triggers more work than `.anchoredPosition` (local). In hot paths:
```csharp
// GOOD — use anchoredPosition for UI elements
_rect.anchoredPosition = new Vector2(x, y);
```

### Text Mesh Pro vs UGUI Text
Always use TextMeshPro (`TMP_Text`). UGUI legacy `Text` is deprecated in Unity 6 and generates more draw calls with worse performance.

---

## 9. Physics on Mobile

### 2D vs 3D physics
If your game is 2D, use `Physics2D` exclusively. Mixing 3D physics bodies into a 2D game wastes CPU.

### FixedUpdate frequency
Default `Fixed Timestep` is 0.02s (50Hz). On low-end mobile at 30fps, this means multiple physics steps per frame.
Set to `0.0333s` (30Hz) for 30fps mobile games to match visual update rate.

```csharp
// Consider setting in project settings or via code at startup:
Time.fixedDeltaTime = 1f / Application.targetFrameRate;
```

### Simplify colliders
```
Complex mesh colliders → Replace with 2–3 primitive colliders (box, sphere, capsule)
Convex hull mesh colliders → Acceptable but profile on device
Concave mesh colliders → NEVER on mobile for dynamic rigidbodies (CPU intensive)
```

### Physics layers
Use a minimal `Layer Collision Matrix` — uncheck all layer pairs that never interact.
This is set in Project Settings but reviewers should flag code that doesn't use layer masks:

```csharp
// BAD — Physics query hits everything
Physics2D.Raycast(origin, dir);

// GOOD — layer mask filters candidates efficiently
Physics2D.Raycast(origin, dir, distance, _enemyLayerMask);
```

---

## 10. Mobile Audio

### Load types
| Clip type | Load type | Compression |
|-----------|-----------|-------------|
| Short SFX (< 200ms) | Decompress on Load | ADPCM |
| Medium SFX (< 10s) | Compressed in Memory | Vorbis Q50 |
| Music / ambience | Streaming | Vorbis Q40–60 |

### Sample rate
```
Mobile target: 22,050 Hz for all SFX
Music: 44,100 Hz maximum (use 22,050 if acceptable quality)
```

### Force Mono
Enable **Force To Mono** for all SFX that don't need stereo panning. Halves memory footprint.
3D positioned AudioSources always sound mono anyway due to spatialization.

### AudioMixer groups
Do not set `AudioSource.volume` directly every frame — drive it through AudioMixer parameters with
a single `SetFloat` call.

---

## 11. Profiling on Device

These patterns should be called out when reviewing profiling-related code.

### Development build markers
```csharp
using Unity.Profiling;

// Use ProfilerMarker for custom profiler sections (zero overhead in release builds)
private static readonly ProfilerMarker s_pathUpdateMarker = new("PathUpdate");

void Update() {
    using (s_pathUpdateMarker.Auto()) {
        UpdatePath();
    }
}
```

### Log stripping
```csharp
// BAD — Debug.Log in production code
Debug.Log("Player moved to " + position);

// GOOD — stripped from release via conditional or wrapped logger
[System.Diagnostics.Conditional("UNITY_EDITOR")]
static void Log(string msg) => Debug.Log(msg);
```

### Memory Profiler snapshots
Remind reviewers: take a Memory Profiler snapshot on the actual device after 5+ minutes of play
to catch slow memory leaks not visible in short sessions.

### Frame pacing (Android)
On Android, use `Application.targetFrameRate` and consider enabling **Android Frame Pacing**
in Player Settings to smooth out frame delivery jitter (prevents micro-stutters even when avg fps is on target).

---

## 12. Animation on Mobile

Animation is a common hidden CPU cost on mobile — easy to forget because it works fine in the editor.

### Generic vs Humanoid rigs
```
Generic rig   → ~30% less CPU than Humanoid; use whenever the character doesn't need IK or retargeting
Humanoid rig  → Only when you need mecanim retargeting or IK pass
```
Flag any humanoid rig on a non-player character (enemy, crowd, decoration) — those almost always should be Generic.

### Animator Culling Mode
```csharp
// BAD — default; animates even when off-screen
_animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;

// GOOD — skip animation updates when renderer isn't visible
_animator.cullingMode = AnimatorCullingMode.CullUpdateTransforms;
// or CullCompletely to stop the state machine too (for background characters)
_animator.cullingMode = AnimatorCullingMode.CullCompletely;
```
Also ensure `SkinnedMeshRenderer.updateWhenOffscreen` is **disabled** for characters not in view.

### Avoid Scale Curves
Scale animation curves are significantly more expensive than position/rotation curves on mobile.
Flag any animation clip that animates scale when the visual result could be achieved by other means.

### Use hashes for Animator parameters (see also Section 1)
All `SetFloat`, `SetBool`, `SetTrigger`, `GetFloat` calls must use pre-computed `Animator.StringToHash` values.
Do the hash computation at class-level as `static readonly int`, not inside Update.

### Prefer tweening over Animator for simple UI animations
Using `Animator` for fade-in/fade-out or simple UI movement creates unnecessary state machine overhead.
Use DOTween or UniTask-based coroutine tweens instead:
```csharp
// BAD — Animator driving a 2-state pop-in animation
_animator.SetTrigger("PopIn");

// GOOD — lightweight tween
await transform.DOScale(Vector3.one, 0.2f).SetEase(Ease.OutBack).ToUniTask(cancellationToken: ct);
```

---

## 13. Asset Import Settings

These can't be caught purely in C# review, but flag code that reads mismatched asset types or creates runtime assets.

### Textures
| Setting | Mobile Best Practice |
|---------|---------------------|
| Max Size | Minimum acceptable for the visual role (e.g., 512 for icons, 1024 for character sheets) |
| Compression | ASTC 6×6 or 8×8 (Android 2016+ and iOS A8+). ETC2 for older Android. |
| Read/Write Enabled | **Disable** unless you need `Texture2D.GetPixels()` at runtime — doubles memory |
| Generate Mipmaps | Enable for world-space textures. **Disable** for UI textures at fixed screen size |
| Power of Two | Use POT dimensions (512, 1024, 2048) for hardware compression compatibility |
| Texture Atlasing | Group small sprites into atlases to reduce draw calls |

In code, flag:
```csharp
// BAD — loading a large texture directly, no pooling
var tex = Resources.Load<Texture2D>("HeroPortrait_4K");

// GOOD — use Addressables for lazy loading of large assets
var handle = Addressables.LoadAssetAsync<Texture2D>("HeroPortrait");
```

### Meshes
| Setting | Mobile Best Practice |
|---------|---------------------|
| Mesh Compression | High or Medium — reduces package size |
| Read/Write Enabled | **Disable** unless modifying mesh at runtime — doubles memory |
| Optimize Mesh | Enable (reorders vertices for GPU cache efficiency) |
| Normals / Tangents | Disable if the shader doesn't need them (e.g., unlit or vertex-color shaders) |
| Rig / Blend Shapes | Disable if not used |

### Addressables vs Resources
- `Resources.Load()` loads synchronously and keeps assets in memory. Use only for truly tiny, always-needed assets.
- `Addressables.LoadAssetAsync()` supports lazy loading, async, and explicit `Release()`. Prefer it for any asset > ~100 KB.

---

## 14. Project Configuration

Settings that are often missed and are particularly impactful on mobile. Flag these in code that touches project/quality config.

### Accelerometer frequency
```csharp
// If the game doesn't use accelerometer input, disable it entirely:
// Player Settings > Other Settings > Accelerometer Frequency = Disabled
// In code, check if anyone reads Input.acceleration without enabling it intentionally
if (Input.acceleration != Vector3.zero) {
    // Is accelerometer actually used? If not, flag for disabling in Player Settings
}
```

### Transform.SetPositionAndRotation
Setting `position` and `rotation` separately triggers two transform change propagations.
Use the combined API to cut that in half:
```csharp
// BAD — two transform dirty notifications
transform.position = newPos;
transform.rotation = newRot;

// GOOD — one combined call
transform.SetPositionAndRotation(newPos, newRot);
```

### Avoid deep hierarchies
Transform hierarchies cost CPU proportionally to depth — every parent dirty-marks all children.
Flatter is faster. Flag GameObjects with more than 5–6 levels of nesting unless structurally required.
```csharp
// Flag: deeply nested GameObject created at runtime
var go = new GameObject("Bullet");
go.transform.SetParent(pool.transform); // avoid if pool has deep hierarchy already
```

### Disable physics auto-sync if not needed
```csharp
// If your game doesn't use physics (or uses manual steps):
Physics.autoSimulation = false;    // 3D
Physics2D.simulationMode = SimulationMode2D.Script; // 2D
// Call Physics.Simulate() / Physics2D.Simulate() manually each frame
```

### Target frame rate and vsync alignment
```csharp
// Set early in application startup — changing mid-game can cause frame time jitter
void Awake() {
    Application.targetFrameRate = 30; // or 60 for action games
    QualitySettings.vSyncCount = 0;   // 0 = let targetFrameRate control pacing on mobile
}
```

---

## Review Tags (Mobile Extensions)

These extend the base tag set in SKILL.md. Use them for mobile-specific findings:

- `[MOBILE-THERMAL]` — Code likely to cause thermal throttling (sustained high CPU/GPU without back-off)
- `[MOBILE-BATTERY]` — Unnecessary power consumption (targetFrameRate=-1, no pause handling)
- `[MOBILE-GC]` — Allocation in hot path that will cause visible GC stutter on mobile
- `[MOBILE-TILER]` — Issue specific to mobile tile-based GPU architecture (overdraw, RT reads, etc.)
- `[MOBILE-BUILD]` — Build setting misconfiguration (IL2CPP, stripping, ARMv7/ARM64, compression)
- `[MOBILE-UI]` — Canvas/layout rebuild or raycast overhead issue
- `[BURST]` — Opportunity to use Burst Compiler / Job System for CPU-intensive work
