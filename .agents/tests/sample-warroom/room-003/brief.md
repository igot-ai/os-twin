# EPIC-003

AI-Powered Segmentation Engine

**Phase:** 2
**Owner:** Engineer Agent (osTwin) + Segment Builder Agent (osTwin)
**Priority:** P0 — Core Feature
**Estimated Effort:** 4 days

### Description

Build an intelligent segmentation engine that goes beyond static rule-based segments. The engine combines traditional RFM segmentation with AI-powered behavioral clustering, allowing merchants to create segments through natural language ("customers who browse but never buy electronics") and have the AI suggest high-value segments automatically.

### Definition of Done

- [ ] Merchants can create segments via rule builder UI OR natural language input
- [ ] AI suggests 5-8 auto-segments on first install based on customer data
- [ ] Segments recompute in real-time as new events arrive (< 2 second latency)
- [ ] Segment overlap visualization shows merchant how segments intersect
- [ ] Export segment to Shopify customer tags for cross-app compatibility

### Tasks

- [ ] **T-003.1** — Design segment rule schema supporting AND/OR/NOT compositions:
  ```json
  {
    "name": "High-Value Browsers",
    "logic": "AND",
    "rules": [
      { "field": "totalSpent", "op": "gte", "value": 200 },
      { "field": "lastOrderDays", "op": "gte", "value": 30 },
      { "field": "pageViewsLast30", "op": "gte", "value": 10 }
    ]
  }
  ```
- [ ] **T-003.2** — Build rule evaluation engine with Redis-cached segment membership
- [ ] **T-003.3** — Implement osTwin Segment Builder Agent:
  - Input: merchant's customer data distribution + store category
  - Output: 5-8 recommended segments with business rationale
  - Uses: clustering on RFM vectors + behavioral patterns
  - Agent prompt template with few-shot examples for Shopify verticals
- [ ] **T-003.4** — Build natural language → segment rule translator:
  ```
  "Customers who bought shoes but not accessories in the last 60 days"
  → { logic: "AND", rules: [
       { field: "purchasedCategories", op: "contains", value: "shoes" },
       { field: "purchasedCategories", op: "not_contains", value: "accessories" },
       { field: "lastOrderDays", op: "lte", value: 60 }
     ]}
  ```
- [ ] **T-003.5** — Create Polaris-based segment builder UI with:
  - Visual rule composer (drag-and-drop conditions)
  - Natural language input bar with AI icon
  - Real-time member count preview as rules change
  - Segment comparison/overlap Venn diagram
- [ ] **T-003.6** — Implement segment-to-Shopify-tag sync (write customer tags via GraphQL)
- [ ] **T-003.7** — Build segment analytics dashboard: growth over time, conversion by segment, revenue attribution
- [ ] **T-003.8** — Create predefined segment templates:
  - VIP Customers (top 10% by spend)
  - At-Risk Churners (purchased 2+ times, no activity 60+ days)
  - Window Shoppers (10+ visits, 0 purchases)
  - New Customer Nurture (first purchase in last 14 days)
  - Cart Abandoners (active cart, no checkout in 48 hours)
  - Category Champions (80%+ purchases in single category)
  - Seasonal Buyers (purchases cluster around specific months)
  - Discount Hunters (80%+ purchases used discount codes)

### Acceptance Criteria

- [ ] Natural language input "repeat buyers who spend over $100" creates valid segment with correct member count
- [ ] Auto-suggest generates segments within 10 seconds of first data sync
- [ ] Segment membership updates within 2 seconds of new qualifying event
- [ ] Rule builder handles 10+ conditions without UI lag
- [ ] Segment tags appear on customer records in Shopify Admin
- [ ] Segment analytics accurately attributes revenue to segments



## Working Directory
/Users/paulaan/PycharmProjects/omega-persona

## Created
2026-03-26T10:29:15Z
