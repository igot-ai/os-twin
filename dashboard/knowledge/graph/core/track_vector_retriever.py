"""Vector retriever that tracks matched IDs/scores and feeds them to the
PageRank-based graph reranker on the engine.

Significance filtering (re-introduced):
- Uses :class:`~.significance_analyzer.SignificanceAnalyzer` to classify
  entities into *significant*, *moderate*, and *baseline* buckets.
- When ``use_significance_filtering=True`` (default), triplets where **both**
  source and target fall below the adaptive baseline threshold are pruned,
  cutting non-relevant noise from the result set.
- ``remove_baseline=True`` (default) completely drops baseline entities from
  the score map; ``remove_baseline=False`` dampens them instead (×0.7).
- Significant entities receive a 1.5× boost to sharpen the signal.
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
from dashboard.knowledge.graph.core.significance_analyzer import SignificanceAnalyzer
from dashboard.knowledge.graph.utils.rag import _get_nodes_from_triplets

if TYPE_CHECKING:  # pragma: no cover
    from dashboard.knowledge.graph.core.graph_rag_query_engine import GraphRAGQueryEngine

logger = logging.getLogger(__name__)

# Boost / dampening constants – easy to tune from one place.
_SIGNIFICANT_BOOST = 1.5
_BASELINE_DAMPEN = 0.7
_DEFAULT_SCORE = 0.01
_MIN_SCORES_FOR_SIGNIFICANCE = 5  # need ≥5 data points for meaningful stats


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

    # ------------------------------------------------------------------
    # Triplet scoring with significance filtering
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_triplet_scores(
        id_scores,
        raw_triplets: List[Triplet],
        use_significance_filtering: bool = True,
        significance_method: str = "ensemble",
        remove_baseline: bool = True,
    ):
        """Calculate triplet scores with optional significance-based filtering.

        Args:
            id_scores: List of ``(entity_id, score)`` tuples from PageRank.
            raw_triplets: List of triplets to score.
            use_significance_filtering: Whether to apply statistical
                significance filtering (default ``True``).
            significance_method: Method for significance detection –
                ``'ensemble'``, ``'modified_z'``, ``'iqr'``, etc.
            remove_baseline: If ``True``, completely removes baseline
                variables; if ``False``, dampens them (×0.7).

        Returns:
            ``(filtered_triplets, scores)`` where *filtered_triplets* excludes
            triplets whose **both** source and target scores fall below the
            adaptive baseline threshold.
        """
        score_map: Dict[str, float] = dict(id_scores)

        # ── Phase 1: significance analysis & score-map conditioning ──
        baseline_threshold: float = _DEFAULT_SCORE  # fallback

        # Need enough data points for statistical significance to be meaningful.
        _apply_significance = (
            use_significance_filtering
            and id_scores
            and len(id_scores) >= _MIN_SCORES_FOR_SIGNIFICANCE
        )

        if _apply_significance:
            analyzer = SignificanceAnalyzer()
            significant_vars = analyzer.detect_significant_variables(
                id_scores, significance_method
            )

            # Build lookup sets
            significant_entities: set = set()
            for category in ("significant", "moderate"):
                for entity_id, _ in significant_vars[category]:
                    significant_entities.add(entity_id)

            baseline_threshold = analyzer.calculate_baseline_threshold(
                id_scores, "adaptive"
            )

            action = "removed" if remove_baseline else "dampened"
            logger.debug(
                "Significance analysis: %d significant, %d moderate, "
                "%d baseline variables (%s)",
                len(significant_vars["significant"]),
                len(significant_vars["moderate"]),
                len(significant_vars["baseline"]),
                action,
            )

            if remove_baseline:
                baseline_ids = {eid for eid, _ in significant_vars["baseline"]}
                for eid in list(score_map.keys()):
                    if eid in baseline_ids:
                        del score_map[eid]

                # Boost remaining significant entities
                for eid in list(score_map.keys()):
                    if eid in significant_entities and score_map[eid] > baseline_threshold:
                        score_map[eid] *= _SIGNIFICANT_BOOST
            else:
                for eid in list(score_map.keys()):
                    if eid in significant_entities:
                        if score_map[eid] > baseline_threshold:
                            score_map[eid] *= _SIGNIFICANT_BOOST
                    else:
                        score_map[eid] = max(
                            score_map[eid] * _BASELINE_DAMPEN, _DEFAULT_SCORE
                        )

        # ── Phase 2: score & filter triplets ──
        filtered_triplets: List[Triplet] = []
        scores: List[float] = []

        for source, desc, target in raw_triplets:
            source_score = score_map.get(source.id, _DEFAULT_SCORE)
            target_score = score_map.get(target.id, _DEFAULT_SCORE)

            # Filter triplets where BOTH endpoints are below baseline
            if (
                _apply_significance
                and source_score <= baseline_threshold
                and target_score <= baseline_threshold
            ):
                logger.debug(
                    "Filtering out triplet: %s (%.6f) -> %s (%.6f) "
                    "[both below baseline %.6f]",
                    source.id,
                    source_score,
                    target.id,
                    target_score,
                    baseline_threshold,
                )
                continue

            relationship_weight = TrackVectorRetriever.get_relationship_weight(desc.id)
            combined = TrackVectorRetriever.calculate_combined_score(
                source_score, target_score, relationship_weight
            )

            filtered_triplets.append((source, desc, target))
            scores.append(combined)

            score_map[source.id] = TrackVectorRetriever.update_entity_score(
                source_score, combined
            )
            score_map[target.id] = TrackVectorRetriever.update_entity_score(
                target_score, combined
            )

        # Log filtering summary
        if _apply_significance:
            removed = len(raw_triplets) - len(filtered_triplets)
            if removed > 0:
                logger.debug(
                    "Triplet filtering: removed %d/%d triplets where both "
                    "endpoints were below baseline",
                    removed,
                    len(raw_triplets),
                )

        return filtered_triplets, scores

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_relationship_weight(desc: str) -> float:
        return 1.0

    @staticmethod
    def calculate_combined_score(source_score: float, target_score: float, weight: float) -> float:
        return weight * ((source_score * target_score) ** 0.5)

    @staticmethod
    def update_entity_score(old_score: float, new_score: float) -> float:
        return (old_score + new_score) / 2
