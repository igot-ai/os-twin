"""Graph RAG sub-package: Kuzu graph store, extractors, query engines, and parsers.

Architecture
------------
This sub-package provides two complementary graph-based processing paths:

**Core components** (``graph/core/``):

- :class:`GraphRAGExtractor` — LlamaIndex ``TransformComponent`` that wraps
  :class:`KnowledgeLLM` to extract entities + relationships from text chunks.
  Produces ``KG_NODES_KEY`` / ``KG_RELATIONS_KEY`` metadata on each node.
- :class:`GraphRAGQueryEngine` — LlamaIndex ``CustomQueryEngine`` combining
  vector retrieval with graph-based reasoning (PageRank, community summaries).
- :class:`GraphRAGStore` — Graph store adapter for LlamaIndex's
  ``PropertyGraphIndex``.
- :class:`TrackVectorRetriever` — Vector retriever with graph tracking.

**Active pipeline** (used by ``KnowledgeService``):

- ``KnowledgeService`` uses :class:`KnowledgeLLM.extract_entities` during
  ingestion (via ``ingestion.py``) and :class:`KnowledgeQueryEngine` from
  ``query.py`` for queries. Both paths integrate with the same Kuzu graph
  store (``graph/index/kuzudb.py``) and zvec vector store.
- :class:`GraphRAGExtractor` and :class:`GraphRAGQueryEngine` leverage
  LlamaIndex's graph algorithm infrastructure (PageRank, community
  detection) for advanced graph reasoning scenarios.

**Parsers** (``graph/parsers/``):

- :class:`MarkitdownReader` — Universal document reader (PDF, DOCX, MD,
  images) using Microsoft's MarkItDown. Vision/OCR is powered by the
  configured LLM provider via ``dashboard.llm_client``.

**Index** (``graph/index/``):

- :class:`KuzuLabelledPropertyGraph` — Kuzu-backed labelled property graph
  for entity/relation storage, PageRank computation, and graph queries.

Public re-exports are deferred to :mod:`dashboard.knowledge` (the parent
package's __init__) to keep this module light. Importing
``dashboard.knowledge.graph`` does NOT pull in heavy deps like kuzu/zvec
— callers must import the concrete modules they need.
"""

__all__: list[str] = []

