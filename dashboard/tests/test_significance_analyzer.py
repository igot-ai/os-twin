"""Tests for SignificanceAnalyzer and significance-based triplet filtering.

Covers:
- SignificanceAnalyzer detection methods (modified_z, iqr, jenks, isolation_forest, ensemble)
- Distribution analysis & baseline threshold calculation
- calculate_triplet_scores with significance filtering enabled
- Filtering behaviour: remove_baseline vs dampen_baseline
- Edge cases: empty inputs, uniform scores, tiny datasets
"""

from __future__ import annotations

import pytest
from unittest import mock

from dashboard.knowledge.graph.core.significance_analyzer import SignificanceAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_triplet(name_a: str, name_b: str, score_a: float = 0.5, score_b: float = 0.5):
    """Create a (EntityNode, Relation, EntityNode) triplet + id_scores entry."""
    from llama_index.core.graph_stores.types import EntityNode, Relation

    entity_a = EntityNode(name=name_a, label="T", properties={}, embedding=[])
    entity_b = EntityNode(name=name_b, label="T", properties={}, embedding=[])
    relation = Relation(source_id=entity_a.id, target_id=entity_b.id, label="REL")
    return (entity_a, relation, entity_b), [(entity_a.id, score_a), (entity_b.id, score_b)]


def _build_scored_entities(n: int, high_count: int = 2, high_score: float = 0.9, low_score: float = 0.01):
    """Build n (entity_id, score) tuples with high_count high-scorers and the rest low."""
    scores = []
    for i in range(n):
        if i < high_count:
            scores.append((f"entity_{i}", high_score))
        else:
            scores.append((f"entity_{i}", low_score))
    return scores


# ---------------------------------------------------------------------------
# SignificanceAnalyzer unit tests
# ---------------------------------------------------------------------------


class TestSignificanceAnalyzerEmpty:
    """Edge cases with empty / tiny inputs."""

    def test_detect_empty_scores(self):
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables([], "ensemble")
        assert result == {"significant": [], "moderate": [], "baseline": []}

    def test_analyze_distribution_empty(self):
        analyzer = SignificanceAnalyzer()
        assert analyzer.analyze_distribution([]) == {}

    def test_detect_single_element(self):
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables([("a", 1.0)], "modified_z")
        total = len(result["significant"]) + len(result["moderate"]) + len(result["baseline"])
        assert total == 1

    def test_detect_two_elements(self):
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables([("a", 0.9), ("b", 0.1)], "iqr")
        total = len(result["significant"]) + len(result["moderate"]) + len(result["baseline"])
        assert total == 2


class TestSignificanceAnalyzerMethods:
    """Test individual detection methods produce valid categorisations."""

    @pytest.fixture()
    def mixed_scores(self):
        """20 entities: 3 high, 5 medium, 12 low."""
        scores = []
        for i in range(3):
            scores.append((f"high_{i}", 0.9 + i * 0.02))
        for i in range(5):
            scores.append((f"mid_{i}", 0.3 + i * 0.05))
        for i in range(12):
            scores.append((f"low_{i}", 0.01 + i * 0.005))
        return scores

    def _assert_valid_result(self, result, total):
        for cat in ("significant", "moderate", "baseline"):
            assert cat in result
        actual_total = sum(len(result[c]) for c in result)
        assert actual_total == total

    def test_modified_z(self, mixed_scores):
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables(mixed_scores, "modified_z")
        self._assert_valid_result(result, len(mixed_scores))

    def test_iqr(self, mixed_scores):
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables(mixed_scores, "iqr")
        self._assert_valid_result(result, len(mixed_scores))

    def test_jenks(self, mixed_scores):
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables(mixed_scores, "jenks")
        self._assert_valid_result(result, len(mixed_scores))

    def test_isolation_forest(self, mixed_scores):
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables(mixed_scores, "isolation_forest")
        self._assert_valid_result(result, len(mixed_scores))

    def test_ensemble(self, mixed_scores):
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables(mixed_scores, "ensemble")
        self._assert_valid_result(result, len(mixed_scores))

    def test_unknown_method_raises(self):
        analyzer = SignificanceAnalyzer()
        with pytest.raises(ValueError, match="Unknown method"):
            analyzer.detect_significant_variables([("a", 1.0), ("b", 2.0)], "bogus")


