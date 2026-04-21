---
name: test-design
description: Design test plans from acceptance criteria
tags: [qa, testing, design]

source: project
---

# Workflow: Test Design

**Goal:** Create a comprehensive test plan for a Unity mobile game feature — covering unit tests, integration tests, play mode tests, and manual QA checks.

**Prerequisites:** Story or feature spec must exist
**Input:** Story file or feature description + `.output/design/gdd.md` for acceptance criteria
**Output:** `.output/qa/test-plan-{feature}.md`

---

## Step 1 — Load Test Targets

1. If a story ID was provided (e.g., "E2-3"), load `.output/planning/stories/E2-3-*.md`
2. Otherwise, load the feature description from user input
3. Load `project-context.md` for testing conventions (NUnit, NSubstitute, PlayMode patterns)
4. Load `contributes/roles/game-engineer/skills/unity-coding/SKILL.md` references/testing.md section

Extract acceptance criteria — each AC becomes at least one test.

---

## Step 2 — Categorize Tests

For the feature, categorize all tests needed:

**Layer 1: Unit Tests (EditMode — fastest, most numerous)**
- Pure logic: business rules, calculations, state transitions
- Model classes: all methods in `{Feature}Model.cs`
- Service classes: all public methods on interfaces
- NOT suitable for: MonoBehaviour lifecycle, physics, UI rendering

**Layer 2: Integration Tests (EditMode with VContainer)**
- Controller + Model together
- Service + Repository together
- VContainer installer verification (all bindings resolve)

**Layer 3: Play Mode Tests (slower — real Unity runtime)**
- Full user flow: tap sequence → expected outcome
- Animation timing: coroutine completes within expected duration
- Scene builder: editor tool creates correct hierarchy

**Layer 4: Manual QA Checks (human verification)**
- Visual correctness: "looks right" on device
- Edge cases: orientation change, background/foreground
- Performance: smooth on target device

---

## Step 3 — Write Test Cases

For each acceptance criterion from the story:

```markdown
### Test: {AC description}

**Layer:** {Unit | Integration | PlayMode | Manual}
**Class:** `{FeatureName}Tests.cs`
**Method:** `{MethodName}_Should{ExpectedBehavior}_When{Condition}()`

**Arrange:**
- Create {Mock/Stub} for {dependency}
- Set initial state: {values}

**Act:**
- Call `{method}({parameters})`

**Assert:**
- `{actual}` should equal `{expected}`
- {side effect} should have occurred

**Unity-specific notes:** {if any — e.g., "Must run in PlayMode due to coroutine"}
```

Write test cases for ALL acceptance criteria.

---

## Step 4 — Write Test Scaffolds

Provide copy-paste ready test scaffolds:

```csharp
// File: Assets/Tests/EditMode/{Feature}Tests.cs
using NUnit.Framework;
using NSubstitute; // or use custom test doubles
using UnityEngine.TestTools;
using {Namespace}.{Feature};

[TestFixture]
public class {Feature}ModelTests
{
    private {Feature}Model _sut; // system under test
    private I{Feature}Service _mockService;
    
    [SetUp]
    public void SetUp()
    {
        _mockService = Substitute.For<I{Feature}Service>();
        _sut = new {Feature}Model(_mockService);
    }
    
    [TearDown]
    public void TearDown()
    {
        _sut?.Dispose();
    }
    
    [Test]
    public void {MethodName}_Should{ExpectedBehavior}_When{Condition}()
    {
        // Arrange
        {arrange code}
        
        // Act
        {act code}
        
        // Assert
        Assert.That({actual}, Is.EqualTo({expected}));
    }
    
    // Add all test cases here...
}
```

---

## Step 5 — Manual QA Checklist

For the feature, write a manual QA checklist:

```markdown
## Manual QA Checklist: {Feature}

**Tester:** QA role
**Build:** {version}
**Device:** {target device}

### Functional Checks
- [ ] {Check 1: specific action and expected result}
- [ ] {Check 2: specific action and expected result}

### Visual Checks
- [ ] Elements positioned correctly (no clipping, no overflow)
- [ ] Animations play smoothly (no jank, correct duration)
- [ ] Text is legible on target screen size
- [ ] Touch targets are at least 44pt

### Edge Cases
- [ ] Works after app backgrounded/foregrounded
- [ ] Works after device lock/unlock
- [ ] Works with poor network connection (if network-dependent)
- [ ] Works with low battery / thermal throttling

### Performance Checks
- [ ] No FPS drop during {key animation/effect}
- [ ] No GC spike visible in Profiler
```

---

## Step 6 — Save

1. Create `.output/qa/` if needed.
2. Save to `.output/qa/test-plan-{feature}.md`.
3. Report: "Test plan saved: {N} unit tests, {N} integration tests, {N} play mode tests, {N} manual checks."
4. Suggest: "Run `[engineer] implement story` then `[qa] test-automate` to implement these tests."
