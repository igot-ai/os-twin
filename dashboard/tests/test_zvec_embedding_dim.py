"""Unit tests for OSTwinStore._embedding_dim attribute.

Verifies that embedding dimension is fixed from OSTWIN_EMBEDDING_DIM env var
and cannot be changed dynamically — all stores and subsystems share the same
dimension to prevent vector collection conflicts.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_store(tmp_path: Path, embedder=None):
    from dashboard.zvec_store import EMBEDDING_DIM, OSTwinStore

    store = OSTwinStore.__new__(OSTwinStore)
    store.warrooms_dir = tmp_path / "war-rooms"
    store.agents_dir = None
    store._embedder = embedder
    store._embedding_dim = EMBEDDING_DIM
    store.zvec_dir = tmp_path / ".zvec"
    store._messages = None
    store._metadata = None
    store._plans = None
    store._epics = None
    store._skills = None
    store._versions = None
    store._changes = None
    store._roles = None
    store._embed_fn = None
    store._embed_available = None
    store._embed_cache_path = store.zvec_dir / "embedding_cache.json"
    store._embed_cache = {}
    return store


class TestEmbeddingDimFixed:
    def test_default_dim_matches_env_var(self, tmp_path):
        """OSTwinStore._embedding_dim must match OSTWIN_EMBEDDING_DIM (1024)."""
        from dashboard.zvec_store import EMBEDDING_DIM, OSTwinStore

        with (
            patch("zvec.init"),
            patch.object(OSTwinStore, "_get_embed_fn", return_value=None),
            patch.object(OSTwinStore, "migrate_collections", return_value={}),
            patch.object(OSTwinStore, "_open_or_create_messages", return_value=MagicMock()),
            patch.object(OSTwinStore, "_open_or_create_metadata", return_value=MagicMock()),
            patch.object(OSTwinStore, "_open_or_create_plans", return_value=MagicMock()),
            patch.object(OSTwinStore, "_open_or_create_epics", return_value=MagicMock()),
            patch.object(OSTwinStore, "_open_or_create_skills", return_value=MagicMock()),
            patch.object(OSTwinStore, "_open_or_create_versions", return_value=MagicMock()),
            patch.object(OSTwinStore, "_open_or_create_changes", return_value=MagicMock()),
            patch.object(OSTwinStore, "_open_or_create_roles", return_value=MagicMock()),
        ):
            store = OSTwinStore(warrooms_dir=tmp_path / "wr")

        assert store._embedding_dim == EMBEDDING_DIM == 1024

    def test_ensure_collections_uses_fixed_dimension(self, tmp_path):
        """ensure_collections() must set _embedding_dim from the env-var constant."""
        from dashboard.zvec_store import EMBEDDING_DIM

        store = _make_store(tmp_path)

        with (
            patch("zvec.init"),
            patch.object(store, "_get_embed_fn", return_value=None),
            patch.object(store, "migrate_collections", return_value={}),
            patch.object(store, "_open_or_create_messages", return_value=MagicMock()),
            patch.object(store, "_open_or_create_metadata", return_value=MagicMock()),
            patch.object(store, "_open_or_create_plans", return_value=MagicMock()),
            patch.object(store, "_open_or_create_epics", return_value=MagicMock()),
            patch.object(store, "_open_or_create_skills", return_value=MagicMock()),
            patch.object(store, "_open_or_create_versions", return_value=MagicMock()),
            patch.object(store, "_open_or_create_changes", return_value=MagicMock()),
            patch.object(store, "_open_or_create_roles", return_value=MagicMock()),
        ):
            store.ensure_collections()

        assert store._embedding_dim == EMBEDDING_DIM == 1024

    def test_two_stores_share_same_dimension(self, tmp_path):
        """Two OSTwinStore instances must share the same fixed dimension."""
        store_a = _make_store(tmp_path / "a")
        store_b = _make_store(tmp_path / "b")

        assert store_a._embedding_dim == store_b._embedding_dim == 1024

    def test_global_not_mutated(self, tmp_path):
        """The module-level EMBEDDING_DIM must not be mutated by ensure_collections."""
        from dashboard import zvec_store as zs
        dim_before = zs.EMBEDDING_DIM

        store = _make_store(tmp_path)
        with (
            patch("zvec.init"),
            patch.object(store, "_get_embed_fn", return_value=None),
            patch.object(store, "migrate_collections", return_value={}),
            patch.object(store, "_open_or_create_messages", return_value=MagicMock()),
            patch.object(store, "_open_or_create_metadata", return_value=MagicMock()),
            patch.object(store, "_open_or_create_plans", return_value=MagicMock()),
            patch.object(store, "_open_or_create_epics", return_value=MagicMock()),
            patch.object(store, "_open_or_create_skills", return_value=MagicMock()),
            patch.object(store, "_open_or_create_versions", return_value=MagicMock()),
            patch.object(store, "_open_or_create_changes", return_value=MagicMock()),
            patch.object(store, "_open_or_create_roles", return_value=MagicMock()),
        ):
            store.ensure_collections()

        assert zs.EMBEDDING_DIM == dim_before == 1024
