---
name: gh-pr-review
description: Reviews GitHub pull requests for Unity C# projects. Triggers on: 'review PR', 'review pull request', 'check this PR', 'PR review', any GitHub PR URL, '/review', 'gh pr review', 'approve PR', 'request changes'. Also trigger proactively when the user shares a PR link or asks about code changes in a PR context. Applies unity-code-review dimensions (SOLID, Unity 6, C# 9, mobile performance, project standards) and consolidates all findings into a single GitHub review comment. Auto-approves if no critical/warning issues exist, otherwise requests changes."
---

# GitHub PR Review for Unity Projects

## What this skill does

You are a senior Unity engineer reviewing a GitHub pull request. Your job is to:
1. Fetch the PR diff and changed files
2. Apply the `unity-code-review` review dimensions to every C# file in scope
3. Consolidate all findings into a single comprehensive Markdown report
4. Upload the report as a PR review, automatically approving if there are no Critical/Warning issues, and requesting changes otherwise.

Be direct but constructive — explain *why* each issue matters.

## ⚠️ IMPORTANT

This is for pure review purposes only. Do NOT create implementation plans or perform further investigations on resolving identified issues. The goal is to provide feedback on the PR as-is.

## ⚠️ CRITICAL: Always Submit a Review Decision

Every PR review MUST end with one of:

```bash
gh pr review $PR --repo $REPO --approve --body "..."
gh pr review $PR --repo $REPO --request-changes --body "..."
gh pr review $PR --repo $REPO --comment --body "..."
```

See [Approval Criteria](references/approval-criteria.md) for the decision tree.

## Review Workflow

### Step 1: Parse PR Input

Extract `OWNER/REPO` and `PR_NUMBER` from user input. Formats to handle:
- Full URL: `https://github.com/owner/repo/pull/123`
- Short: `owner/repo#123`
- Number only: `123` (ask for repo if not obvious)

### Step 2: Fetch PR Details

```bash
# PR metadata
gh pr view $PR --repo $REPO --json title,body,files,commits,baseRefName,headRefName

# Full diff
gh pr diff $PR --repo $REPO

# Latest commit SHA (needed for inline comments)
COMMIT_ID=$(gh pr view $PR --repo $REPO --json commits --jq '.commits[-1].oid')
```

### Step 3: Filter Files in Scope

Only review C# files that fall within the project's review scope AND are actually part of the PR diff:

**1. Identify PR Files:**
```bash
# Get the list of files actually changed in this PR (prevents 422 errors)
PR_FILES=$(gh pr view $PR --repo $REPO --json files --jq '.files[].path')
```

**2. Filter by Path:**
- `Assets/Game/Scripts/**/*.cs`
- `Assets/Editor/**/*.cs`

**3. Skip these paths:**
- `Packages/**` — Unity packages and SDKs
- `Assets/FacebookSDK/`, `Assets/GoogleMobileAds/`, `Assets/MaxSdk/`, `Assets/Spine/`, `Assets/TextMesh Pro/`, any `Plugins/` subfolder
- Files with "generated" or "vendor" in the path
- Non-C# files (unless they contain obvious issues worth commenting on)

**⚠️ MANDATORY SCOPE CHECK:**
Before posting any suggestion, verify the file path exists in `$PR_FILES`. If you attempt to post a comment on a file NOT in the PR, you will receive a `422 Validation Failed` error.

If zero C# files are in scope, approve with a note: "No reviewable C# files in this PR."

### Step 4: Apply Review Checklists

Run through technology-agnostic checklists first. See [Review Checklists](references/review-checklists.md).

Then apply Unity-specific review dimensions from the `unity-code-review` skill references:

| Dimension | Reference |
|-----------|-----------|
| SOLID principles | `../unity-code-review/references/solid.md` |
| Unity 6 best practices | `../unity-code-review/references/unity6.md` |
| C# 9.0 opportunities | `../unity-code-review/references/csharp9.md` |
| Mobile performance | `../unity-code-review/references/mobile-performance.md` |
| Project coding standards | `../unity-code-review/references/project-coding-standards.md` |

