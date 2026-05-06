---
name: developer-experience
description: Audit and improve the inner-loop developer experience including build times, test feedback cycles, local development setup, tooling quality, and documentation completeness. Produces DX scorecards with prioritized improvement plans.
---

# developer-experience

## Purpose

Developer experience (DX) is the single largest multiplier in an engineering organization. Every minute saved in the inner loop multiplies across every engineer, every day. This skill measures and improves DX systematically.

## DX Metrics

| Metric | Definition | Target | How to Measure |
|--------|-----------|--------|----------------|
| Time to first commit | New hire → first meaningful PR | < 1 day | Onboarding tracking |
| Build time | Local build from clean state | < 2 min | CI metrics |
| Test time | Full local test suite | < 5 min | CI metrics |
| Deploy time | Code merged → running in staging | < 15 min | Pipeline metrics |
| Feedback time | Code change → test result | < 30 sec (unit) | Local tooling |
| Setup time | Clone → running locally | < 15 min | Manual test |

## DX Audit Template

```markdown
# Developer Experience Audit — [Team/Service]

**Date:** [date]
**Auditor:** platform-engineer

## Scorecard

| Dimension | Score (1-5) | Notes |
|-----------|-------------|-------|
| Local setup | X | [ease of getting started] |
| Build speed | X | [time and reliability] |
| Test feedback | X | [speed and clarity] |
| Documentation | X | [completeness and accuracy] |
| Tooling | X | [IDE support, CLI tools] |
| Debugging | X | [ease of diagnosing issues] |
| **Overall DX** | **X.X** | |

## Pain Points (from developer feedback)
1. [Pain point 1 — frequency and impact]
2. [Pain point 2 — frequency and impact]

## Improvement Plan

| Priority | Improvement | Impact | Effort | Owner | Timeline |
|----------|-----------|--------|--------|-------|----------|
| P0 | [improvement] | High | Low | [who] | [when] |
| P1 | [improvement] | High | Medium | [who] | [when] |
| P2 | [improvement] | Medium | Medium | [who] | [when] |

## Quick Wins (< 1 day effort)
1. [Quick win 1]
2. [Quick win 2]
```

## DX Improvement Categories

### 1. Inner Loop Speed
- Hot reload / fast refresh
- Incremental compilation
- Test watch mode
- Local dependency caching

### 2. Onboarding
- One-command local setup
- Seed data for development
- Example configurations
- Contributor guidelines

### 3. Documentation
- Architecture decision records
- API documentation (auto-generated where possible)
- Troubleshooting guides
- FAQ from common support questions

### 4. Tooling
- IDE extensions and configurations
- CLI tools for common tasks
- Code generators / scaffolding
- Environment management

## Anti-Patterns

- Measuring DX without acting on it → surveys without follow-through erode trust
- Optimizing for the wrong thing → ask developers what hurts, don't assume
- One-size-fits-all → different teams may have different DX needs
- Ignoring onboarding → if new engineers struggle, your DX has a problem