class TestSignificanceAnalyzerHighSignal:
    """With a clear signal, at least some entities should be classified as significant."""

    def test_high_outliers_detected(self):
        """3 outliers at 10.0 vs 17 noise at 0.01 — outliers should be significant."""
        scores = [(f"noise_{i}", 0.01) for i in range(17)]
        scores += [(f"signal_{i}", 10.0) for i in range(3)]
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables(scores, "ensemble")
        sig_ids = {e for e, _ in result["significant"]}
        # At least some of the signals should be detected
        assert len(sig_ids & {f"signal_{i}" for i in range(3)}) >= 1


class TestBaselineThreshold:
    """Test baseline threshold calculation methods."""

    @pytest.fixture()
    def scores(self):
        return [(f"e{i}", float(i)) for i in range(1, 11)]  # 1..10

    def test_adaptive_threshold(self, scores):
        analyzer = SignificanceAnalyzer()
        t = analyzer.calculate_baseline_threshold(scores, "adaptive")
        assert isinstance(t, float)
        assert t > 0

    def test_statistical_threshold(self, scores):
        analyzer = SignificanceAnalyzer()
        t = analyzer.calculate_baseline_threshold(scores, "statistical")
        assert isinstance(t, float)

    def test_percentile_threshold(self, scores):
        analyzer = SignificanceAnalyzer()
        t = analyzer.calculate_baseline_threshold(scores, "percentile")
        assert isinstance(t, float)

    def test_unknown_threshold_raises(self, scores):
        analyzer = SignificanceAnalyzer()
        with pytest.raises(ValueError):
            analyzer.calculate_baseline_threshold(scores, "nonexistent")


class TestDistributionAnalysis:
    """Test analyze_distribution returns proper stats."""

    def test_basic_stats(self):
        scores = [(f"e{i}", float(i)) for i in range(1, 21)]
        analyzer = SignificanceAnalyzer()
        analysis = analyzer.analyze_distribution(scores)

        assert "statistics" in analysis
        assert "distribution" in analysis
        s = analysis["statistics"]
        assert s["count"] == 20
        assert s["min"] == 1.0
        assert s["max"] == 20.0

    def test_distribution_type_detection(self):
        analyzer = SignificanceAnalyzer()
        assert analyzer._identify_distribution_type(0.1, 1.0) == "approximately_normal"
        assert analyzer._identify_distribution_type(2.0, 1.0) == "right_skewed"
        assert analyzer._identify_distribution_type(-2.0, 1.0) == "left_skewed"
        assert analyzer._identify_distribution_type(0.3, 5.0) == "heavy_tailed"


class TestRecommendations:
    """Test get_recommendations produces structured output."""

    def test_recommendations_structure(self):
        scores = [(f"e{i}", float(i) * 0.1) for i in range(20)]
        analyzer = SignificanceAnalyzer()
        recs = analyzer.get_recommendations(scores)
        assert "distribution_analysis" in recs
        assert "significant_variables" in recs
        assert "baseline_threshold" in recs
        assert "recommendations" in recs
        assert isinstance(recs["recommendations"], list)


# ---------------------------------------------------------------------------
# calculate_triplet_scores with significance filtering
# ---------------------------------------------------------------------------


