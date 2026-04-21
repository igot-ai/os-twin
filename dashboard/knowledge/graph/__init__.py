"""Graph RAG sub-package: Kuzu graph store, vector retriever, and prompts.

Public re-exports are deferred to :mod:`dashboard.knowledge` (the parent
package's __init__) to keep this module light. Importing
``dashboard.knowledge.graph`` does NOT pull in heavy deps like kuzu/zvec
— callers must import the concrete modules they need.
"""

__all__: list[str] = []
