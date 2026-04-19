"""Vector retriever that tracks matched IDs/scores and feeds them to the
PageRank-based graph reranker on the engine.

Refactor notes (EPIC-001):
- Removed dependency on the deleted ``SignificanceAnalyzer``. The fancy
  significance-filtering branch in ``calculate_triplet_scores`` is now a no-op
  (we keep all triplets, scored via the simple combined score).
- Embedding lookups use :class:`KnowledgeEmbedder` lazily (not used directly
  here — we receive ``embed_model`` from the caller).
- ``networkx`` is imported lazily (top of __init__).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.graph_stores.types import PropertyGraphStore, Triplet
from llama_index.core.indices.property_graph import VectorContextRetriever
from llama_index.core.schema import BaseNode, NodeWithScore
from llama_index.core.vector_stores import MetadataFilters
from llama_index.core.vector_stores.types import BasePydanticVectorStore

from dashboard.knowledge.config import PAGERANK_SCORE_THRESHOLD
from dashboard.knowledge.graph.utils.rag import _get_nodes_from_triplets

if TYPE_CHECKING:  # pragma: no cover
    from dashboard.knowledge.graph.core.graph_rag_query_engine import GraphRAGQueryEngine

logger = logging.getLogger(__name__)


class TrackVectorRetriever(VectorContextRetriever):
    """Vector retriever with PageRank-based reranking via the host engine."""

    matching_ids: List[str]
    matching_scores: List[float]
    engine: "GraphRAGQueryEngine"
    category_id: Any = None

    def __init__(
        self,
        engine,
        graph_store: PropertyGraphStore,
        include_text: bool = True,
        embed_model: Optional[BaseEmbedding] = None,
        vector_store: Optional[BasePydanticVectorStore] = None,
        similarity_top_k: int = 4,
        path_depth: int = 1,
        similarity_score: Optional[float] = None,
        filters: Optional[MetadataFilters] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            graph_store,
            include_text=include_text,
            embed_model=embed_model,
            vector_store=vector_store,
            similarity_top_k=similarity_top_k,
            path_depth=path_depth,
            similarity_score=similarity_score,
            filters=filters,
            **kwargs,
        )
        # Lazy networkx import.
        import networkx as nx  # noqa: WPS433

        self.matching_ids = []
        self.matching_scores = []
        self.engine = engine
        self.category_id = kwargs.get("category_id")
        self.graph = nx.DiGraph()

    def _get_kg_ids(self, kg_nodes: Sequence[BaseNode]) -> List[str]:
        matching = super()._get_kg_ids(kg_nodes)
        self.matching_ids = matching
        return matching

    def _get_nodes_with_score(
        self,
        triplets: List[Triplet],
        scores: Optional[List[float]] = None,
    ) -> List[NodeWithScore]:
        self.matching_scores = scores
        personalize: Dict[str, float] = {}

        if self.matching_scores is not None and self.matching_ids is not None:
            for i, triplet in enumerate(triplets):
                score = self.matching_scores[i]
                personalize[triplet[0].id] = personalize.get(triplet[0].id, 0) + score
                personalize[triplet[2].id] = personalize.get(triplet[2].id, 0) + score
                if i in self.matching_ids:
                    matching_id = self.matching_ids[i]
                    personalize[matching_id] = personalize.get(matching_id, 0) + score

        ranks_ids = self.engine.compute_page_rank(personalize, category_id=self.category_id)
        ids = [r[0] for r in ranks_ids if r[1] > PAGERANK_SCORE_THRESHOLD]
        rel_map = self.engine.get_community_relations(ids)

        triplets_filtered, scores_filtered = self.calculate_triplet_scores(ranks_ids, rel_map)
        return _get_nodes_from_triplets(self.graph, triplets_filtered, scores_filtered)

    @staticmethod
    def calculate_triplet_scores(
        id_scores,
        raw_triplets: List[Triplet],
        use_significance_filtering: bool = False,  # significance analyzer was removed
        significance_method: str = "ensemble",  # kept for API compat
        remove_baseline: bool = True,  # kept for API compat
    ):
        """Score triplets via a simple combined formula. Significance filtering is a no-op."""
        score_map: Dict[str, float] = dict(id_scores)
        scores: List[float] = []
        filtered_triplets: List[Triplet] = []

        for source, desc, target in raw_triplets:
            source_score = score_map.get(source.id, 0.01)
            target_score = score_map.get(target.id, 0.01)
            relationship_weight = TrackVectorRetriever.get_relationship_weight(desc.id)
            combined = TrackVectorRetriever.calculate_combined_score(
                source_score, target_score, relationship_weight
            )
            filtered_triplets.append((source, desc, target))
            scores.append(combined)
            score_map[source.id] = TrackVectorRetriever.update_entity_score(source_score, combined)
            score_map[target.id] = TrackVectorRetriever.update_entity_score(target_score, combined)

        return filtered_triplets, scores

    @staticmethod
    def get_relationship_weight(desc: str) -> float:
        return 1.0

    @staticmethod
    def calculate_combined_score(source_score: float, target_score: float, weight: float) -> float:
        return weight * ((source_score * target_score) ** 0.5)

    @staticmethod
    def update_entity_score(old_score: float, new_score: float) -> float:
        return (old_score + new_score) / 2
