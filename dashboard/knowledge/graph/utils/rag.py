"""RAG-related helpers: entity/relationship parsers, prompt builders, triplet
to-NodeWithScore converters.

No `app.*` references. Heavy LLM/embedding stuff lives in
:mod:`dashboard.knowledge.llm` and :mod:`dashboard.knowledge.embeddings`.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Optional

# llama-index is a hard dep of the graph package — see requirements.txt.
from llama_index.core.graph_stores.types import Triplet
from llama_index.core.schema import (
    NodeRelationship,
    NodeWithScore,
    RelatedNodeInfo,
    TextNode,
)

from dashboard.knowledge.graph.prompt import (
    _OUTPUT_KP,
    JSON_OUTPUT_FORMAT_TEMPLATE,
    KG_DOMAIN_FORMAT,
    KG_EXAMPLE,
    KG_EXAMPLE_JSON,
    KG_EXTRACTION_STEPS,
    KG_EXTRACTION_STEPS_JSON,
    KG_GOAL,
    KG_SYSTEM_ROLE,
    KG_TRIPLET_EXTRACT_TMPL,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & patterns
# ---------------------------------------------------------------------------

TRIPLET_SOURCE_KEY = "source"

entity_pattern = r'\("entity"\$\$\$\$(.*?)\$\$\$\$(.*?)\$\$\$\$(.*?)\)'
relationship_pattern = r'\("relationship"\$\$\$\$(.*?)\$\$\$\$(.*?)\$\$\$\$(.*?)\$\$\$\$(.*?)\)'


# ---------------------------------------------------------------------------
# Triplets → NodeWithScore
# ---------------------------------------------------------------------------


def _get_nodes_from_triplets(
    graph: Any,  # networkx.DiGraph (lazy-imported by caller)
    triplets: List[Triplet],
    scores: Optional[List[float]] = None,
) -> List[NodeWithScore]:
    """Insert triplets into a NetworkX directed graph and return NodeWithScore objects.

    Args:
        graph: NetworkX directed graph to insert triplets into.
        triplets: List of triplets to process.
        scores: Optional scores for each triplet.

    Returns:
        List of NodeWithScore wrapping a simplified triplet representation.
    """
    results: List[NodeWithScore] = []

    for i, triplet in enumerate(triplets):
        source = triplet[0]
        relation = triplet[1]
        target = triplet[2]

        def build_node_label(node):
            if node.label != "text_chunk":
                entity_desc = node.properties.get("entity_description", "")
                return f"({node.label}: {entity_desc})" if entity_desc else node.label
            return getattr(node, "text", node.id)

        current_score = 1.0 if scores is None else scores[i]

        def add_or_update_node(node_id, label, properties, score_contribution):
            if node_id in graph:
                existing_data = graph.nodes[node_id]
                existing_score = existing_data.get("score", 0.0)
                new_score = existing_score + score_contribution
                merged = {**existing_data, **properties, "label": label, "score": new_score}
                graph.nodes[node_id].update(merged)
            else:
                graph.add_node(node_id, label=label, score=score_contribution, **properties)

        source_label = build_node_label(source)
        target_label = build_node_label(target)

        add_or_update_node(source.id, source_label, source.properties, current_score)
        add_or_update_node(target.id, target_label, target.properties, current_score)

        relationship_desc = relation.properties.get("relationship_description", "") or ""
        edge_data = {
            "label": relation.label,
            "relationship_description": relationship_desc,
            **relation.properties,
        }
        graph.add_edge(source.id, target.id, **edge_data)

        relationship_text = f"{relation.label}"
        if relationship_desc.strip():
            relationship_text += f"({relationship_desc})"

        text = f"{source.id} -> {relationship_text} -> {target.id}"
        triplet_metadata = {
            "triplet_index": i,
            "source_id": source.id,
            "target_id": target.id,
        }

        relationships = {}
        source_id = source.properties.get(TRIPLET_SOURCE_KEY, None)
        if source_id is not None:
            relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=str(source_id))

        results.append(
            NodeWithScore(
                node=TextNode(
                    text=text,
                    relationships=relationships,
                    id_=f"{source.id}_{target.id}",
                    metadata=triplet_metadata,
                ),
                score=1.0 if scores is None else scores[i],
            )
        )

    return results


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def extract_KP_fn(extend_format: str, language: str = "English"):
    """Generate knowledge-extraction prompt using the legacy $$$ format."""
    return (
        KG_TRIPLET_EXTRACT_TMPL.format(
            goal=KG_GOAL,
            system_role=KG_SYSTEM_ROLE,
            extraction_steps=KG_EXTRACTION_STEPS.format(language=language.upper()),
            language=language.upper(),
        ),
        _OUTPUT_KP,
        KG_DOMAIN_FORMAT.format(
            example=KG_EXAMPLE,
            knowledge_format=extend_format,
            language=language.upper(),
        ),
    )


def extract_KP_json_fn(extend_format: str, language: str = "English", num_data_points: int = 3):
    """Generate knowledge-extraction prompt using JSON format."""
    return (
        KG_TRIPLET_EXTRACT_TMPL.format(
            goal=KG_GOAL,
            system_role=KG_SYSTEM_ROLE,
            extraction_steps=KG_EXTRACTION_STEPS_JSON.format(language=language.upper()),
            language=language.upper(),
        ),
        _OUTPUT_KP,
        KG_DOMAIN_FORMAT.format(
            example=KG_EXAMPLE_JSON,
            knowledge_format=extend_format,
            language=language.upper(),
        )
        + JSON_OUTPUT_FORMAT_TEMPLATE,
    )


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------


def parse_fn(response_str: str) -> Any:
    """Parse legacy $$$ format response into (entities, relationships) tuples."""
    entities = re.findall(entity_pattern, response_str)
    relationships = re.findall(relationship_pattern, response_str)
    return entities, relationships


def parse_json_fn(response_str: str) -> Any:
    """Parse JSON-format response into (entities, relationships) lists."""
    try:
        if response_str.strip().startswith("["):
            data = json.loads(response_str)
            if isinstance(data, list):
                entities: list = []
                relationships: list = []
                for item in data:
                    if "entities" in item:
                        entities.extend(item["entities"])
                    if "relationships" in item:
                        relationships.extend(item["relationships"])
                return entities, relationships
        elif response_str.strip().startswith("{"):
            data = json.loads(response_str)
            return data.get("entities", []), data.get("relationships", [])
        else:
            json_match = re.search(r"(\[.*\]|\{.*\})", response_str, re.DOTALL)
            if json_match:
                return parse_json_fn(json_match.group(1))
            return [], []
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse JSON response: %s", exc)
        return [], []
