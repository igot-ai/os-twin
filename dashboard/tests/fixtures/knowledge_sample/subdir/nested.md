# Nested doc — Reactor internals

This nested document tests recursive folder walks in the Knowledge MCP
ingestion pipeline. It should be discovered alongside the top-level files.

The Reactor uses a copy-on-write subscriber list to avoid lock contention
during dispatch. Subscribers are notified in registration order.
