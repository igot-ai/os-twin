# Tasks for EPIC-006 — App Store Submission & Compliance

- [ ] TASK-001 — Security Hardening: HMAC Webhook Validation & SQL Injection Audit
  - AC: All webhook endpoints verify HMAC signatures. Audit of all Prisma queries confirms no raw string concatenation (parameterized only).
- [ ] TASK-002 — Security Hardening: XSS Prevention & Rate Limiting
  - AC: React components use safe rendering. CSP headers configured in middleware. Rate limiting middleware applied to public/app-proxy routes.
- [ ] TASK-003 — Performance Optimization: Backend & Database
  - AC: API endpoints respond in < 100ms (p95). Caching strategy implemented for frequently accessed data. Database indices optimized for common queries.
- [ ] TASK-004 — Performance Optimization: Frontend Bundle & Assets
  - AC: Bundle size analysis performed. Code splitting implemented for route-based loading. Lighthouse performance score ≥ 90.
- [ ] TASK-005 — Accessibility Compliance (WCAG 2.1 AA)
  - AC: All merchant UI elements have proper ARIA labels. Keyboard navigation fully functional. Color contrast meets AA standards.
- [ ] TASK-006 — Legal & Listing Content Preparation
  - AC: Privacy policy, ToS, and DPA are updated and hosted. App Store listing text (SEO) and screenshots plan finalized.
- [ ] TASK-007 — Final Verification & QA Integration
  - AC: All sub-tasks checked. App meets "Built for Shopify" requirements. Ready for osTwin QA Agent final run.
