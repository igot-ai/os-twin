---
name: infrastructure-as-code
description: Design and review Infrastructure as Code (IaC) templates covering resource provisioning, environment reproducibility, state management, testing strategies, and drift detection. Ensures all infrastructure is version-controlled, reviewable, and auditable.
---

# infrastructure-as-code

## Purpose

If infrastructure isn't in code, it's in someone's head — and that person is on vacation when things break. IaC ensures infrastructure is reproducible, auditable, and version-controlled.

## IaC Principles

1. **Everything in code** — no manual provisioning, no ClickOps
2. **Idempotent** — running the same code twice produces the same result
3. **Reviewable** — infrastructure changes go through code review
4. **Testable** — validate before apply
5. **Modular** — reusable modules for common patterns

## IaC Design Template

```markdown
# Infrastructure Design: [Service/Environment]

**Tool:** Terraform | Pulumi | CloudFormation
**State backend:** [where state is stored]
**Environment strategy:** [how dev/staging/prod are managed]

## Resource Inventory

| Resource | Type | Purpose | Module |
|----------|------|---------|--------|
| [name] | [type] | [why] | [module ref] |

## Module Structure

```
modules/
├── networking/     # VPC, subnets, security groups
├── compute/        # EC2, ECS, Lambda
├── storage/        # S3, RDS, DynamoDB
├── monitoring/     # CloudWatch, Datadog
└── security/       # IAM, KMS, Secrets Manager
```

## Environment Management

| Environment | Purpose | Differences from Prod |
|-------------|---------|----------------------|
| dev | Development | Smaller instances, relaxed security |
| staging | Pre-production | Prod-like, synthetic data |
| prod | Production | Full scale, real data |

## State Management
- Backend: [S3, GCS, Terraform Cloud]
- Locking: [DynamoDB, GCS, built-in]
- State isolation: [workspace, directory, account]

## Testing Strategy
- **Validate:** syntax and configuration validation
- **Plan review:** human review of planned changes
- **Policy:** automated policy checks (e.g., OPA, Sentinel)
- **Integration:** deploy to ephemeral environment and verify
```

## IaC Review Checklist

- [ ] No hardcoded secrets or credentials
- [ ] Resources are tagged (owner, environment, cost center)
- [ ] Security groups follow least-privilege
- [ ] Encryption is enabled for data at rest and in transit
- [ ] Backup and retention policies are configured
- [ ] Cost implications are documented
- [ ] Rollback procedure is clear

## Anti-Patterns

- Manual changes to managed infrastructure → causes drift; use IaC for all changes
- Monolithic IaC → split into manageable, independently deployable modules
- No state locking → concurrent applies corrupt state
- Secrets in IaC code → use secret managers, never commit secrets
- No testing → "apply and pray" is not a deployment strategy
