# Tasks for EPIC-001: Shopify App Foundation & Authentication

- [ ] T-001.1 — Initialize app with `shopify app init` using Node.js + React Router v7 template
  - AC: App initialized with `npx @shopify/cli app init --template reactRouter --path . --name omega-persona`.
- [ ] T-001.2 — Configure `shopify.app.toml` with required scopes
  - AC: Scopes `read_customers`, `read_orders`, `read_products`, `write_content`, `read_analytics` are added.
- [ ] T-001.3 — Implement session storage with Prisma (replace default SQLite with PostgreSQL)
  - AC: `prisma/schema.prisma` updated to use `postgresql` provider. Database connection string set up in `.env`.
- [ ] T-001.4 — Design and migrate core database schema: Merchant, CustomerProfile, EventLog, ContentVariant, Segment
  - AC: All tables added to Prisma schema and `npx prisma migrate deploy` runs successfully.
- [ ] T-001.5 — Implement GDPR webhook handlers with proper data deletion logic
  - AC: Endpoints `customers/data_request`, `customers/redact`, and `shop/redact` return 200 OK.
- [ ] T-001.6 — Set up Billing API with three tiers: Free, Growth, Scale
  - AC: All tiers defined and activated.
- [ ] T-001.7 — Create embedded app shell with Polaris AppProvider, NavigationMenu, and Page components
  - AC: App renders successfully in Shopify Admin with Polaris layout.
- [ ] T-001.8 — Write Dockerfile + docker-compose.yml for local development (app + PostgreSQL + Redis)
  - AC: Services start successfully with `docker-compose up`.
- [ ] T-001.9 — Configure GitHub Actions: lint (ESLint + Prettier), type-check, Vitest unit tests
  - AC: Workflows defined in `.github/workflows/ci.yml`.
