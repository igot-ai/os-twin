# EPIC-001

Shopify App Foundation & Authentication

**Phase:** 1
**Owner:** Engineer Agent (osTwin)
**Priority:** P0 — Blocking
**Estimated Effort:** 3 days

### Description

Scaffold a production-grade Shopify app using the latest CLI template (React Router v7), implement OAuth 2.0 authentication, set up the database schema for multi-tenant merchant data, and wire up GDPR-mandatory webhooks. This is the foundation that every subsequent EPIC builds upon.

### Definition of Done

- [ ] App installs successfully on a Shopify development store
- [ ] OAuth flow completes with offline access token storage
- [ ] GDPR webhooks (customers/data_request, customers/redact, shop/redact) respond correctly
- [ ] Prisma schema migrated with merchant, customer, and session tables
- [ ] App renders embedded admin UI with Polaris Web Components
- [ ] Shopify Billing API integrated with free + 2 paid tiers
- [ ] CI/CD pipeline runs lint, type-check, and unit tests on every push

### Tasks

- [ ] **T-001.1** — Initialize app with `shopify app init` using Node.js + React Router v7 template
- [ ] **T-001.2** — Configure `shopify.app.toml` with required scopes: `read_customers`, `read_orders`, `read_products`, `write_content`, `read_analytics`
- [ ] **T-001.3** — Implement session storage with Prisma (replace default SQLite with PostgreSQL)
- [ ] **T-001.4** — Design and migrate core database schema:
  ```
  Merchant (shopDomain, accessToken, plan, installedAt)
  CustomerProfile (shopifyCustomerId, merchantId, email, segments[], lastSeen)
  EventLog (customerId, eventType, payload, timestamp)
  ContentVariant (segmentId, contentType, body, performance{})
  Segment (merchantId, name, rules[], memberCount, lastComputed)
  ```
- [ ] **T-001.5** — Implement GDPR webhook handlers with proper data deletion logic
- [ ] **T-001.6** — Set up Billing API with three tiers:
  - Free: 100 customers, 2 segments, basic personalization
  - Growth ($29/mo): 5,000 customers, unlimited segments, AI content
  - Scale ($99/mo): Unlimited customers, A/B testing, analytics, priority support
- [ ] **T-001.7** — Create embedded app shell with Polaris AppProvider, NavigationMenu, and Page components
- [ ] **T-001.8** — Write Dockerfile + docker-compose.yml for local development (app + PostgreSQL + Redis)
- [ ] **T-001.9** — Configure GitHub Actions: lint (ESLint + Prettier), type-check, Vitest unit tests

### Acceptance Criteria

- [ ] `shopify app dev` starts without errors and app loads in admin
- [ ] Fresh install on new dev store completes OAuth in < 3 seconds
- [ ] All 3 GDPR endpoints return 200 with correct payloads
- [ ] Database migrations run idempotently (`npx prisma migrate deploy`)
- [ ] Billing subscription activates/deactivates correctly on plan change
- [ ] App passes `shopify app check` with zero warnings



## Working Directory
/Users/paulaan/PycharmProjects/omega-persona

## Created
2026-03-26T10:29:15Z
