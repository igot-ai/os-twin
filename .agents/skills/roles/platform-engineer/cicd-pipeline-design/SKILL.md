---
name: cicd-pipeline-design
description: Design and optimize CI/CD pipelines for speed, reliability, and security. Covers pipeline architecture, stage design, caching strategies, parallelization, security scanning integration, and failure diagnosis.
---

# cicd-pipeline-design

## Purpose

CI/CD pipelines are the factory floor of software delivery. A slow, flaky pipeline is a tax on every engineer in the organization. This skill produces pipeline designs that are fast, reliable, and secure.

## Pipeline Design Targets

| Metric | Target | Why |
|--------|--------|-----|
| Unit test stage | < 5 min | Fast feedback loop |
| Full pipeline | < 15 min | Engineers shouldn't context-switch while waiting |
| False failure rate | < 1% | Flaky pipelines erode trust |
| Security scan | Integrated | Shift-left security |
| Deploy to staging | < 5 min | Fast validation |

## Pipeline Architecture Template

```markdown
# Pipeline Design: [Service/Repo Name]

## Stages

### 1. Build
- **Time target:** < 2 min
- **Caching:** [dependency cache, build cache]
- **Artifacts:** [what gets produced]

### 2. Unit Tests
- **Time target:** < 5 min
- **Parallelization:** [split strategy]
- **Coverage threshold:** [minimum %]

### 3. Static Analysis
- **Linting:** [tools]
- **Type checking:** [tools]
- **Security scan:** [SAST tool]

### 4. Integration Tests
- **Time target:** < 10 min
- **Environment:** [how test environment is provisioned]
- **Data:** [test data strategy]

### 5. Security Scan
- **Dependency audit:** [CVE scanning]
- **Container scan:** [if applicable]
- **License compliance:** [if applicable]

### 6. Deploy to Staging
- **Method:** [blue-green, canary, rolling]
- **Smoke tests:** [what runs post-deploy]

### 7. Deploy to Production
- **Trigger:** [manual approval, auto on merge, scheduled]
- **Rollback:** [how to revert]
- **Monitoring:** [what to watch post-deploy]
```

## Optimization Strategies

1. **Caching** — cache dependencies, build artifacts, Docker layers
2. **Parallelization** — run independent stages concurrently
3. **Test splitting** — distribute tests across multiple workers
4. **Incremental builds** — only rebuild what changed
5. **Fast feedback first** — run fastest checks earliest

## Anti-Patterns

- Serial stages that could be parallel → wastes time
- No caching → rebuilding everything from scratch every time
- Flaky tests in the pipeline → either fix them or quarantine them
- No security scanning → vulnerabilities should be caught before merge, not in production
- Manual deployment with no audit trail → deployments must be automated and logged