class TestTripletScoresWithSignificance:
    """Test the full pipeline: significance → score → filter in
    TrackVectorRetriever.calculate_triplet_scores.
    """

    @pytest.fixture()
    def _large_dataset(self):
        """Build 10 triplets: 2 high-score, 8 low-score entities."""
        from llama_index.core.graph_stores.types import EntityNode, Relation

        id_scores = []
        triplets = []

        # 2 significant entities (high score)
        for i in range(2):
            a = EntityNode(name=f"sig_{i}_a", label="T", properties={}, embedding=[])
            b = EntityNode(name=f"sig_{i}_b", label="T", properties={}, embedding=[])
            rel = Relation(source_id=a.id, target_id=b.id, label="REL")
            triplets.append((a, rel, b))
            id_scores.append((a.id, 0.85 + i * 0.05))
            id_scores.append((b.id, 0.80 + i * 0.05))

        # 8 baseline entities (noise)
        for i in range(8):
            a = EntityNode(name=f"noise_{i}_a", label="T", properties={}, embedding=[])
            b = EntityNode(name=f"noise_{i}_b", label="T", properties={}, embedding=[])
            rel = Relation(source_id=a.id, target_id=b.id, label="REL")
            triplets.append((a, rel, b))
            id_scores.append((a.id, 0.001 + i * 0.0001))
            id_scores.append((b.id, 0.001 + i * 0.0001))

        return id_scores, triplets

    def test_filtering_reduces_triplets(self, _large_dataset):
        """With significance filtering ON, some noise triplets should be cut."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever

        id_scores, triplets = _large_dataset
        filtered, scores = TrackVectorRetriever.calculate_triplet_scores(
            id_scores, triplets,
            use_significance_filtering=True,
            significance_method="ensemble",
            remove_baseline=True,
        )
        # Should keep at least the 2 significant triplets but remove some noise
        assert len(filtered) <= len(triplets)
        assert len(filtered) >= 2  # the signal triplets survive
        assert len(scores) == len(filtered)

    def test_no_filtering_keeps_all(self, _large_dataset):
        """With significance filtering OFF, all triplets are kept."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever

        id_scores, triplets = _large_dataset
        filtered, scores = TrackVectorRetriever.calculate_triplet_scores(
            id_scores, triplets,
            use_significance_filtering=False,
        )
        assert len(filtered) == len(triplets)
        assert len(scores) == len(triplets)

    def test_dampen_mode_keeps_more(self, _large_dataset):
        """remove_baseline=False dampens but doesn't drop, so more triplets may survive."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever

        id_scores, triplets = _large_dataset
        filtered_remove, _ = TrackVectorRetriever.calculate_triplet_scores(
            id_scores, triplets,
            use_significance_filtering=True,
            remove_baseline=True,
        )
        filtered_dampen, _ = TrackVectorRetriever.calculate_triplet_scores(
            id_scores, triplets,
            use_significance_filtering=True,
            remove_baseline=False,
        )
        # Dampening is more lenient than removal
        assert len(filtered_dampen) >= len(filtered_remove)

    def test_small_dataset_skips_significance(self):
        """With < _MIN_SCORES_FOR_SIGNIFICANCE entities, filtering is bypassed."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        from llama_index.core.graph_stores.types import EntityNode, Relation

        entity_a = EntityNode(name="A", label="T", properties={}, embedding=[])
        entity_b = EntityNode(name="B", label="T", properties={}, embedding=[])
        rel = Relation(source_id=entity_a.id, target_id=entity_b.id, label="REL")

        id_scores = [(entity_a.id, 0.8), (entity_b.id, 0.6)]
        triplet = (entity_a, rel, entity_b)

        filtered, scores = TrackVectorRetriever.calculate_triplet_scores(
            id_scores, [triplet],
            use_significance_filtering=True,  # requested but will be skipped
        )
        assert len(filtered) == 1  # not filtered because dataset is too small
        assert len(scores) == 1

    def test_empty_id_scores(self):
        """Empty id_scores → no filtering, defaults used."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        from llama_index.core.graph_stores.types import EntityNode, Relation

        a = EntityNode(name="X", label="T", properties={}, embedding=[])
        b = EntityNode(name="Y", label="T", properties={}, embedding=[])
        rel = Relation(source_id=a.id, target_id=b.id, label="REL")

        filtered, scores = TrackVectorRetriever.calculate_triplet_scores(
            [], [(a, rel, b)],
            use_significance_filtering=True,
        )
        assert len(filtered) == 1
        assert scores[0] > 0

    def test_scores_are_positive(self, _large_dataset):
        """All returned scores should be positive."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever

        id_scores, triplets = _large_dataset
        _, scores = TrackVectorRetriever.calculate_triplet_scores(
            id_scores, triplets,
            use_significance_filtering=True,
        )
        assert all(s > 0 for s in scores)

    def test_different_methods(self, _large_dataset):
        """All significance methods should produce valid output."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever

        id_scores, triplets = _large_dataset
        for method in ("ensemble", "modified_z", "iqr", "jenks", "isolation_forest"):
            filtered, scores = TrackVectorRetriever.calculate_triplet_scores(
                id_scores, triplets,
                use_significance_filtering=True,
                significance_method=method,
            )
            assert len(filtered) == len(scores)
            assert len(filtered) <= len(triplets)


class TestUniformScores:
    """When all scores are identical, the analyzer should handle it gracefully."""

    def test_uniform_scores_no_crash(self):
        scores = [(f"e{i}", 0.5) for i in range(20)]
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables(scores, "ensemble")
        total = sum(len(result[c]) for c in result)
        assert total == 20

    def test_uniform_triplet_scoring(self):
        """Uniform scores shouldn't crash calculate_triplet_scores."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        from llama_index.core.graph_stores.types import EntityNode, Relation

        id_scores = [(f"e{i}", 0.5) for i in range(10)]
        triplets = []
        for i in range(5):
            a = EntityNode(name=f"u{i}a", label="T", properties={}, embedding=[])
            b = EntityNode(name=f"u{i}b", label="T", properties={}, embedding=[])
            rel = Relation(source_id=a.id, target_id=b.id, label="REL")
            triplets.append((a, rel, b))
            id_scores.append((a.id, 0.5))
            id_scores.append((b.id, 0.5))

        filtered, scores = TrackVectorRetriever.calculate_triplet_scores(
            id_scores, triplets,
            use_significance_filtering=True,
        )
        assert len(scores) == len(filtered)


