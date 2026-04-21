---
name: test-automate
description: Automate test cases using Unity test frameworks
tags: [qa, testing, automation]
: core
source: project
---

# Workflow: Test Automate

**Goal:** Generate automated Unity NUnit test code for all test scenarios — writing EditMode and PlayMode tests that validate story ACs, prevent regressions, and enforce performance budgets.

**Prerequisites:** `test-design.md` must exist or user provides story/AC to test
**Input:** `.output/qa/test-design.md` + story files + existing source code
**Output:** `Assets/Tests/` — organized, runnable Unity test files

**Reference skills:** `.agents/skills/roles/qa/qa-knowledge/references/qa-automation.md` + `.agents/skills/roles/qa/qa-knowledge/references/unity-testing.md`

---

## Step 1 — Detect Engine and Test Framework

1. Load `.agents/skills/roles/qa/qa-knowledge/references/qa-automation.md`
2. Load `.agents/skills/roles/qa/qa-knowledge/references/unity-testing.md`
3. Read `ProjectSettings/ProjectVersion.txt` → confirm Unity version
4. Check `Packages/manifest.json` → confirm test packages:
   - `com.unity.test-framework` (NUnit + TestRunner)
   - `com.unity.performance.profile-analyzer` (optional)
5. Check `Assets/Tests/` for existing test patterns — respect them

Confirm: "Detected Unity {version} with NUnit. Existing tests: {list}. I'll match existing patterns."

---

## Step 2 — Analyze Target Code

For each story/system to test:

1. Read the source class (e.g., `Assets/Scripts/{Feature}/{Feature}Model.cs`)
2. Identify:
   - Public methods that need testing
   - Dependencies to mock (interfaces → use manual stubs or NSubstitute)
   - Async methods (UniTask → test with `.ToCoroutine()`)
   - Unity lifecycle (Awake/Start/Update → requires PlayMode)
3. Determine test type:
   - **EditMode** (preferred): Pure C# logic, no MonoBehaviour, fastest
   - **PlayMode**: Requires scene, MonoBehaviour lifecycle, UI interaction

---

## Step 3 — Generate Test Files

**EditMode pattern (Model/Service logic):**

```csharp
// Assets/Tests/EditMode/{Feature}ModelTests.cs
using NUnit.Framework;
using {GameNamespace}.{Feature};

[TestFixture]
public class {Feature}ModelTests
{
    private {Feature}Model _model;

    [SetUp]
    public void SetUp() => _model = new {Feature}Model();

    [TearDown]
    public void TearDown() => _model = null;

    // AC: Given {precondition}, When {action}, Then {result}
    [Test]
    public void {MethodName}_{Condition}_Returns{Expected}()
    {
        // Arrange
        {setup}

        // Act
        var result = _model.{MethodName}({args});

        // Assert
        Assert.That(result, Is.EqualTo({expected}));
    }

    [Test]
    [TestCase(0, false)]
    [TestCase(1, true)]
    public void {MethodName}_BoundaryValues(int input, bool expected)
    {
        Assert.That(_model.{MethodName}(input), Is.EqualTo(expected));
    }
}
```

**PlayMode pattern (MonoBehaviour, async, UI):**

```csharp
// Assets/Tests/PlayMode/{Feature}IntegrationTests.cs
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using Cysharp.Threading.Tasks;
using System.Collections;

[TestFixture]
public class {Feature}IntegrationTests
{
    private GameObject _testObject;

    [UnitySetUp]
    public IEnumerator SetUp()
    {
        _testObject = new GameObject("{Feature}Test");
        yield return null;
    }

    [UnityTearDown]
    public IEnumerator TearDown()
    {
        Object.Destroy(_testObject);
        yield return null;
    }

    [UnityTest]
    public IEnumerator {Feature}_WhenTriggered_CompletesWithinBudget()
    {
        var controller = _testObject.AddComponent<{Feature}Controller>();
        yield return null;

        var startTime = Time.realtimeSinceStartup;
        yield return controller.{AsyncMethod}().ToCoroutine();
        var elapsed = Time.realtimeSinceStartup - startTime;

        Assert.That(elapsed, Is.LessThan(0.1f), "Must complete within 100ms");
    }
}
```

Write all test files to disk. Create `Assets/Tests/EditMode/` and `Assets/Tests/PlayMode/` directories as needed.

---

## Step 4 — Assembly Definition Files

If test folders lack `.asmdef` files, create them:

```json
// Assets/Tests/EditMode/Tests.EditMode.asmdef
{
    "name": "Tests.EditMode",
    "references": ["UnityEngine.TestRunner", "UnityEditor.TestRunner", "{GameAssemblyName}"],
    "includePlatforms": ["Editor"],
    "overrideReferences": true,
    "precompiledReferences": ["nunit.framework.dll"],
    "autoReferenced": false,
    "defineConstraints": ["UNITY_INCLUDE_TESTS"]
}
```

---

## Step 5 — Verify Coverage

After writing tests:

1. Count TCs written vs planned in `test-design.md`
2. Verify every AC from `epics-and-stories.md` has at least one test
3. Check all P1 scenarios are automated
4. Report any gaps

---

## Step 6 — Save and Report

1. List all files created with test counts.
2. Validate no common mistakes: missing `[Test]`, missing `yield return`, wrong assembly refs.
3. Report: "{N} test files created, {N} test cases. Run via: Window > General > Test Runner."
4. Suggest: "Run `[qa] test-review` after tests pass to validate coverage quality."
