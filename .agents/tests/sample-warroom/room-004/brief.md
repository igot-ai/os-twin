# EPIC-004

1:1 Content Personalization Engine

**Phase:** 3
**Owner:** Content Writer Agent (osTwin) + Engineer Agent (osTwin)
**Priority:** P0 — Core Feature
**Estimated Effort:** 5 days

### Description

The crown jewel: an AI content engine that generates personalized marketing content for each customer segment — product recommendations, email copy, storefront banners, discount strategies — and serves it dynamically through Shopify's extension points. Every customer sees content tailored to their behavior, preferences, and lifecycle stage.

### Definition of Done

- [ ] osTwin Content Writer Agent generates 5+ content variants per segment
- [ ] Content renders dynamically in storefront via Theme App Extension
- [ ] Email content personalized per-recipient using segment + individual signals
- [ ] A/B testing framework measures variant performance with statistical significance
- [ ] Merchant dashboard shows content performance with revenue attribution

### Tasks

- [ ] **T-004.1** — Design content variant data model:
  ```
  ContentCampaign (merchantId, name, segments[], status, schedule)
    └── ContentVariant (campaignId, segmentId, type, body, cta, performance{})
         ├── type: "banner" | "product_rec" | "email" | "popup" | "notification"
         ├── body: { headline, subheadline, bodyText, imagePrompt, ctaText, ctaUrl }
         └── performance: { impressions, clicks, conversions, revenue }
  ```
- [ ] **T-004.2** — Implement osTwin Content Writer Agent:
  - Input: segment definition + segment behavioral profile + merchant brand voice + product catalog sample
  - Output: 3-5 content variants per segment with different angles (urgency, social proof, value, exclusivity, education)
  - Agent uses structured output format for direct rendering
  - Includes tone calibration: luxury vs. casual vs. technical vs. playful
- [ ] **T-004.3** — Build Theme App Extension (App Block) for personalized storefront content:
  - Hero banner block (personalized headline + CTA)
  - Product recommendation carousel (segment-specific)
  - Social proof block ("X people in your area bought this")
  - Exit-intent popup with personalized offer
- [ ] **T-004.4** — Create personalized email template system:
  - Liquid-compatible template with dynamic merge fields
  - Per-segment email content with individual-level product recs
  - Integration hook for Shopify Email or Klaviyo/Mailchimp via metafields
- [ ] **T-004.5** — Build A/B testing framework:
  - Random variant assignment with consistent bucketing (customer ID hash)
  - Impression/click/conversion tracking with attribution window (7 days)
  - Statistical significance calculator (chi-squared test, minimum 100 impressions)
  - Auto-promote winning variant when significance threshold reached
- [ ] **T-004.6** — Create content management UI:
  - Campaign builder wizard (select segments → generate content → preview → launch)
  - Live preview per segment showing personalized storefront experience
  - Content calendar with scheduled campaigns
  - Performance dashboard with segment × variant matrix
- [ ] **T-004.7** — Implement personalization API endpoint:
  ```
  GET /api/personalize?customerId={id}&placement={banner|rec|popup}
  → Returns: { variant, content, trackingId }
  ```
- [ ] **T-004.8** — Build product recommendation engine:
  - Collaborative filtering: "customers in your segment also bought"
  - Content-based: category affinity × product attributes
  - Trending in segment: velocity-based ranking within segment
  - Cross-sell: frequently bought together within segment

### Acceptance Criteria

- [ ] Content Writer Agent generates 5 distinct variants for "VIP Customers" segment in < 15 seconds
- [ ] Storefront App Block renders personalized banner within 200ms of page load
- [ ] A/B test correctly splits traffic 50/50 and tracks conversions
- [ ] Auto-promote triggers when variant reaches p < 0.05 significance
- [ ] Email templates render correctly in Shopify Email preview
- [ ] Product recommendations differ meaningfully between "VIP" and "New Customer" segments
- [ ] Campaign wizard completes in ≤ 5 steps from segment selection to launch



## Working Directory
/Users/paulaan/PycharmProjects/omega-persona

## Created
2026-03-26T10:29:15Z
