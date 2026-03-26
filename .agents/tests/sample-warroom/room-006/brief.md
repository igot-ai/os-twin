# EPIC-006

App Store Submission & Compliance

**Phase:** 5
**Owner:** QA Agent (osTwin) + DevOps Agent (osTwin)
**Priority:** P0 — Gating
**Estimated Effort:** 3 days

### Description

Prepare the app for Shopify App Store submission, passing all requirements on the first review cycle. This includes performance optimization, accessibility compliance, security audit, privacy policy, and App Store listing optimization. The osTwin QA Agent runs the full compliance checklist autonomously.

### Definition of Done

- [ ] App passes all Shopify App Review requirements (documented checklist)
- [ ] App listing copy, screenshots, and demo video created
- [ ] Performance benchmarks met (LCP < 2.5s, no layout shift, < 100ms API response)
- [ ] Security audit passed (OWASP Top 10, no exposed credentials, CSP headers)
- [ ] Privacy policy and terms of service published
- [ ] "Built for Shopify" badge requirements met from day one

### Tasks

- [ ] **T-006.1** — Run osTwin QA Agent against Shopify App Review checklist:
  - App functionality works as described
  - No broken links or error states
  - Graceful handling of empty states and edge cases
  - Proper loading states and error messages
  - Responsive design across device sizes
- [ ] **T-006.2** — Performance optimization:
  - Bundle size analysis and code splitting
  - API response caching strategy
  - Database query optimization (N+1 detection, index audit)
  - CDN configuration for static assets
- [ ] **T-006.3** — Security hardening:
  - HMAC webhook validation on all endpoints
  - SQL injection prevention audit (Prisma parameterized queries)
  - XSS prevention in dynamic content rendering
  - Rate limiting on public API endpoints
  - CSP headers and HTTPS enforcement
- [ ] **T-006.4** — Accessibility compliance:
  - WCAG 2.1 AA audit on all merchant-facing UI
  - Keyboard navigation through all interactive elements
  - Screen reader compatibility with Polaris components
  - Color contrast validation
- [ ] **T-006.5** — Create App Store listing:
  - App name, tagline, and description (SEO-optimized)
  - 4-6 feature screenshots with annotations
  - 60-second demo video showing core flow
  - Pricing page with tier comparison
  - FAQ section addressing common merchant questions
- [ ] **T-006.6** — Legal compliance:
  - Privacy policy (GDPR, CCPA, PIPEDA compliant)
  - Terms of service
  - Data processing agreement template
  - Cookie consent for any tracking
- [ ] **T-006.7** — Submit via Shopify Dev Dashboard and monitor review queue
- [ ] **T-006.8** — Prepare responses for common reviewer questions:
  - Data handling and retention practices
  - AI content generation safeguards
  - Performance impact on merchant storefronts

### Acceptance Criteria

- [ ] QA Agent reports zero critical and zero high-severity issues
- [ ] Lighthouse performance score ≥ 90 on embedded admin pages
- [ ] All API endpoints respond in < 100ms at p95
- [ ] App review submitted with complete listing — no "draft" fields
- [ ] Privacy policy covers all data collection points identified in EPIC-002
- [ ] Demo video clearly shows: install → segment → personalize → measure workflow



## Working Directory
/Users/paulaan/PycharmProjects/omega-persona

## Created
2026-03-26T10:29:15Z
