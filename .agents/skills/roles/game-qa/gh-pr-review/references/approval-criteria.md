# Approval Criteria

## Decision Tree

After reviewing all files in the PR, count findings by severity and apply this logic:

```
Any Critical or Warning findings?
├── YES (≥1 Critical or Warning) → REQUEST_CHANGES
│         Body: "🔴 N critical / N warning issues found. Please fix before merging."
│
└── NO (0 Critical AND 0 Warning) → APPROVE
          Body: "✅ Looks good! N info suggestions posted."
```

## Severity Classification

| Severity | Meaning | Examples |
|----------|---------|---------|
| **Critical** | Causes bugs, memory leaks, crashes, or serious performance problems | Missing `.AddTo()` on UniRx subscriptions, `GetComponent` in `Update()`, null reference in hot path |
| **Warning** | Violates important principles; causes maintainability/performance issues over time | SRP violations, missing `sealed`, `Task` instead of `UniTask` |
| **Info** | Style, newer language features, minor improvements | C# 9 pattern matching opportunity, naming conventions, target-typed `new()` |

## Edge Cases

- **All findings are Info**: APPROVE — info findings are suggestions, not blockers
- **PR has only non-C# files in scope**: APPROVE with note "No reviewable C# files"
- **Critical in third-party code**: Skip — do not flag third-party code
- **Critical in test stubs marked `// TODO`**: Downgrade to Warning (which still results in REQUEST_CHANGES)
- **Partial class missing context**: Use COMMENT if unsure; note what's missing

## Review Body Templates

These templates are used for the body of the consolidated review markdown report.

### APPROVE
```
✅ **Approved**

All findings are Info-level. All looks good overall.

**What's done well:**
- (positive pattern 1)
- (positive pattern 2)
```

### REQUEST_CHANGES
```
🔴 **Changes Requested**

Found N critical / N warning issues. Please address them before merging.

**Key blockers:**
1. (critical/warning issue summary)
2. (critical/warning issue summary)
```


