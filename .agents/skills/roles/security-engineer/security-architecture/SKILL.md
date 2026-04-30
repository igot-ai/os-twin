---
name: security-architecture
description: Review system architecture for security principles including zero-trust, least privilege, defense in depth, data encryption, network segmentation, identity management, and audit logging. Produces security architecture reviews with gap analysis and remediation priorities.
---

# security-architecture

## Purpose

Security architecture review ensures that the system is designed with security as a foundational property — not an afterthought. This review happens at the design level, before implementation begins.

## Security Architecture Principles

### 1. Zero Trust
- Never trust, always verify
- Authenticate and authorize every request
- No implicit trust based on network location
- Verify explicitly, use least privileged access, assume breach

### 2. Defense in Depth
- Multiple layers of security controls
- No single point of security failure
- If one layer fails, others still protect

### 3. Least Privilege
- Grant minimum permissions needed
- Time-bound access where possible
- Regular access reviews

### 4. Secure by Default
- Default configurations are secure
- Security features are opt-out, not opt-in
- Fail securely (deny by default)

## Security Architecture Review Template

```markdown
# Security Architecture Review: [System Name]

**Reviewer:** security-engineer
**Date:** [date]
**Verdict:** ✅ Approved | ⚠️ Conditional | 🔴 Redesign Required

## System Overview
[Architecture diagram reference, data flows, trust boundaries]

## Review Dimensions

### Identity & Access Management
- [ ] Authentication mechanism is appropriate for risk level
- [ ] Authorization is enforced at service boundary, not just UI
- [ ] Service-to-service authentication is implemented
- [ ] API keys/tokens have appropriate scopes and expiration
- [ ] Access is logged and auditable
**Score:** [1-5] | **Finding:** [summary]

### Data Protection
- [ ] Data classification is defined (public, internal, confidential, restricted)
- [ ] Encryption at rest for confidential and restricted data
- [ ] Encryption in transit (TLS 1.2+) for all data
- [ ] Key management follows best practices (not hardcoded)
- [ ] Data retention and deletion policies defined
**Score:** [1-5] | **Finding:** [summary]

### Network Security
- [ ] Network segmentation between environments
- [ ] Firewall rules follow least-privilege
- [ ] Public endpoints are minimized
- [ ] Internal services are not directly internet-accessible
- [ ] DDoS protection for public endpoints
**Score:** [1-5] | **Finding:** [summary]

### Logging & Monitoring
- [ ] Security events are logged (auth, access, changes)
- [ ] Logs are tamper-resistant and centralized
- [ ] Alerting on suspicious patterns
- [ ] Audit trail for compliance requirements
- [ ] Log retention meets compliance requirements
**Score:** [1-5] | **Finding:** [summary]

### Resilience & Recovery
- [ ] Secrets rotation is automated
- [ ] Backup and recovery procedures include security
- [ ] Incident response plan covers security incidents
- [ ] Business continuity plan exists
**Score:** [1-5] | **Finding:** [summary]

## Gap Analysis
| Gap | Severity | Remediation | Priority |
|-----|----------|------------|----------|
| [gap] | P[X] | [fix] | [timeline] |

## Verdict
[Final assessment with conditions if applicable]
```

## Anti-Patterns

- Security review only at the end → architecture changes are expensive late in development
- Treating internal networks as trusted → assume breach; internal ≠ secure
- Security through obscurity → hiding implementation details is not a security control
- Compliance-driven security → compliance is a minimum bar, not a security strategy
