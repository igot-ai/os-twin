"""Graph store wrapper around :class:`KuzuLabelledPropertyGraph`.

Refactor notes (EPIC-001):
- Removed ``pyvis`` dependency (was used by ``to_json_graph`` for HTML viz).
  The method still returns ``{nodes, edges}`` but built directly from networkx.
- ``networkx`` is imported lazily inside ``to_json_graph``.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from llama_index.core.graph_stores import LabelledNode, SimplePropertyGraphStore
from llama_index.core.graph_stores.types import Triplet

from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

logger = logging.getLogger(__name__)


class GraphRAGStore(SimplePropertyGraphStore):
    """Property graph store with PageRank + community helpers."""

    community_summary: dict = {}
    max_cluster_size: int = 5
    entity_info: dict = {}
    language: str = "English"
    include_graph: bool = True

    def __init__(self, graph: KuzuLabelledPropertyGraph) -> None:
        super().__init__(graph=graph)
        self.graph = graph

    def to_json_graph(self) -> dict:
        """Return ``{nodes, edges}`` snapshot of the entity sub-graph."""
        import networkx as nx  # noqa: WPS433 — lazy import

        directed = nx.DiGraph()
        seen: set[str] = set()
        for node in self.graph.get_all_nodes(label_type="entity"):
            if node.id not in seen:
                directed.add_node(node.id, label=node.id, properties=node.properties)
                seen.add(node.id)
        for triplet in self.graph.get_triplets():
            directed.add_edge(triplet[0].id, triplet[2].label, label=triplet[1].id)

        nodes = [
            {"id": n, "label": data.get("label", n), "properties": data.get("properties", {})}
            for n, data in directed.nodes(data=True)
        ]
        edges = [
            {"source": s, "target": t, "label": data.get("label", "")}
            for s, t, data in directed.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    def pagerank(self, personalize: dict, **kwargs):
        return self.graph.pagerank(personalize, **kwargs)

    def get(self, properties: Optional[dict] = None, ids: Optional[List[str]] = None) -> List[LabelledNode]:
        return self.graph.get_by_ids(ids)

    def get_triplets(
        self,
        entity_names: Optional[List[str]] = None,
        relation_names: Optional[List[str]] = None,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> List[Triplet]:
        if not any([ids, properties, entity_names, relation_names]):
            return []

        triplets = self.graph.get_triplets(ids=ids)
        if entity_names:
            triplets = [t for t in triplets if t[0].id in entity_names or t[2].id in entity_names]
        if relation_names:
            triplets = [t for t in triplets if t[1].id in relation_names]
        if properties:
            triplets = [
                t
                for t in triplets
                if any(
                    t[0].properties.get(k) == v
                    or t[1].properties.get(k) == v
                    or t[2].properties.get(k) == v
                    for k, v in properties.items()
                )
            ]
        if ids:
            triplets = [t for t in triplets if any(t[0].id == i or t[2].id == i for i in ids)]
        return triplets

    def get_rel_map(
        self,
        graph_nodes: List[LabelledNode],
        depth: int = 2,
        limit: int = 30,
        ignore_rels: Optional[List[str]] = None,
    ) -> List[Triplet]:
        triplets: list = []
        cur_depth = 0
        graph_triplets = self.get_triplets(ids=[gn.id for gn in graph_nodes])
        seen_triplets: set[str] = set()

        while len(graph_triplets) > 0 and cur_depth < depth:
            triplets.extend(graph_triplets)
            graph_triplets = self.get_triplets(ids=[t[2].id for t in graph_triplets])
            graph_triplets = [t for t in graph_triplets if str(t) not in seen_triplets]
            seen_triplets.update([str(t) for t in graph_triplets])
            cur_depth += 1

        ignore_rels = ignore_rels or []
        return [t for t in triplets if t[1].id not in ignore_rels]
