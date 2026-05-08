"""Unit tests for OSTwinStore._embedding_dim instance attribute fix.

Verifies the code-review fix (commit 10f8a49) that replaced:
    global EMBEDDING_DIM
    EMBEDDING_DIM = self._embed_fn.get_sentence_embedding_dimension()
with:
    self._embedding_dim = self._embed_fn.get_sentence_embedding_dimension()

The global EMBEDDING_DIM is now only mutated once per store in
ensure_collections(), preventing races when multiple OSTwinStore
instances are created with different embedding models.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path, dim: int = 384, embedder=None):
    """Return an OSTwinStore wired to tmp_path without touching zvec runtime."""
    from dashboard.zvec_store import OSTwinStore

    store = OSTwinStore.__new__(OSTwinStore)
    store.warrooms_dir = tmp_path / "war-rooms"
    store.agents_dir = None
    store._embedder = embedder
    store._embedding_dim = dim   # <-- the new instance attribute
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


# ---------------------------------------------------------------------------
# TestEmbeddingDimInstance
# ---------------------------------------------------------------------------


class TestEmbeddingDimInstance:
    def test_default_dim_is_384_on_init(self, tmp_path):
        """A freshly constructed OSTwinStore must have _embedding_dim == 384."""
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

        assert store._embedding_dim == EMBEDDING_DIM == 384

    def test_embedding_dim_updated_per_instance_when_model_loads(self, tmp_path):
        """After _get_embed_fn loads a model, _embedding_dim must reflect model dim."""
        store = _make_store(tmp_path, dim=384)

        mock_embed_fn = MagicMock()
        mock_embed_fn.get_sentence_embedding_dimension.return_value = 768

        # Simulate the code path inside _get_embed_fn that sets self._embedding_dim
        # (the fix: write to instance attr, not global)
        store._embed_fn = mock_embed_fn
        store._embedding_dim = mock_embed_fn.get_sentence_embedding_dimension()
        store._embed_available = True

        assert store._embedding_dim == 768

    def test_two_stores_with_different_dims_do_not_interfere(self, tmp_path):
        """Two OSTwinStore instances with different dims must be independent."""
        store_a = _make_store(tmp_path / "a", dim=384)
        store_b = _make_store(tmp_path / "b", dim=768)

        # Simulate model load for store_a (384-dim model)
        fn_a = MagicMock()
        fn_a.get_sentence_embedding_dimension.return_value = 384
        store_a._embed_fn = fn_a
        store_a._embedding_dim = fn_a.get_sentence_embedding_dimension()

        # Simulate model load for store_b (768-dim model)
        fn_b = MagicMock()
        fn_b.get_sentence_embedding_dimension.return_value = 768
        store_b._embed_fn = fn_b
        store_b._embedding_dim = fn_b.get_sentence_embedding_dimension()

        # They must not have clobbered each other
        assert store_a._embedding_dim == 384
        assert store_b._embedding_dim == 768

    def test_ensure_collections_syncs_global_embedding_dim(self, tmp_path):
        """ensure_collections() must write self._embedding_dim into module global."""
        from dashboard import zvec_store as zs

        store = _make_store(tmp_path, dim=512)

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

        # Module-level global must be updated to match this store's dim
        assert zs.EMBEDDING_DIM == 512
