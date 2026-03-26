# EPIC-002

Customer Event Pipeline & Data Collection

**Phase:** 1
**Owner:** Engineer Agent (osTwin)
**Priority:** P0 — Blocking
**Estimated Effort:** 2 days

### Description

Build the real-time data collection layer that captures customer behavior across the merchant's store. This pipeline feeds the segmentation engine with the signals it needs to build intelligent customer profiles.

### Definition of Done

- [ ] Webhook subscriptions created for all required customer/order events
- [ ] Events processed, deduplicated, and stored within 500ms of receipt
- [ ] Customer profiles enriched with behavioral signals in real-time
- [ ] App extension captures storefront browsing behavior (page views, product views, cart actions)
- [ ] Data retention policy enforced (90 days rolling for free tier, 1 year for paid)

### Tasks

- [ ] **T-002.1** — Register GraphQL webhook subscriptions via `webhookSubscriptionCreate`:
  - `ORDERS_CREATE`, `ORDERS_PAID`, `ORDERS_FULFILLED`
  - `CUSTOMERS_CREATE`, `CUSTOMERS_UPDATE`
  - `CARTS_CREATE`, `CARTS_UPDATE`
  - `CHECKOUTS_CREATE`, `CHECKOUTS_UPDATE`
- [ ] **T-002.2** — Build webhook processor with HMAC validation, idempotency keys, and dead-letter queue
- [ ] **T-002.3** — Implement customer profile enrichment pipeline:
  ```
  Raw Event → Validate → Deduplicate → Enrich Profile → Update Segments → Cache
  ```
- [ ] **T-002.4** — Create Shopify Web Pixel extension for storefront behavior tracking:
  - Page views with time-on-page
  - Product detail views with scroll depth
  - Add-to-cart / Remove-from-cart events
  - Search queries
- [ ] **T-002.5** — Build computed behavioral metrics per customer:
  - Purchase frequency, AOV, total spend (RFM model)
  - Browse-to-buy ratio
  - Category affinity scores
  - Session recency and depth
- [ ] **T-002.6** — Implement data retention cron job with per-plan limits
- [ ] **T-002.7** — Create `/api/customers/:id/profile` endpoint returning full enriched profile

### Acceptance Criteria

- [ ] Placing a test order triggers webhook → profile update within 500ms
- [ ] Web Pixel captures page_view event on storefront navigation
- [ ] RFM scores computed correctly against test dataset (verify with known values)
- [ ] Data older than retention period is purged on cron run
- [ ] Profile endpoint returns enriched data with segment membership array



## Working Directory
/Users/paulaan/PycharmProjects/omega-persona

## Created
2026-03-26T10:29:15Z
