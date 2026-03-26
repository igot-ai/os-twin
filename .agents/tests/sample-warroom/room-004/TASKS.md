# Tasks for EPIC-004: 1:1 Content Personalization Engine

- [x] TASK-001 — Design and Implement Content Personalization Data Model
    - AC: Prisma schema supports `ContentCampaign` and `ContentVariant` with all required fields (merchantId, segments, schedule, type, body, performance).
    - AC: Database migrations applied.
    - AC: Basic CRUD services for campaigns and variants implemented.

- [x] TASK-002 — Implement osTwin Content Writer Agent
    - AC: Agent generates 3-5 content variants per segment with different angles (urgency, social proof, etc.).
    - AC: Supports tone calibration (luxury, casual, technical, playful).
    - AC: Outputs structured JSON for direct rendering in storefront and email.
    - AC: Integrated with `ContentWriterService` using LLM.

- [x] TASK-003 — Implement Personalization API Endpoint
    - AC: `GET /api/personalize` returns `{ variant, content, trackingId }` based on `customerId` and `placement`.
    - AC: Implements consistent bucketing for A/B testing using customer ID hash.
    - AC: Integrated with Redis for low-latency response (< 200ms).

- [x] TASK-004 — Build Hybrid Product Recommendation Engine
    - AC: Implements Collaborative filtering (segment-based), Content-based (category affinity), and Trending in segment.
    - AC: Implements Cross-sell logic (frequently bought together within segment).
    - AC: Recommendations differ meaningfully between segments.

- [x] TASK-005 — Build A/B Testing Framework
    - AC: Tracks impressions, clicks, and conversions with 7-day attribution window.
    - AC: Statistical significance calculator (chi-squared test) implemented.
    - AC: Auto-promote winning variant when p < 0.05 and minimum 100 impressions reached.

- [x] TASK-006 — Build Theme App Extension (App Blocks)
    - AC: Hero banner block with personalized headline/CTA.
    - AC: Product recommendation carousel (segment-specific).
    - AC: Social proof block ("X people in your area bought this").
    - AC: Exit-intent popup with personalized offer.

- [x] TASK-007 — Create Personalized Email Template System
    - AC: Liquid-compatible template with dynamic merge fields.
    - AC: Integration hook for Shopify Email/Klaviyo via metafields.
    - AC: Per-segment email content with individual-level product recs.

- [x] TASK-008 — Create Content Management UI
    - AC: Campaign builder wizard (select segments → generate content → preview → launch).
    - AC: Live preview per segment for storefront experience.
    - AC: Performance dashboard with revenue attribution and segment × variant matrix.
