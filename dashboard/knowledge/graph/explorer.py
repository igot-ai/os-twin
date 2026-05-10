"""Knowledge Explorer — tiled graph loading for the Supernova visualization layer.

Provides progressive, on-demand graph exploration APIs that compose existing
:class:`KuzuLabelledPropertyGraph` methods. The existing flat ``get_graph``
endpoint remains untouched — this module adds *new* capabilities:

- **seed**: Load the "brightest" nodes (top PageRank) + their 1-hop neighborhood.
- **expand**: Expand from a set of node IDs outward by N hops.
- **search**: Vector-similarity search over node embeddings + 1-hop context.
- **path**: Shortest weighted path between two nodes.
- **node_detail**: Full detail for a single node including incident edges + scores.
- **summary**: Lightweight topology stats without any node data.

All methods return plain dicts that are JSON-serialisable — no LlamaIndex types
leak into the API layer.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node / edge serialization helpers
# ---------------------------------------------------------------------------


def _node_to_dict(node: Any) -> Dict[str, Any]:
    """Serialize a LlamaIndex LabelledNode to a JSON-friendly dict.

    Includes optional ``degree`` (number of incident relations) and
    ``centrality_score`` when available.
    """
    props = getattr(node, "properties", None) or {}
    if isinstance(props, str):
        try:
            props = json.loads(props)
        except (json.JSONDecodeError, TypeError):
            props = {}

    return {
        "id": getattr(node, "id", ""),
        "label": getattr(node, "label", ""),
        "name": getattr(node, "name", "") or getattr(node, "id", ""),
        "score": float(props.get("weight", 1.0)),
        "properties": props,
    }


def _relation_to_dict(rel: Any) -> Dict[str, Any]:
    """Serialize a LlamaIndex Relation to a JSON-friendly dict.

    Preserves ``relation_label`` and ``relation_properties`` (currently
    discarded by the flat ``get_graph`` — this is the enhanced version).
    """
    rel_props = getattr(rel, "properties", None) or {}
    if isinstance(rel_props, str):
        try:
            rel_props = json.loads(rel_props)
        except (json.JSONDecodeError, TypeError):
            rel_props = {}

    # Try structured fields first, fall back to properties dict
    rel_label = getattr(rel, "label", "") or rel_props.get("relation_label", "RELATES")
    rel_weight = float(
        rel_props.get("weight", 1.0)
        if isinstance(rel_props, dict)
        else 1.0
    )

    return {
        "source": getattr(rel, "source_id", ""),
        "target": getattr(rel, "target_id", ""),
        "label": rel_label,
        "weight": rel_weight,
        "properties": rel_props,
    }


def _triplet_to_edge_dicts(source: Any, rel: Any, target: Any) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """Convert a (source, relation, target) triplet into node/edge dicts.

    Returns (source_dict, target_dict, edge_dict, [node_dicts]).
    Handles deduplication upstream.
    """
    s_dict = _node_to_dict(source)
    t_dict = _node_to_dict(target)
    e_dict = _relation_to_dict(rel)
    return s_dict, t_dict, e_dict, [s_dict, t_dict]


# ---------------------------------------------------------------------------
# KnowledgeExplorer
# ---------------------------------------------------------------------------


class KnowledgeExplorer:
    """Progressive graph exploration engine for the Supernova visualisation.

    Composes existing :class:`KuzuLabelledPropertyGraph` methods — no new
    Cypher queries are introduced. This class is a thin orchestration layer.

    Usage::

        kg = service.get_kuzu_graph(namespace)
        explorer = KnowledgeExplorer(kg)
        seed = explorer.seed(top_k=50)
        expanded = explorer.expand(node_ids=["id1", "id2"], depth=1)
    """

    def __init__(self, graph: Any) -> None:
        self.graph = graph

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return lightweight topology stats without node data.

        Includes node/edge counts, label distribution, and degree stats.
        All via cheap Cypher COUNT queries.
        """
        kg = self.graph
        try:
            entity_count = kg.count_entities()
            chunk_count = kg.count_chunks()
            relation_count = kg.count_relations()
        except Exception as exc:
            logger.error("Explorer summary count failed: %s", exc)
            entity_count, chunk_count, relation_count = 0, 0, 0

        # Label distribution (cheap aggregation)
        label_distribution: Dict[str, int] = {}
        try:
            conn = kg.connection
            result = conn.execute(
                "MATCH (n:Node) WHERE n.label <> 'text_chunk' "
                "RETURN n.label AS label, count(n) AS cnt ORDER BY cnt DESC LIMIT 20"
            )
            for row in result:
                label_distribution[row[0]] = row[1]
        except Exception as exc:
            logger.debug("Label distribution query failed: %s", exc)

        # Degree stats
        degree_stats: Dict[str, Any] = {}
        try:
            conn = kg.connection
            result = conn.execute(
                "MATCH (n:Node)-[r:RELATES]->(m:Node) "
                "WHERE n.label <> 'text_chunk' AND m.label <> 'text_chunk' "
                "RETURN n.id AS nid, count(r) AS deg "
                "ORDER BY deg DESC LIMIT 1"
            )
            max_deg = 0
            for row in result:
                max_deg = row[1]
            degree_stats["max_degree"] = max_deg
        except Exception as exc:
            logger.debug("Degree stats query failed: %s", exc)
            degree_stats["max_degree"] = 0

        return {
            "entity_count": entity_count,
            "chunk_count": chunk_count,
            "relation_count": relation_count,
            "label_distribution": label_distribution,
            "degree_stats": degree_stats,
        }

    def seed(self, top_k: int = 50) -> Dict[str, Any]:
        """Load the initial "sky" — top-K nodes by PageRank + 1-hop neighborhood.

        1. Run PageRank with uniform personalization over entity nodes.
        2. Take top-K results.
        3. Expand 1-hop via ``get_triplets(ids=...)``.
        4. Return nodes + edges + stats.

        The PageRank computation is cached by the graph store so repeated
        calls are fast.
        """
        kg = self.graph

        # Step 1: PageRank to find top nodes
        try:
            # Uniform personalization — all nodes get equal weight
            # We need entity IDs first for the personalization dict
            entities = kg.get_all_nodes(label_type="entity")
            entity_ids = [getattr(e, "id", "") for e in entities if getattr(e, "id", "")]
            if not entity_ids:
                return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0, "seed_count": 0}}

            uniform_weight = 1.0 / len(entity_ids)
            personalize = {eid: uniform_weight for eid in entity_ids}

            pagerank_results = kg.pagerank(personalize, score_threshold=0.0)
            top_ids = [pid for pid, _score in pagerank_results[:top_k]]
        except Exception as exc:
            logger.error("Explorer seed PageRank failed: %s", exc)
            # Fallback: just use first top_k entity IDs
            top_ids = entity_ids[:top_k]

        if not top_ids:
            return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0, "seed_count": 0}}

        # Step 2: Expand 1-hop from top nodes
        return self._expand_from_ids(top_ids, include_seed_info=True)

    def expand(self, node_ids: List[str], depth: int = 1) -> Dict[str, Any]:
        """Expand from a set of node IDs outward by N hops.

        Each hop fetches the neighborhood of the frontier nodes via
        ``get_triplets(ids=...)``. Depth is capped at 3 for performance.

        Args:
            node_ids: Starting node IDs to expand from.
            depth: Number of hops (1-3, default 1).

        Returns:
            Dict with nodes, edges, and stats.
        """
        depth = max(1, min(3, depth))
        kg = self.graph

        all_node_ids = set(node_ids)
        frontier = list(node_ids)
        all_edges: List[Dict[str, Any]] = []
        seen_edges: set = set()

        for hop in range(depth):
            if not frontier:
                break
            try:
                triplets = kg.get_triplets(ids=frontier)
            except Exception as exc:
                logger.error("Explorer expand hop %d failed: %s", hop, exc)
                break

            next_frontier: List[str] = []
            for source, rel, target in triplets:
                s_id = getattr(source, "id", "")
                t_id = getattr(target, "id", "")
                r_key = (s_id, t_id, getattr(rel, "label", ""))
                if r_key not in seen_edges:
                    seen_edges.add(r_key)
                    all_edges.append(_relation_to_dict(rel))
                if s_id not in all_node_ids:
                    all_node_ids.add(s_id)
                    next_frontier.append(s_id)
                if t_id not in all_node_ids:
                    all_node_ids.add(t_id)
                    next_frontier.append(t_id)
            frontier = next_frontier

        # Fetch full node data for all discovered IDs
        nodes = self._fetch_nodes_by_ids(list(all_node_ids))
        # Filter edges to only those with both endpoints in the node set
        node_id_set = {n["id"] for n in nodes}
        filtered_edges = [
            e for e in all_edges
            if e["source"] in node_id_set and e["target"] in node_id_set
        ]

        return {
            "nodes": nodes,
            "edges": filtered_edges,
            "stats": {"node_count": len(nodes), "edge_count": len(filtered_edges)},
        }

    def search(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Vector-similarity search over node embeddings + 1-hop context.

        Uses ``get_all_nodes(context=query)`` which leverages KuzuDB's
        vector index, then expands 1-hop for context.

        Args:
            query: Natural language search query.
            limit: Max number of seed results from vector search.

        Returns:
            Dict with nodes, edges, and stats.
        """
        kg = self.graph
        try:
            results = kg.get_all_nodes(label_type="entity", context=query, limit=limit)
        except Exception as exc:
            logger.error("Explorer search failed: %s", exc)
            return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0, "query": query}}

        seed_ids = [getattr(n, "id", "") for n in results if getattr(n, "id", "")]
        if not seed_ids:
            return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0, "query": query}}

        result = self._expand_from_ids(seed_ids)
        result["stats"]["query"] = query
        return result

    def path(self, source_id: str, target_id: str) -> Dict[str, Any]:
        """Find the shortest weighted path between two nodes.

        Uses NetworkX shortest_path on the entity subgraph with
        relationship-type weighting.

        Args:
            source_id: Starting node ID.
            target_id: Ending node ID.

        Returns:
            Dict with path node IDs, path edges, nodes, and stats.
        """
        import networkx as nx  # noqa: WPS433

        kg = self.graph
        try:
            G = kg.get_all_nodes(label_type="entity", graph=True)
        except Exception as exc:
            logger.error("Explorer path graph fetch failed: %s", exc)
            return {"path": [], "nodes": [], "edges": [], "stats": {"path_length": 0}}

        if source_id not in G or target_id not in G:
            return {"path": [], "nodes": [], "edges": [], "stats": {"path_length": 0, "error": "node_not_found"}}

        try:
            path_nodes = nx.shortest_path(G, source_id, target_id, weight="weight")
        except nx.NetworkXNoPath:
            return {"path": [], "nodes": [], "edges": [], "stats": {"path_length": 0, "error": "no_path"}}
        except Exception as exc:
            logger.error("Explorer path computation failed: %s", exc)
            return {"path": [], "nodes": [], "edges": [], "stats": {"path_length": 0, "error": str(exc)}}

        # Fetch full node data for path nodes
        # Map NX node IDs to original entity IDs
        original_ids = []
        for nx_id in path_nodes:
            orig_id = G.nodes[nx_id].get("id", nx_id)
            original_ids.append(orig_id)

        nodes = self._fetch_nodes_by_ids(original_ids)

        # Get edges along the path
        path_edges = []
        for i in range(len(path_nodes) - 1):
            nx_s = path_nodes[i]
            nx_t = path_nodes[i + 1]
            orig_s = G.nodes[nx_s].get("id", nx_s)
            orig_t = G.nodes[nx_t].get("id", nx_t)
            edge_data = G.edges[nx_s, nx_t] if G.has_edge(nx_s, nx_t) else {}
            rel_label = edge_data.get("relation_label", edge_data.get("label", "RELATES"))
            rel_weight = edge_data.get("weight", 1.0)
            path_edges.append({
                "source": orig_s,
                "target": orig_t,
                "label": rel_label,
                "weight": rel_weight,
            })

        return {
            "path": original_ids,
            "nodes": nodes,
            "edges": path_edges,
            "stats": {"path_length": len(original_ids)},
        }

    def node_detail(self, node_id: str) -> Dict[str, Any]:
        """Full detail for a single node: properties, incident edges, scores.

        Args:
            node_id: The node ID to inspect.

        Returns:
            Dict with node data, incident edges, and scores.
        """
        kg = self.graph
        try:
            node = kg.get_node(node_id)
        except Exception as exc:
            logger.error("Explorer node_detail fetch failed: %s", exc)
            return {"node": None, "edges": [], "stats": {}}

        if node is None:
            return {"node": None, "edges": [], "stats": {"error": "node_not_found"}}

        node_dict = _node_to_dict(node)

        # Get incident edges
        incident_edges = []
        try:
            triplets = kg.get_triplets(ids=[node_id])
            for source, rel, target in triplets:
                edge = _relation_to_dict(rel)
                # Annotate with whether this is incoming or outgoing
                s_id = getattr(source, "id", "")
                if s_id == node_id:
                    edge["direction"] = "outgoing"
                else:
                    edge["direction"] = "incoming"
                # Include peer node info
                peer = target if s_id == node_id else source
                edge["peer"] = _node_to_dict(peer)
                incident_edges.append(edge)
        except Exception as exc:
            logger.error("Explorer node_detail edges failed: %s", exc)

        # Compute degree
        out_degree = sum(1 for e in incident_edges if e.get("direction") == "outgoing")
        in_degree = sum(1 for e in incident_edges if e.get("direction") == "incoming")

        node_dict["degree"] = in_degree + out_degree
        node_dict["in_degree"] = in_degree
        node_dict["out_degree"] = out_degree

        return {
            "node": node_dict,
            "edges": incident_edges,
            "stats": {
                "degree": in_degree + out_degree,
                "in_degree": in_degree,
                "out_degree": out_degree,
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _expand_from_ids(self, seed_ids: List[str], include_seed_info: bool = False) -> Dict[str, Any]:
        """Expand 1-hop from seed IDs and return the subgraph.

        This is the shared core for ``seed()`` and ``search()``.
        """
        kg = self.graph
        all_node_ids = set(seed_ids)
        all_edges: List[Dict[str, Any]] = []
        seen_edges: set = set()

        try:
            triplets = kg.get_triplets(ids=seed_ids)
        except Exception as exc:
            logger.error("Explorer _expand_from_ids triplet fetch failed: %s", exc)
            triplets = []

        for source, rel, target in triplets:
            s_id = getattr(source, "id", "")
            t_id = getattr(target, "id", "")
            r_key = (s_id, t_id, getattr(rel, "label", ""))
            if r_key not in seen_edges:
                seen_edges.add(r_key)
                all_edges.append(_relation_to_dict(rel))
            all_node_ids.add(s_id)
            all_node_ids.add(t_id)

        nodes = self._fetch_nodes_by_ids(list(all_node_ids))

        # Filter edges to only those with both endpoints present
        node_id_set = {n["id"] for n in nodes}
        filtered_edges = [
            e for e in all_edges
            if e["source"] in node_id_set and e["target"] in node_id_set
        ]

        stats: Dict[str, Any] = {
            "node_count": len(nodes),
            "edge_count": len(filtered_edges),
        }
        if include_seed_info:
            stats["seed_count"] = len(seed_ids)

        return {
            "nodes": nodes,
            "edges": filtered_edges,
            "stats": stats,
        }

    def _fetch_nodes_by_ids(self, node_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch full node data for a list of IDs.

        Uses ``kg.get_by_ids()`` which is efficient for batch lookups.
        Falls back to individual ``get_node()`` calls if batch fails.
        """
        if not node_ids:
            return []

        kg = self.graph
        nodes: List[Dict[str, Any]] = []
        try:
            kg_nodes = kg.get_by_ids(node_ids)
            for n in kg_nodes:
                nodes.append(_node_to_dict(n))
            return nodes
        except Exception as exc:
            logger.warning("Batch node fetch failed, falling back: %s", exc)

        # Fallback: individual fetches
        for nid in node_ids:
            try:
                n = kg.get_node(nid)
                if n is not None:
                    nodes.append(_node_to_dict(n))
            except Exception:
                pass
        return nodes