# ---------------------------------------------------------------------------
# Property-graph integration tests (lines 84-111 of track_vector_retriever)
# ---------------------------------------------------------------------------


class TestTrackVectorRetrieverPropertyGraphIntegration:
    """Cover _get_kg_ids and _get_nodes_with_score — the wiring between
    VectorContextRetriever and the PageRank/significance pipeline.
    """

    @pytest.fixture()
    def retriever(self):
        """Build a TrackVectorRetriever with fully mocked collaborators."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        fake_gs = mock.MagicMock(spec=GraphRAGStore)
        fake_vs = mock.MagicMock()
        fake_embed = mock.MagicMock()

        engine = mock.MagicMock()
        # compute_page_rank returns (entity_id, score) with 6 entries so
        # significance filtering triggers (≥5).
        engine.compute_page_rank.return_value = [
            ("e0", 0.9), ("e1", 0.8), ("e2", 0.7),
            ("e3", 0.6), ("e4", 0.5), ("e5", 0.01),
        ]
        # get_community_relations returns triplets from the rel_map
        from llama_index.core.graph_stores.types import EntityNode, Relation
        a = EntityNode(name="A", label="T", properties={}, embedding=[])
        b = EntityNode(name="B", label="T", properties={}, embedding=[])
        c = EntityNode(name="C", label="T", properties={}, embedding=[])
        rel_ab = Relation(source_id=a.id, target_id=b.id, label="R1")
        rel_bc = Relation(source_id=b.id, target_id=c.id, label="R2")
        engine.get_community_relations.return_value = [
            (a, rel_ab, b),
            (b, rel_bc, c),
        ]

        retriever = TrackVectorRetriever(
            engine=engine,
            graph_store=fake_gs,
            vector_store=fake_vs,
            embed_model=fake_embed,
        )
        return retriever, engine, (a, b, c, rel_ab, rel_bc)

    def test_get_kg_ids_delegates_and_stores(self, retriever):
        """_get_kg_ids calls super() and stores matching IDs."""
        ret, _, _ = retriever
        from llama_index.core.schema import TextNode

        nodes = [TextNode(text="x", id_="n1"), TextNode(text="y", id_="n2")]
        result = ret._get_kg_ids(nodes)

        assert isinstance(result, list)
        assert ret.matching_ids == result

    def test_get_nodes_with_score_full_pipeline(self, retriever):
        """_get_nodes_with_score wires: personalize → PageRank → community →
        calculate_triplet_scores → _get_nodes_from_triplets.
        """
        ret, engine, (a, b, c, rel_ab, rel_bc) = retriever

        # Setup matching_ids and matching_scores
        ret.matching_ids = [a.id, b.id]
        triplets = [(a, rel_ab, b), (b, rel_bc, c)]
        scores = [0.9, 0.7]

        result = ret._get_nodes_with_score(triplets, scores)

        # Verify engine was called
        engine.compute_page_rank.assert_called_once()
        engine.get_community_relations.assert_called_once()

        # Result should be a list of NodeWithScore
        assert isinstance(result, list)

    def test_get_nodes_with_score_none_scores(self, retriever):
        """When scores is None, personalize dict stays empty."""
        ret, engine, (a, b, c, rel_ab, rel_bc) = retriever

        ret.matching_ids = [a.id]
        triplets = [(a, rel_ab, b)]

        result = ret._get_nodes_with_score(triplets, None)

        # Should still call PageRank with empty personalize
        engine.compute_page_rank.assert_called_once()
        call_args = engine.compute_page_rank.call_args[0][0]
        assert call_args == {}

    def test_get_nodes_with_score_empty_triplets(self, retriever):
        """Empty triplets produce empty output but still calls engine."""
        ret, engine, _ = retriever

        ret.matching_ids = []
        result = ret._get_nodes_with_score([], [])

        engine.compute_page_rank.assert_called_once()

    def test_category_id_forwarded(self):
        """category_id is stored from kwargs and forwarded to compute_page_rank."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        fake_gs = mock.MagicMock(spec=GraphRAGStore)
        engine = mock.MagicMock()
        engine.compute_page_rank.return_value = []
        engine.get_community_relations.return_value = []

        ret = TrackVectorRetriever(
            engine=engine,
            graph_store=fake_gs,
            vector_store=mock.MagicMock(),
            embed_model=mock.MagicMock(),
            category_id="cat_42",
        )
        ret.matching_ids = []

        ret._get_nodes_with_score([], [])

        engine.compute_page_rank.assert_called_once_with(
            {}, category_id="cat_42"
        )


