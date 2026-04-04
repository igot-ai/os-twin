# Automated Testing (NUnit)

Writing and running robust tests for the Snake Escape project.

## Test Types

1. **EditMode**: Fast, logic-only tests. Runs in background. No Unity Scene.
2. **PlayMode**: Integration tests. Requires Unity Scene. Slower.

## NUnit Pattern (AAA)

```csharp
[TestFixture]
public class GameLogicTests
{
    [Test]
    public void Score_Increases_OnAction()
    {
        // 1. Arrange
        var logic = new GameLogic();
        
        // 2. Act
        logic.AddScore(10);
        
        // 3. Assert
        Assert.AreEqual(10, logic.Score.Value);
    }
}
```

## Async Tests (UniTask)

```csharp
[UnityTest]
public IEnumerator LoadLevel_LoadsCorrectData() => UniTask.ToCoroutine(async () =>
{
    var level = await mLevelManager.GetLevel(1);
    Assert.IsNotNull(level);
});
```

## Core Rules

- **MANDATORY**: Use `EditMode` for all Pure C# logic tests.
- **MANDATORY**: Tests must have descriptive names (e.g. `WhenAction_Condition_ExpectedResult`).
- **MANDATORY**: Trigger `unity-testrunner` via CLI for CI/CD or bulk validation.