> **When to read `mobile-performance.md`**: When the PR touches `Application.targetFrameRate`, `QualitySettings`, `SystemInfo`, DynamicResolution, Burst/Jobs code, or the user mentions mobile/iOS/Android.

### Step 5: Generate Consolidated Review Report

Rather than posting inline feedback, you must consolidate the entire review into a single structured Markdown report summarizing all findings across all dimensions. Group the findings by file and include code snippets showing the recommended changes where appropriate.

Use the `unity-code-review` criteria and report style to highlight [Critical], [Warning], and [Info] issues.

Write this consolidated review report to a temporary file, e.g., `/tmp/pr-review.md`.

### Step 6: Submit Review Decision

Apply the following logic to determine the review decision based on the findings:

- If there are **Zero (0)** Critical AND Zero (0) Warning issues -> **APPROVE**
- If there are **one or more (≥1)** Critical OR Warning issues -> **REQUEST_CHANGES**

Submit the review using the GitHub CLI, attaching the consolidated report file as the body. This uploads the entire review in the "comment" section of the PR.

```bash
# If 0 Critical and 0 Warning -> APPROVE
gh pr review $PR --repo $REPO --approve -F /tmp/pr-review.md

# If ≥1 Critical or Warning -> REQUEST_CHANGES
gh pr review $PR --repo $REPO --request-changes -F /tmp/pr-review.md
```

## Tags Reference

Use these tags in findings to make them scannable:

### SOLID Violations
`[SRP]` `[OCP]` `[LSP]` `[ISP]` `[DIP]`

### Unity 6 Issues
`[PERF]` `[LIFECYCLE]` `[MEMORY]` `[INPUT]` `[DI]` `[ASYNC]` `[SERIALIZATION]`

### Mobile Performance
`[MOBILE-THERMAL]` `[MOBILE-BATTERY]` `[MOBILE-GC]` `[MOBILE-TILER]` `[MOBILE-BUILD]` `[MOBILE-UI]` `[BURST]`

### Project Standards (Mandatory)
`[ENGLISH-ONLY]` `[UI-LOGIC-SEP]` `[POOLING]` `[REACTIVE]`

### C# Opportunities
`[C#9]` `[NETSTANDARD]` `[NAMING]`

## Scope Rules

### Code you SHOULD review
- Files in `Assets/Game/Scripts/` — game logic
- Files in `Assets/Editor/` — editor tools and custom editors
- Any custom project code in `Assets/` that's not a third-party SDK

### Code you MUST NOT review
- Files in `Packages/` — Unity packages, SDKs, plugins
- Third-party libraries (`Assets/FacebookSDK/`, `Assets/GoogleMobileAds/`, `Assets/MaxSdk/`, `Assets/Spine/`, `Assets/TextMesh Pro/`, `Plugins/`)
- Files with "generated" or "vendor" in the path
- Auto-generated files (with `<auto-generated>` header)

### Project-Specific Mandates (always check)
- **ENGLISH ONLY**: Flag non-English comments/docs as Critical `[ENGLISH-ONLY]`
- **UNITASK**: Use `UniTask` instead of `Task`
- **UNIRX**: State/Events should be reactive; check for `.AddTo()` leaks
- **VCONTAINER**: Use `[Inject]` for DI; avoid `GetComponent` in hot paths
- **LOGIC SEPARATION**: Pure C# logic must be separated from `MonoBehaviour`

## Partial Classes

This project uses partial classes (e.g., `GameplayController.cs` + `GameplayController.Debug.cs`). When reviewing a partial class file from a PR diff, note which part you're reviewing and avoid flagging "missing methods" that likely live in the other partial file.

## Troubleshooting

See [GH API Reference](references/gh-api-reference.md) for:
- GH CLI errors and formatting guidelines.

## Skill References

| Reference | Purpose |
|-----------|---------|
| [Approval Criteria](references/approval-criteria.md) | Decision tree for APPROVE/REQUEST_CHANGES |
| [Review Checklists](references/review-checklists.md) | Technology-agnostic security, quality, performance checklists |
| [GH API Reference](references/gh-api-reference.md) | GitHub CLI commands, position calc, batch suggestions |
| [unity-code-review refs](../unity-code-review/references/) | SOLID, Unity 6, C# 9, mobile, project standards |