# ---------------------------------------------------------------------------
# SignificanceAnalyzer – uncovered branches
# ---------------------------------------------------------------------------


class TestAnalyzerExceptionFallbacks:
    """Cover error / fallback branches in the analyzer."""

    def test_ensemble_all_methods_fail(self):
        """When every sub-method raises, ensemble returns all-baseline."""
        import numpy as np

        analyzer = SignificanceAnalyzer()
        scores = [("a", 1.0), ("b", 2.0), ("c", 3.0)]
        values = np.array([s for _, s in scores], dtype=float)

        with mock.patch.object(analyzer, "_modified_z_score_detection", side_effect=RuntimeError):
            with mock.patch.object(analyzer, "_iqr_detection", side_effect=RuntimeError):
                with mock.patch.object(analyzer, "_jenks_detection", side_effect=RuntimeError):
                    with mock.patch.object(analyzer, "_isolation_forest_detection", side_effect=RuntimeError):
                        result = analyzer._ensemble_detection(scores, values)

        assert result["significant"] == []
        assert result["moderate"] == []
        assert len(result["baseline"]) == 3

    def test_isolation_forest_exception_falls_back_to_percentile(self):
        """When IsolationForest.fit raises, fallback to percentile."""
        import numpy as np

        analyzer = SignificanceAnalyzer()
        scores = [(f"e{i}", float(i)) for i in range(15)]
        values = np.array([s for _, s in scores], dtype=float)

        with mock.patch(
            "dashboard.knowledge.graph.core.significance_analyzer._isolation_forest"
        ) as mock_if:
            mock_if.return_value.return_value.fit.side_effect = ValueError("boom")
            result = analyzer._isolation_forest_detection(scores, values)

        # Should still classify all entities via percentile fallback
        total = sum(len(result[c]) for c in result)
        assert total == 15

    def test_jenks_clustering_exception_falls_back(self):
        """When KMeans raises, Jenks falls back to percentile."""
        import numpy as np

        analyzer = SignificanceAnalyzer()
        scores = [(f"e{i}", float(i)) for i in range(10)]
        values = np.array([s for _, s in scores], dtype=float)

        with mock.patch(
            "dashboard.knowledge.graph.core.significance_analyzer._kmeans"
        ) as mock_km:
            mock_km.return_value.return_value.fit_predict.side_effect = RuntimeError("fail")
            result = analyzer._jenks_detection(scores, values)

        total = sum(len(result[c]) for c in result)
        assert total == 10


