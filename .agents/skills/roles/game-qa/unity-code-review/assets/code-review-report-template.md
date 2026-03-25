---
# Review Metadata (frontmatter)
# This section provides structured data for automation and indexing

metadata:
  review_date: YYYY-MM-DD
  review_version: "1.0"
  reviewer: Auto-generated
  file_path: "Assets/Game/Scripts/ClassName.cs"
  file_hash: "" # Optional: MD5 hash for change detection
  review_scope:
    dimensions:
      - SOLID principles
      - Unity 6 best practices
      - C# 9.0 language features
      - .NET Standard 2.1 API correctness
    excluded:
      - auto_generated_files: true
      - third_party_code: true
      - test_stubs: true
    partial_classes:
      reviewed: ClassName.cs
      omitted: ClassName.Debug.cs
    summary: "Brief summary of class role and overall quality"
  classification_tags:
    - "class_type: MonoBehaviour|ScriptableObject|Service|Orchestrator|Utility"
    - "complexity: low|medium|high"
    - "maintainability: needs_work|acceptable|good"
    - "performance: critical|warning|info"
---

# Code Review: [FileName.cs]

> **One-sentence summary of the class's role and overall quality**

## Executive Summary

### Finding Distribution

| Severity | Count |
|----------|-------|
| **Critical** | N     |
| **Warning**  | N     |
| **Info**     | N     |

### Quick Stats

- **Lines of code reviewed**: ~N
- **Classes reviewed**: N
- **Methods reviewed**: N
- **Review duration**: ~N minutes

---

## Findings

### Critical Findings (Blockers)

> **Critical issues that MUST be addressed before merging.** These cause bugs, memory leaks, crashes, or serious performance problems.

#### [TAG] [C-XX] Short descriptive title

**Location**: `FileName.cs:~LineNumber`

**Rule**: [SOLID/SRP] [Unity6/Performance] [C#9/Records] [NETSTANDARD]

**Why it matters**: Explain the real-world consequence in 1-2 sentences.

**Current code**:
```csharp
// Highlight the problematic code
```

**Suggested fix**:
```csharp
// Show the corrected code
```

**Impact**: [Critical/High/Medium/Low]

---

### Warning Findings (Important)

> **These violations will cause maintainability or performance issues over time.**

#### [TAG] [W-XX] Short descriptive title

**Location**: `FileName.cs:~LineNumber`

**Rule**: [SOLID/OCP] [Unity6/Lifecycle] [NETSTANDARD] [C#9]

**Why it matters**: Explain why this matters for long-term maintenance.

**Current code**:
```csharp
```

**Suggested fix**:
```csharp
```

**Impact**: [High/Medium/Low]

---

### Info Findings (Opportunities)

> **Style improvements, newer language features, or minor enhancements.**

#### [TAG] [I-XX] Short descriptive title

**Location**: `FileName.cs:~LineNumber`

**Rule**: [C#9] [NETSTANDARD] [NAMING]

**Why it matters**: Brief explanation of the improvement opportunity.

**Suggested fix**:
```csharp
```

**Impact**: [Medium/Low]

---

## What's Done Well

> **Patterns and practices worth reinforcing in other parts of the codebase.**

- List 2-4 things the code does right
  - Example: Good use of dependency injection
  - Example: Proper separation of concerns

---

## Recommendations

### High Priority

1. **Action**: [Specific task]
   - **Rule**: [SOLID/SRP] or [Unity6/Performance]
   - **Expected outcome**: [What should improve]

2. **Action**: [Specific task]
   - **Rule**: [SOLID/OCP] or [Unity6/Lifecycle]
   - **Expected outcome**: [What should improve]

### Medium Priority

3. **Action**: [Specific task]
   - **Rule**: [C#9] or [NETSTANDARD]
   - **Expected outcome**: [What should improve]

4. **Action**: [Specific task]
   - **Rule**: [NAMING] or [DI]
   - **Expected outcome**: [What should improve]

### Low Priority

5. **Action**: [Specific task]
   - **Rule**: [Style] or [Opportunity]
   - **Expected outcome**: [What should improve]

---

## Automation Data

### JSON Output (for machine processing)

```json
{
  "review_metadata": {
    "review_date": "YYYY-MM-DD",
    "review_version": "1.0",
    "file_path": "Assets/Game/Scripts/ClassName.cs",
    "file_hash": "",
    "tags": ["class_type: MonoBehaviour", "complexity: medium"]
  },
  "findings": [
    {
      "severity": "critical",
      "id": "C-01",
      "tag": "[TAG]",
      "title": "Short descriptive title",
      "location": "FileName.cs:~LineNumber",
      "rule": "[SOLID/SRP]",
      "impact": "High",
      "explanation": "Brief explanation",
      "current_code": "```csharp\n// code\n```",
      "suggested_fix": "```csharp\n// corrected code\n```"
    },
    {
      "severity": "warning",
      "id": "W-01",
      "tag": "[TAG]",
      "title": "Short descriptive title",
      "location": "FileName.cs:~LineNumber",
      "rule": "[SOLID/OCP]",
      "impact": "Medium",
      "explanation": "Brief explanation",
      "current_code": "```csharp\n// code\n```",
      "suggested_fix": "```csharp\n// corrected code\n```"
    }
  ],
  "strengths": [
    "Good use of dependency injection",
    "Proper separation of concerns"
  ],
  "recommendations": [
    {
      "priority": "high",
      "action": "Specific task",
      "rule": "[SOLID/SRP]",
      "expected_outcome": "What should improve"
    }
  ]
}
```

### Automated Tasks (for follow-up agents)

- **[TASK-01] Refactor class to follow SRP**
  - Location: FileName.cs:~LineRange
  - Rule: SOLID/SRP
  - Priority: Critical
  - Assignee: TBD
  - Due date: TBD
  - Status: Pending

- **[TASK-02] Cache GetComponent in lifecycle method**
  - Location: FileName.cs:~LineRange
  - Rule: Unity6/Performance
  - Priority: High
  - Assignee: TBD
  - Due date: TBD
  - Status: Pending

---

## Tags Reference

### SOLID Violations
- `[SRP]` - Single Responsibility Principle
- `[OCP]` - Open/Closed Principle
- `[LSP]` - Liskov Substitution Principle
- `[ISP]` - Interface Segregation Principle
- `[DIP]` - Dependency Inversion Principle

### Unity 6 Issues
- `[PERF]` - Performance problems (GC, hot paths, allocation)
- `[LIFECYCLE]` - Wrong Unity lifecycle method usage
- `[MEMORY]` - Memory leaks, missing Dispose, unsubscribed events
- `[INPUT]` - Old Input Manager instead of New Input System
- `[DI]` - Dependency injection / VContainer pattern issues
- `[ASYNC]` - Coroutine/UniTask misuse
- `[SERIALIZATION]` - Inspector/serialization issues

### Project Standards (Mandatory)
- `[ENGLISH-ONLY]` - Non-English comments or documentation
- `[UI-LOGIC-SEP]` - Logic coupled to MonoBehaviour (Should be Pure C#)
- `[POOLING]` - Missing collection pooling in hot path
- `[REACTIVE]` - UniRx misuse or missing subscription cleanup

### C# Opportunities
- `[C#9]` - C# 9.0 language feature opportunity
- `[NETSTANDARD]` - .NET Standard 2.1 API opportunity
- `[NAMING]` - Naming convention violation

---

## Notes

> Additional context, observations, or context-specific notes.
