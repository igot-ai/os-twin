# Tasks for EPIC-003: AI-Powered Segmentation Engine

- [x] TASK-001 — Design and Implement Segment Rule Schema & Types
  - AC: TypeScript interfaces for `SegmentRule`, `SegmentLogic`, and `SegmentSchema` match the JSON structure in T-003.1.
  - AC: Validation logic (e.g., Zod) for the schema.
  - Files: `src/types/segmentation.ts`, `src/utils/segmentation-schema.ts`

- [x] TASK-002 — Build Rule Evaluation Engine
  - AC: Logic to evaluate `CustomerProfile` against `SegmentRules`.
  - AC: Support for AND/OR/NOT compositions.
  - AC: Integration with Redis for caching segment membership.
  - AC: Performance: Recompute for 1000 customers in < 100ms.
  - Files: `src/services/segmentation/evaluator.ts`, `src/utils/redis.ts`

- [x] TASK-003 — Implement Real-time Segment Recomputation
  - AC: Webhook/Event handler that triggers re-evaluation on new events (orders, page views).
  - AC: Latency from event to membership update < 2 seconds.
  - Files: `src/services/segmentation/service.ts`, `src/webhooks/processor.ts`

- [x] TASK-004 — Implement osTwin Segment Builder Agent (Backend)
  - AC: Agent that takes customer data/distribution and store category.
  - AC: Returns 5-8 recommended segments with logic and rationale.
  - AC: Uses behavioral clustering (RFM + category affinity).
  - Files: `src/services/ai/segment-suggestion.ts`, `src/agents/prompts/segmentation.js`

- [x] TASK-005 — Build Natural Language → Segment Rule Translator
  - AC: Integration with LLM to translate natural language to JSON segment rules.
  - AC: Handles complex queries (e.g., "repeat buyers who spend over $100").
  - Files: `src/services/ai/nl-translator.ts`, `src/api/segments.ts`

- [x] TASK-006 — Implement Segment-to-Shopify-Tag Sync
  - AC: GraphQL service to write customer tags to Shopify.
  - AC: Syncs when segment membership changes.
  - Files: `src/shopify/customerTags.js`, `src/services/segmentation/service.ts`

- [x] TASK-007 — Build Segment Analytics Dashboard Data Service
  - AC: Aggregation logic for growth, conversion, and revenue attribution per segment.
  - Files: `src/services/segmentation/analytics.ts`, `src/api/segments.ts`

- [x] TASK-008 — Create Predefined Segment Templates
  - AC: Implementation of the 8 templates listed in T-003.8.
  - Files: `src/services/segmentation/templates.ts`

- [x] TASK-009 — Develop Polaris-based Segment Builder UI
  - AC: Visual rule composer (drag-and-drop).
  - AC: Natural language input bar with AI icon.
  - AC: Real-time member count preview.
  - AC: Overlap visualization (Venn diagram).
  - Files: `src/components/SegmentBuilderUI.jsx`, `src/api/segments.ts`

- [x] TASK-010 — Integration Testing & Quality Gates
  - AC: End-to-end flow from NL input to Shopify tag sync.
  - AC: Unit test coverage ≥ 80%.
  - AC: Lint clean and no hardcoded secrets.
  - Files: `tests/integration/segmentation.test.ts`, `tests/unit/segmentation/evaluator.test.ts`

## Fixes (Post-QA Feedback)
- [x] Fix Schema Mismatch: Flattened `SegmentDefinition` to have `name`, `logic`, and `rules` as siblings.
- [x] Fix API Bug: Changed bulk recompute to use `recomputeAllSegments`.
- [x] Fix UI Integration: Updated endpoint to `/api/agents/chat` and improved keyword matching.
- [x] UI Enhancements: Added draggable rule items and CSS-based Venn diagram for overlap visualization.
- [x] Code Cleanup: Removed duplicate imports and fixed inconsistent `NOT` rule evaluation.
- [x] Test Reliability: Mocked AI services and Orchestrator in agent tests to prevent timeouts and external dependencies.