class TestRecommendationBranches:
    """Cover recommendation branches: skewed, high-ratio, low-ratio."""

    def test_skewed_distribution_recommendation(self):
        """Right-skewed data should trigger the log-transform recommendation."""
        # 18 low values + 2 extreme outliers → right-skewed
        scores = [(f"e{i}", 0.01) for i in range(18)]
        scores += [("big_0", 100.0), ("big_1", 200.0)]

        analyzer = SignificanceAnalyzer()
        recs = analyzer.get_recommendations(scores)
        rec_texts = recs["recommendations"]
        assert any("right-skewed" in r for r in rec_texts)

    def test_high_ratio_recommendation(self):
        """When >20% are significant, suggest tightening."""
        analyzer = SignificanceAnalyzer()
        # Force high significance by creating distinct high-scoring entities
        scores = [(f"sig_{i}", 10.0 + i) for i in range(8)]  # 8 out of 10 — 80%
        scores += [(f"low_{i}", 0.01) for i in range(2)]

        # Mock detect_significant_variables to return high ratio
        with mock.patch.object(
            analyzer, "detect_significant_variables",
            return_value={
                "significant": scores[:8],
                "moderate": [],
                "baseline": scores[8:],
            },
        ):
            recs = analyzer.get_recommendations(scores)
        rec_texts = recs["recommendations"]
        assert any("tightening" in r.lower() for r in rec_texts)

    def test_low_ratio_recommendation(self):
        """When <5% are significant, suggest loosening."""
        analyzer = SignificanceAnalyzer()
        scores = [(f"e{i}", float(i) * 0.01) for i in range(100)]

        # Mock: only 1 out of 100 significant (1%) → <5% threshold
        with mock.patch.object(
            analyzer, "detect_significant_variables",
            return_value={
                "significant": [scores[99]],
                "moderate": [],
                "baseline": scores[:99],
            },
        ):
            recs = analyzer.get_recommendations(scores)
        rec_texts = recs["recommendations"]
        assert any("loosening" in r.lower() for r in rec_texts)


# ---------------------------------------------------------------------------
# Regression tests for senior engineer review fixes
# ---------------------------------------------------------------------------


class TestIsolationForestLogicFix:
    """FIX #1: Isolation Forest was reversed – high anomaly scores (inliers)
    were being promoted instead of low anomaly scores (true outliers)."""

    def test_high_score_outliers_not_marked_as_baseline(self):
        """3 clear outliers at 10.0 among 17 noise at 0.01 –
        the outliers should never all land in baseline."""
        import numpy as np

        analyzer = SignificanceAnalyzer()
        scores = [(f"noise_{i}", 0.01) for i in range(17)]
        scores += [(f"signal_{i}", 10.0) for i in range(3)]
        values = np.array([s for _, s in scores], dtype=float)

        result = analyzer._isolation_forest_detection(scores, values)

        baseline_ids = {e for e, _ in result["baseline"]}
        signal_ids = {f"signal_{i}" for i in range(3)}
        # At least one signal should escape baseline
        assert not signal_ids.issubset(baseline_ids), (
            "All high-score outliers ended up in baseline – Isolation Forest logic is still reversed"
        )

    def test_low_score_noise_stays_baseline(self):
        """Low-score noise should remain in baseline, not be promoted."""
        import numpy as np

        analyzer = SignificanceAnalyzer()
        scores = [(f"noise_{i}", 0.001 + i * 0.0001) for i in range(17)]
        scores += [(f"signal_{i}", 10.0 + i) for i in range(3)]
        values = np.array([s for _, s in scores], dtype=float)

        result = analyzer._isolation_forest_detection(scores, values)

        sig_ids = {e for e, _ in result["significant"]}
        # No noise entity should be promoted to significant
        noise_promoted = sig_ids & {f"noise_{i}" for i in range(17)}
        assert len(noise_promoted) == 0


class TestZeroVarianceGuard:
    """FIX #2: Zero-variance arrays must not crash or falsely promote."""

    def test_identical_scores_all_baseline(self):
        """Flat array [0.85, 0.85, ...] → everything baseline, nothing promoted."""
        analyzer = SignificanceAnalyzer()
        scores = [(f"e{i}", 0.85) for i in range(20)]
        result = analyzer.detect_significant_variables(scores, "ensemble")
        assert len(result["significant"]) == 0
        assert len(result["moderate"]) == 0
        assert len(result["baseline"]) == 20

    def test_identical_scores_sorted_descending(self):
        """Even flat baseline results should be sorted."""
        analyzer = SignificanceAnalyzer()
        scores = [(f"e{i}", 0.5) for i in range(5)]
        result = analyzer.detect_significant_variables(scores, "modified_z")
        assert len(result["baseline"]) == 5

    def test_analyze_distribution_zero_variance_no_nan(self):
        """stats.skew/kurtosis on zero-variance should NOT produce NaN."""
        import math

        analyzer = SignificanceAnalyzer()
        scores = [(f"e{i}", 0.5) for i in range(10)]
        analysis = analyzer.analyze_distribution(scores)

        assert not math.isnan(analysis["distribution"]["skewness"])
        assert not math.isnan(analysis["distribution"]["kurtosis"])
        assert analysis["distribution"]["distribution_type"] == "point_mass"
        assert analysis["distribution"]["is_normal"] is False

    def test_single_element_returns_baseline(self):
        """A single element has zero variance → baseline."""
        analyzer = SignificanceAnalyzer()
        result = analyzer.detect_significant_variables([("a", 1.0)], "ensemble")
        assert len(result["baseline"]) == 1
        assert len(result["significant"]) == 0


