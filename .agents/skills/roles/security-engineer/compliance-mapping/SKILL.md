---
name: compliance-mapping
description: Map implementation details to compliance framework requirements (SOC2, GDPR, HIPAA, PCI-DSS, ISO 27001). Identifies gaps between current implementation and framework requirements, produces evidence documentation, and tracks remediation.
---

# compliance-mapping

## Purpose

Compliance frameworks define what security controls must exist. This skill connects the gap between "what the framework requires" and "what we've actually implemented," producing actionable mapping documents and evidence.

## Supported Frameworks

| Framework | Focus | When Required |
|-----------|-------|---------------|
| **SOC 2** | Trust service criteria (security, availability, confidentiality) | SaaS companies, enterprise customers |
| **GDPR** | EU data protection and privacy | Processing EU citizen data |
| **HIPAA** | Protected health information | Healthcare data processing |
| **PCI-DSS** | Payment card data security | Payment processing |
| **ISO 27001** | Information security management | Enterprise compliance |

## Compliance Mapping Template

```markdown
# Compliance Mapping: [Framework] — [System/Service]

**Framework version:** [version]
**Mapped by:** security-engineer
**Date:** [date]
**Overall compliance:** [X]% of controls satisfied

## Control Mapping

### [Category: e.g., Access Control]

| Control ID | Requirement | Implementation | Status | Evidence |
|-----------|-------------|---------------|--------|----------|
| [AC-1] | [what the control requires] | [how we implement it] | ✅🟡🔴 | [where evidence is] |
| [AC-2] | [what the control requires] | [how we implement it] | ✅🟡🔴 | [where evidence is] |

### Status Legend
- ✅ **Compliant** — control is fully implemented with evidence
- 🟡 **Partial** — control is partially implemented, gaps identified
- 🔴 **Non-compliant** — control is not implemented

## Gap Analysis

| Control | Gap | Risk | Remediation | Priority | Owner |
|---------|-----|------|------------|----------|-------|
| [ID] | [what's missing] | [impact] | [how to fix] | P[X] | [who] |

## Evidence Inventory

| Control | Evidence Type | Location | Last Updated |
|---------|-------------|----------|-------------|
| [ID] | [policy doc, config, screenshot, log] | [where] | [date] |

## Remediation Timeline

| Phase | Controls | Deadline | Status |
|-------|---------|----------|--------|
| 1 | [P0 controls] | [date] | In progress |
| 2 | [P1 controls] | [date] | Not started |
| 3 | [P2 controls] | [date] | Not started |
```

## Compliance Review Process

1. **Scope** — identify which framework requirements apply to this system
2. **Map** — connect each requirement to current implementation
3. **Assess** — evaluate compliance status for each control
4. **Gap** — document gaps with remediation plans
5. **Evidence** — collect and organize compliance evidence
6. **Track** — monitor remediation progress
7. **Review** — reassess quarterly or when significant changes occur

## Anti-Patterns

- Compliance as a project → compliance is continuous, not a one-time effort
- Paper compliance → documentation without implementation is fraud
- Over-scoping → not every control applies to every system; scope accurately
- Ignoring evidence management → auditors need evidence; collect it continuously, not before the audit
- Treating compliance as security → compliance is a minimum bar; it doesn't mean you're secure
