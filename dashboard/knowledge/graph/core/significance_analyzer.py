"""
Statistical significance analyzer for triplet scores.

Implements multiple algorithms to identify significant variables and establish
baselines, allowing the retriever to cut non-relevant baseline triplets from
the final result set.

Algorithms:
1. Modified Z-Score (robust to outliers via MAD)
2. Interquartile Range (IQR) method
3. Jenks Natural Breaks (approximated via K-Means clustering)
4. Isolation Forest (ML-based anomaly detection)
5. Ensemble (majority-vote across all methods)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports – scipy / sklearn are available in the env but we avoid loading
# them at module-import time so the rest of the graph package stays lightweight.
# ---------------------------------------------------------------------------


def _numpy():
    import numpy as np  # noqa: WPS433

    return np


def _scipy_stats():
    from scipy import stats  # noqa: WPS433

    return stats


def _kmeans():
    from sklearn.cluster import KMeans  # noqa: WPS433

    return KMeans


def _isolation_forest():
    from sklearn.ensemble import IsolationForest  # noqa: WPS433

    return IsolationForest


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class SignificanceAnalyzer:
    """Advanced statistical analyzer for determining significant variables in
    triplet scoring.

    Three output categories:
    - **significant** – clearly above baseline, boosted during scoring.
    - **moderate** – marginal, kept but not boosted.
    - **baseline** – noise / irrelevant, candidates for removal or dampening.
    """

    def __init__(self, significance_threshold: float = 0.05):
        self.significance_threshold = significance_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_distribution(self, scores: List[Tuple[str, float]]) -> Dict[str, Any]:
        """Comprehensive analysis of score distribution.

        Args:
            scores: List of ``(entity_id, score)`` tuples.

        Returns:
            Dictionary containing distribution statistics and insights.
        """
        if not scores:
            return {}

        np = _numpy()
        stats = _scipy_stats()

        values = np.array([s for _, s in scores], dtype=float)
        entities = [e for e, _ in scores]

        q25 = float(np.percentile(values, 25))
        q75 = float(np.percentile(values, 75))
        std_val = float(np.std(values))

        stats_summary = {
            "count": len(values),
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            "std": std_val,
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "q25": q25,
            "q75": q75,
            "iqr": q75 - q25,
        }

        # FIX #2: Guard against zero-variance throwing NaNs & RuntimeWarnings
        if std_val == 0.0:
            skewness, kurtosis_val = 0.0, 0.0
            is_normal = False
            dist_type = "point_mass"
        else:
            skewness = float(stats.skew(values))
            kurtosis_val = float(stats.kurtosis(values))
            is_normal = self._test_normality(values)
            dist_type = self._identify_distribution_type(skewness, kurtosis_val)

        distribution_info = {
            "skewness": skewness,
            "kurtosis": kurtosis_val,
            "is_normal": is_normal,
            "distribution_type": dist_type,
        }

        return {
            "statistics": stats_summary,
            "distribution": distribution_info,
            "raw_data": list(zip(entities, values.tolist())),
        }

    def detect_significant_variables(
        self,
        scores: List[Tuple[str, float]],
        method: str = "ensemble",
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Detect significant variables using specified method.

        Args:
            scores: List of ``(entity_id, score)`` tuples.
            method: Detection method –
                ``'modified_z'``, ``'iqr'``, ``'jenks'``,
                ``'isolation_forest'``, or ``'ensemble'`` (default).

        Returns:
            Dictionary with ``'significant'``, ``'moderate'``, ``'baseline'``
            categories, each a list of ``(entity_id, score)`` tuples sorted by
            score descending.
        """
        empty: Dict[str, List[Tuple[str, float]]] = {
            "significant": [],
            "moderate": [],
            "baseline": [],
        }
        if not scores:
            return empty

        np = _numpy()
        # FIX #5a: Extract numpy array exactly once and pass it down
        values = np.array([s for _, s in scores], dtype=float)

        # FIX #2: Fast path – if variance is zero, everything is safely baseline
        if len(scores) < 2 or np.std(values) == 0.0:
            empty["baseline"] = sorted(scores, key=lambda x: x[1], reverse=True)
            return empty

        dispatch = {
            "ensemble": self._ensemble_detection,
            "modified_z": self._modified_z_score_detection,
            "iqr": self._iqr_detection,
            "jenks": self._jenks_detection,
            "isolation_forest": self._isolation_forest_detection,
        }
        fn = dispatch.get(method)
        if fn is None:
            raise ValueError(f"Unknown method: {method}")

        result = fn(scores, values)

        # FIX #4: Enforce docstring contract – sort all categories descending globally
        for cat in result:
            result[cat].sort(key=lambda x: x[1], reverse=True)

        return result

    def calculate_baseline_threshold(
        self,
        scores: List[Tuple[str, float]],
        method: str = "adaptive",
    ) -> float:
        """Calculate dynamic baseline threshold.

        Args:
            scores: List of ``(entity_id, score)`` tuples.
            method: ``'adaptive'`` (median + 2·MAD·1.4826), ``'statistical'``
                (mean + 2·std), or ``'percentile'`` (75th percentile).

        Returns:
            Baseline threshold value.
        """
        if not scores:
            return 0.0

        np = _numpy()
        values = np.array([s for _, s in scores], dtype=float)

        if method == "adaptive":
            median = float(np.median(values))
            mad = float(np.median(np.abs(values - median)))
            # FIX #5d: Standard statistical scaling – MAD * 1.4826 ≈ Std Dev
            if mad == 0.0:
                mad = float(np.std(values) * 0.6745)
            return float(median + 2 * (mad * 1.4826))
        elif method == "statistical":
            return float(np.mean(values) + 2 * np.std(values))
        elif method == "percentile":
            return float(np.percentile(values, 75))
        else:
            raise ValueError(f"Unknown threshold method: {method}")

    def get_recommendations(self, scores: List[Tuple[str, float]]) -> Dict[str, Any]:
        """Comprehensive recommendations for the scoring system."""
        analysis = self.analyze_distribution(scores)
        significant_vars = self.detect_significant_variables(scores, "ensemble")
        baseline_threshold = self.calculate_baseline_threshold(scores, "adaptive")

        recommendations: List[str] = []

        if analysis and analysis["distribution"]["skewness"] > 1:
            recommendations.append(
                "Distribution is right-skewed. Consider log transformation for better analysis."
            )

        sig_count = len(significant_vars["significant"])
        total = len(scores)

        if total > 0:
            ratio = sig_count / total
            if ratio > 0.2:
                recommendations.append(
                    "High proportion of significant variables detected. "
                    "Consider tightening thresholds."
                )
            elif ratio < 0.05:
                recommendations.append(
                    "Very few significant variables detected. "
                    "Consider loosening thresholds or checking data quality."
                )

        return {
            "distribution_analysis": analysis,
            "significant_variables": significant_vars,
            "baseline_threshold": baseline_threshold,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Detection methods (private)
    # ------------------------------------------------------------------

    def _ensemble_detection(
        self, scores: List[Tuple[str, float]], values: Any
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Majority-vote across all individual detection methods."""
        methods = ["modified_z", "iqr", "jenks", "isolation_forest"]
        results: Dict[str, Dict[str, List[Tuple[str, float]]]] = {}

        dispatch = {
            "modified_z": self._modified_z_score_detection,
            "iqr": self._iqr_detection,
            "jenks": self._jenks_detection,
            "isolation_forest": self._isolation_forest_detection,
        }

        for m in methods:
            try:
                results[m] = dispatch[m](scores, values)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Method %s failed: %s", m, exc)

        if not results:
            return {"significant": [], "moderate": [], "baseline": list(scores)}

        # Tally votes per entity
        entity_votes: Dict[str, Dict[str, int]] = {}
        for method_result in results.values():
            for category, items in method_result.items():
                for entity, _ in items:
                    entity_votes.setdefault(entity, {"significant": 0, "moderate": 0, "baseline": 0})
                    entity_votes[entity][category] += 1

        final: Dict[str, List[Tuple[str, float]]] = {
            "significant": [],
            "moderate": [],
            "baseline": [],
        }

        # FIX #3: Conservative tie-breaking – ties default to baseline (noise reduction)
        priority = {"baseline": 3, "moderate": 2, "significant": 1}

        for entity, score in scores:
            votes = entity_votes.get(entity, {"significant": 0, "moderate": 0, "baseline": 0})
            category = max(votes.keys(), key=lambda c: (votes[c], priority[c]))
            final[category].append((entity, score))

        # NOTE: Sorting is now handled globally in detect_significant_variables
        return final

    def _modified_z_score_detection(
        self, scores: List[Tuple[str, float]], values: Any
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Modified Z-score using Median Absolute Deviation (robust to outliers)."""
        import numpy as np

        median = np.median(values)
        mad = np.median(np.abs(values - median))

        if mad == 0:
            mad = np.std(values) * 0.6745  # fallback

        # If still zero (all values identical), everything is baseline.
        if mad == 0:
            return {"significant": [], "moderate": [], "baseline": list(scores)}

        mod_z = 0.6745 * (values - median) / mad

        SIGNIFICANT = 2.5
        MODERATE = 1.5

        result: Dict[str, List[Tuple[str, float]]] = {
            "significant": [],
            "moderate": [],
            "baseline": [],
        }
        for i, (entity, score) in enumerate(scores):
            z = mod_z[i]
            if z > SIGNIFICANT:
                result["significant"].append((entity, score))
            elif z > MODERATE:
                result["moderate"].append((entity, score))
            else:
                result["baseline"].append((entity, score))
        return result

    def _iqr_detection(
        self, scores: List[Tuple[str, float]], values: Any
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Interquartile Range method."""
        import numpy as np

        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1

        sig_threshold = q3 + 1.5 * iqr
        mod_threshold = q3 + 0.5 * iqr

        result: Dict[str, List[Tuple[str, float]]] = {
            "significant": [],
            "moderate": [],
            "baseline": [],
        }
        for entity, score in scores:
            if score > sig_threshold:
                result["significant"].append((entity, score))
            elif score > mod_threshold:
                result["moderate"].append((entity, score))
            else:
                result["baseline"].append((entity, score))
        return result

    def _jenks_detection(
        self, scores: List[Tuple[str, float]], values: Any
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Jenks Natural Breaks approximated via K-Means (3 clusters)."""
        import numpy as np

        KMeans = _kmeans()

        # Need ≥3 data points AND ≥3 distinct values for 3-cluster K-Means.
        n_distinct = len(np.unique(values))
        if len(values) < 3 or n_distinct < 3:
            return self._percentile_classification(scores, values)

        try:
            # FIX #5b: n_init="auto" avoids deprecation warnings in modern sklearn
            km = KMeans(n_clusters=3, random_state=42, n_init="auto")
            clusters = km.fit_predict(values.reshape(-1, 1))

            centers = [(i, c[0]) for i, c in enumerate(km.cluster_centers_)]
            centers.sort(key=lambda x: x[1], reverse=True)

            cluster_map = {
                centers[0][0]: "significant",
                centers[1][0]: "moderate",
                centers[2][0]: "baseline",
            }

            result: Dict[str, List[Tuple[str, float]]] = {
                "significant": [],
                "moderate": [],
                "baseline": [],
            }
            for i, (entity, score) in enumerate(scores):
                result[cluster_map[clusters[i]]].append((entity, score))
            return result

        except Exception as exc:  # noqa: BLE001
            logger.warning("Jenks clustering failed: %s", exc)
            return self._percentile_classification(scores, values)

    def _isolation_forest_detection(
        self, scores: List[Tuple[str, float]], values: Any
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Isolation Forest for anomaly detection.

        FIX #1: scikit-learn's decision_function() returns LOW/NEGATIVE values
        for anomalies and HIGH/POSITIVE values for normal inliers.  We want to
        identify high-scoring *outliers* as significant, so we look for items
        with LOW anomaly scores (isolated) AND original scores above the median.
        """
        import numpy as np

        if len(scores) < 10:
            return self._percentile_classification(scores, values)

        IsoForest = _isolation_forest()
        val_2d = values.reshape(-1, 1)

        try:
            iso = IsoForest(contamination=0.1, random_state=42)
            iso.fit(val_2d)

            # CRITICAL FIX: Low anomaly_scores = anomalies (isolated points)
            anomaly_scores = iso.decision_function(val_2d)

            p10 = np.percentile(anomaly_scores, 10)
            p30 = np.percentile(anomaly_scores, 30)
            median_score = float(np.median(values))

            result: Dict[str, List[Tuple[str, float]]] = {
                "significant": [],
                "moderate": [],
                "baseline": [],
            }
            for i, (entity, score) in enumerate(scores):
                a = anomaly_scores[i]

                # We specifically want high-scoring isolated points,
                # avoiding uniquely low points.
                if a <= p10 and score > median_score:
                    result["significant"].append((entity, score))
                elif a <= p30 and score > median_score:
                    result["moderate"].append((entity, score))
                else:
                    result["baseline"].append((entity, score))
            return result

        except Exception as exc:  # noqa: BLE001
            logger.warning("Isolation Forest failed: %s", exc)
            return self._percentile_classification(scores, values)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _percentile_classification(
        self, scores: List[Tuple[str, float]], values: Any
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Fallback percentile-based classification (P90 / P70 splits)."""
        import numpy as np

        p90 = np.percentile(values, 90)
        p70 = np.percentile(values, 70)

        result: Dict[str, List[Tuple[str, float]]] = {
            "significant": [],
            "moderate": [],
            "baseline": [],
        }
        for entity, score in scores:
            # FIX #2: Use strict `>` to prevent flat arrays from being promoted
            if score > p90:
                result["significant"].append((entity, score))
            elif score > p70:
                result["moderate"].append((entity, score))
            else:
                result["baseline"].append((entity, score))
        return result

    def _test_normality(self, values: Any) -> bool:
        """Shapiro-Wilk normality test (p > 0.05 ⇒ approximately normal)."""
        if len(values) < 8:
            return False

        import numpy as np

        stats = _scipy_stats()

        # FIX #5c: Prevent SciPy UserWarning log spam on huge subgraphs
        if len(values) > 5000:
            values = np.random.choice(values, 5000, replace=False)

        _, p_value = stats.shapiro(values)
        return p_value > self.significance_threshold

    @staticmethod
    def _identify_distribution_type(skewness: float, kurtosis: float) -> str:
        """Heuristic distribution classification."""
        if abs(skewness) <= 0.5 and abs(kurtosis) <= 3:
            return "approximately_normal"
        elif skewness > 0.5:
            return "right_skewed"
        elif skewness < -0.5:
            return "left_skewed"
        elif kurtosis > 3:
            return "heavy_tailed"
        return "unknown"