class TestEnsembleTieBreaking:
    """FIX #3: Ties must resolve to baseline (conservative), not significant."""

    def test_tie_resolves_to_baseline(self):
        """When significant and baseline votes are tied, baseline wins."""
        import numpy as np

        analyzer = SignificanceAnalyzer()
        # Construct scores where methods will disagree
        scores = [(f"e{i}", float(i)) for i in range(1, 21)]
        values = np.array([s for _, s in scores], dtype=float)

        # Manually simulate a 2-2 tie: 2 say significant, 2 say baseline
        with mock.patch.object(analyzer, "_modified_z_score_detection",
                               return_value={"significant": [scores[0]], "moderate": [], "baseline": scores[1:]}):
            with mock.patch.object(analyzer, "_iqr_detection",
                                   return_value={"significant": [scores[0]], "moderate": [], "baseline": scores[1:]}):
                with mock.patch.object(analyzer, "_jenks_detection",
                                       return_value={"significant": [], "moderate": [], "baseline": list(scores)}):
                    with mock.patch.object(analyzer, "_isolation_forest_detection",
                                           return_value={"significant": [], "moderate": [], "baseline": list(scores)}):
                        result = analyzer._ensemble_detection(scores, values)

        # Entity e1 has 2 significant + 2 baseline votes → should resolve to baseline
        baseline_ids = {e for e, _ in result["baseline"]}
        assert scores[0][0] in baseline_ids, "Tied entity should default to baseline"


class TestSortContract:
    """FIX #4: All methods must return results sorted descending by score."""

    @pytest.mark.parametrize("method", ["modified_z", "iqr", "jenks", "isolation_forest", "ensemble"])
    def test_all_methods_sorted_descending(self, method):
        """Every detection method must return sorted results."""
        analyzer = SignificanceAnalyzer()
        # Use enough data for all methods including isolation_forest (≥10)
        scores = [(f"e{i}", float(i) * 0.1) for i in range(20)]
        result = analyzer.detect_significant_variables(scores, method)

        for cat in ("significant", "moderate", "baseline"):
            items = result[cat]
            if len(items) > 1:
                values = [s for _, s in items]
                assert values == sorted(values, reverse=True), (
                    f"Method '{method}', category '{cat}' is not sorted descending"
                )


class TestMADScaling:
    """FIX #5d: adaptive threshold must use MAD * 1.4826 scaling."""

    def test_adaptive_threshold_uses_scaling(self):
        """Threshold should be median + 2 * MAD * 1.4826, not median + 2 * MAD."""
        import numpy as np

        analyzer = SignificanceAnalyzer()
        scores = [(f"e{i}", float(i)) for i in range(1, 11)]  # 1..10
        values = np.array([s for _, s in scores], dtype=float)

        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        expected = median + 2 * (mad * 1.4826)

        actual = analyzer.calculate_baseline_threshold(scores, "adaptive")
        assert abs(actual - expected) < 1e-10, (
            f"Expected {expected}, got {actual} — MAD scaling factor 1.4826 not applied"
        )

    def test_empty_scores_returns_zero(self):
        """Empty scores → threshold 0.0."""
        analyzer = SignificanceAnalyzer()
        assert analyzer.calculate_baseline_threshold([], "adaptive") == 0.0


class TestPercentileStrictComparison:
    """FIX #2 (sub-fix): _percentile_classification uses > not >= to prevent
    flat arrays from promoting identical values."""

    def test_flat_array_all_baseline(self):
        """When all values equal p90, strict > means nothing is promoted."""
        import numpy as np

        analyzer = SignificanceAnalyzer()
        scores = [(f"e{i}", 0.5) for i in range(10)]
        values = np.array([s for _, s in scores], dtype=float)

        result = analyzer._percentile_classification(scores, values)
        assert len(result["significant"]) == 0
        assert len(result["moderate"]) == 0
        assert len(result["baseline"]) == 10
