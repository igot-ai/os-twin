"""EPIC-002 — namespace lifecycle tests.

Covers:

- ID validation (ADR-12 regex)
- create / get / list / delete happy paths and edge cases
- Atomic manifest writes (survive simulated crash)
- Manifest round-trip (datetime serialization)
- Per-namespace path isolation
- Concurrent create — only one wins
- Kuzu cache eviction on delete (immediate re-create works)
- Per-namespace Kuzu / Chroma path resolution
- :class:`KnowledgeService` lifecycle delegation + EPIC-003/004 stubs raise
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pytest

from dashboard.knowledge.namespace import (
    MAX_IMPORTS_PER_MANIFEST,
    ImportRecord,
    InvalidNamespaceIdError,
    NamespaceExistsError,
    NamespaceManager,
    NamespaceMeta,
    NamespaceNotFoundError,
    NamespaceStats,
)
from dashboard.knowledge.service import KnowledgeService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_kb(tmp_path: Path) -> Path:
    """Isolated knowledge-base root per test.

    We pass ``base_dir=tmp_kb`` to NamespaceManager directly rather than
    monkeypatching env, because ``config.KNOWLEDGE_DIR`` is computed at module
    import time — too late to override here.
    """
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    return kb


@pytest.fixture(autouse=True)
def _clear_kuzu_cache() -> Iterator[None]:
    """Wipe the Kuzu DB cache around every test to keep them hermetic."""
    from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

    KuzuLabelledPropertyGraph.kuzu_database_cache.clear()
    yield
    KuzuLabelledPropertyGraph.kuzu_database_cache.clear()


# ---------------------------------------------------------------------------
# 1) validate_id — ADR-12 regex
# ---------------------------------------------------------------------------


def test_validate_id_accepts_good_names() -> None:
    good = [
        "a",
        "0",
        "abc",
        "test-ns",
        "test_ns",
        "abc-123_def",
        "x" * 64,  # exactly the 64-char cap (1 + 63)
        "0abc",
        "9zzz",
    ]
    for name in good:
        assert NamespaceManager.validate_id(name), f"expected {name!r} to be valid"


def test_validate_id_rejects_bad_names() -> None:
    bad = [
        "",                # empty
        "Foo",             # uppercase
        "foo!",            # punctuation
        "foo bar",         # space
        "foo/bar",         # slash
        "../foo",          # path traversal
        "-foo",            # leading hyphen
        "_foo",            # leading underscore
        "foo.bar",         # dot
        "x" * 65,          # one over the cap
        None,              # not a string
        123,               # not a string
        b"bytes",          # not a str
    ]
    for name in bad:
        assert not NamespaceManager.validate_id(name), f"expected {name!r} to be invalid"


# ---------------------------------------------------------------------------
# 2) create
# ---------------------------------------------------------------------------


def test_create_namespace_creates_directory(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    meta = nm.create("test-ns")
    assert isinstance(meta, NamespaceMeta)
    assert meta.name == "test-ns"
    assert (tmp_kb / "test-ns").is_dir()




def test_create_namespace_default_language_english(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    meta = nm.create("ns1")
    assert meta.language == "English"


def test_create_duplicate_raises_NamespaceExistsError(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("dup")
    with pytest.raises(NamespaceExistsError):
        nm.create("dup")
    # And the original directory is still intact.
    assert (tmp_kb / "dup" / "manifest.json").exists()


def test_create_invalid_id_raises_InvalidNamespaceIdError(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    with pytest.raises(InvalidNamespaceIdError):
        nm.create("Bad Name!")
    # InvalidNamespaceIdError is also a ValueError (so API layers can map → 400).
    with pytest.raises(ValueError):
        nm.create("../escape")
    # No directory created on failure.
    assert not (tmp_kb / "Bad Name!").exists()


# ---------------------------------------------------------------------------
# 3) get
# ---------------------------------------------------------------------------


def test_get_existing_returns_meta(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    created = nm.create("ns-a", description="hello")
    fetched = nm.get("ns-a")
    assert fetched is not None
    assert fetched.name == "ns-a"
    assert fetched.description == "hello"
    # Round-trip equality on schema_version + name.
    assert fetched.schema_version == created.schema_version


def test_get_missing_returns_none(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    assert nm.get("does-not-exist") is None


def test_get_invalid_id_returns_none(tmp_kb: Path) -> None:
    """get() of an invalid id is a soft-miss, not a raise — same as a 404."""
    nm = NamespaceManager(base_dir=tmp_kb)
    assert nm.get("Bad Name!") is None


# ---------------------------------------------------------------------------
# 4) list
# ---------------------------------------------------------------------------


def test_list_empty_returns_empty(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    assert nm.list() == []


def test_list_returns_all_created(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("ns-a")
    nm.create("ns-b")
    nm.create("ns-c")
    names = sorted(m.name for m in nm.list())
    assert names == ["ns-a", "ns-b", "ns-c"]


def test_list_skips_unrelated_directories(tmp_kb: Path) -> None:
    """A bare directory without a manifest is skipped, not crashed on."""
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("real-ns")
    (tmp_kb / "stray-dir").mkdir()  # no manifest.json
    (tmp_kb / "Invalid Name").mkdir()  # invalid id → ignored
    names = sorted(m.name for m in nm.list())
    assert names == ["real-ns"]


# ---------------------------------------------------------------------------
# 5) delete
# ---------------------------------------------------------------------------


def test_delete_removes_directory_and_returns_true(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("to-delete")
    assert (tmp_kb / "to-delete").exists()
    assert nm.delete("to-delete") is True
    assert not (tmp_kb / "to-delete").exists()


def test_delete_missing_returns_false(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    assert nm.delete("nope") is False


def test_delete_invalid_id_returns_false(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    assert nm.delete("Bad Name!") is False


def test_delete_then_immediate_recreate_works(tmp_kb: Path) -> None:
    """Architect-mandated: recreate after delete must succeed cleanly.

    This catches dangling Kuzu file handles — the cache must be evicted before
    rmtree, so a second create() with the same name doesn't reuse a stale DB.
    """
    nm = NamespaceManager(base_dir=tmp_kb)
    m1 = nm.create("test-ns")

    # Touch the kuzu db so a connection is opened and cached.
    from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

    g = KuzuLabelledPropertyGraph.for_namespace("test-ns")
    # Force the cache to be populated (constructor already does this).
    cached_path = g._resolve_db_path()
    assert cached_path in KuzuLabelledPropertyGraph.kuzu_database_cache
    del g

    # Now delete the namespace.
    assert nm.delete("test-ns") is True
    assert not (tmp_kb / "test-ns").exists()
    # Cache eviction must have happened.
    assert cached_path not in KuzuLabelledPropertyGraph.kuzu_database_cache

    # Immediate re-create must succeed (no permission/lock errors).
    m2 = nm.create("test-ns")
    assert m2.created_at >= m1.created_at  # truly fresh manifest
    assert (tmp_kb / "test-ns" / "manifest.json").exists()


# ---------------------------------------------------------------------------
# 6) Manifest atomicity & round-trip
# ---------------------------------------------------------------------------


def test_manifest_atomic_write_survives_crash(
    tmp_kb: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If os.replace fails mid-write, the previous manifest must be intact.

    We let the first create() succeed, then break os.replace and attempt a
    write_manifest() — the second write should raise, but the original
    manifest on disk must be unchanged AND no leftover .tmp file remains.
    """
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("ns-x", description="original")
    original_text = (tmp_kb / "ns-x" / "manifest.json").read_text()

    # Patch os.replace inside the namespace module to always fail.
    import dashboard.knowledge.namespace as ns_mod

    def _boom(src, dst):
        raise OSError("simulated crash mid-write")

    monkeypatch.setattr(ns_mod.os, "replace", _boom)

    # Build a new meta and try to write it — must raise.
    meta = nm.get("ns-x")
    assert meta is not None
    meta.description = "MUTATED — should not land"
    with pytest.raises(OSError, match="simulated crash"):
        nm.write_manifest("ns-x", meta)

    # 1) Original manifest unchanged.
    assert (tmp_kb / "ns-x" / "manifest.json").read_text() == original_text

    # 2) No leftover .tmp files in the namespace dir.
    tmp_files = list((tmp_kb / "ns-x").glob(".manifest.*.tmp"))
    assert tmp_files == [], f"leftover temp files: {tmp_files}"


def test_manifest_roundtrip(tmp_kb: Path) -> None:
    """Write → read → write → read should yield equivalent NamespaceMeta."""
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("rt", language="Spanish", description="d1")
    m1 = nm.get("rt")
    assert m1 is not None

    # Mutate stats and write back.
    nm.update_stats("rt", chunks=5, entities=2)
    m2 = nm.get("rt")
    assert m2 is not None
    assert m2.stats.chunks == 5
    assert m2.stats.entities == 2
    assert m2.language == "Spanish"
    assert m2.description == "d1"
    assert m2.created_at == m1.created_at  # immutable
    assert m2.updated_at >= m1.updated_at  # bumped


# ---------------------------------------------------------------------------
# 7) Namespace isolation
# ---------------------------------------------------------------------------


def test_two_namespaces_isolated(tmp_kb: Path) -> None:
    """Two namespace directories must be siblings, not nested, and independent."""
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("ns-a", description="A")
    nm.create("ns-b", description="B")

    a_path = tmp_kb / "ns-a"
    b_path = tmp_kb / "ns-b"
    assert a_path.is_dir() and b_path.is_dir()
    # Siblings, not nested.
    assert a_path.parent == b_path.parent == tmp_kb

    # Mutating one's stats does NOT affect the other.
    nm.update_stats("ns-a", chunks=10)
    assert nm.get("ns-a").stats.chunks == 10
    assert nm.get("ns-b").stats.chunks == 0

    # Deleting one does NOT touch the other.
    nm.delete("ns-a")
    assert not a_path.exists()
    assert b_path.exists()
    assert nm.get("ns-b") is not None


def test_kuzu_path_uses_correct_per_namespace_path(tmp_kb: Path) -> None:
    """KuzuLabelledPropertyGraph.for_namespace must point at {kb}/{ns}/graph.db."""
    from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

    # Pre-create the namespace dir so the parent exists.
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("kuzu-ns")

    # We expect the resolved path to use the .db-suffix verbatim path —
    # but the *config* helper resolves to the real KNOWLEDGE_DIR (not tmp_kb)
    # because config is module-level. Instead check the new for_namespace
    # constructor wires the correct path STRUCTURE.
    from dashboard.knowledge.config import kuzu_db_path

    expected = kuzu_db_path("kuzu-ns")  # {KNOWLEDGE_DIR}/kuzu-ns/graph.db
    assert str(expected).endswith("kuzu-ns/graph.db") or str(expected).endswith(
        "kuzu-ns\\graph.db"
    )

    g = KuzuLabelledPropertyGraph.for_namespace("kuzu-ns")
    resolved = g._resolve_db_path()
    assert resolved.endswith("kuzu-ns/graph.db") or resolved.endswith("kuzu-ns\\graph.db")
    assert resolved == str(expected.resolve())


def test_kuzu_resolve_db_path_smart_handles_db_suffix(tmp_path: Path) -> None:
    """When database_path ends with .db it must be used verbatim."""
    from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

    explicit = tmp_path / "custom" / "myfile.db"
    g = KuzuLabelledPropertyGraph(
        index="some-ns",
        ws_id="some-ns",
        database_path=str(explicit),
    )
    assert g._resolve_db_path() == str(explicit.resolve())


def test_vector_path_uses_correct_per_namespace_path(tmp_kb: Path) -> None:
    """vector_dir(ns) must root vectors under ``{KNOWLEDGE_DIR}/{ns}/vectors/``.

    Post EPIC-003 v2: the on-disk directory is ``vectors/`` (zvec collection)
    not ``chroma/``. The deprecated ``chroma_dir`` alias still resolves to
    the new path; verifying both keeps back-compat callers honest.
    """
    from dashboard.knowledge.config import chroma_dir, vector_dir

    p = vector_dir("some-ns")
    assert str(p).endswith("some-ns/vectors") or str(p).endswith("some-ns\\vectors")

    # Deprecated alias still works.
    assert chroma_dir("some-ns") == vector_dir("some-ns")

    # init_vector_store_for_namespace was removed in EPIC-003 v2; importing
    # it must succeed (it's now a NotImplementedError stub) but calling it
    # must raise NotImplementedError pointing at the new API.
    from dashboard.knowledge.graph.core.storage import init_vector_store_for_namespace

    assert callable(init_vector_store_for_namespace)
    with pytest.raises(NotImplementedError, match="zvec"):
        init_vector_store_for_namespace("some-ns")


# ---------------------------------------------------------------------------
# 8) Concurrency
# ---------------------------------------------------------------------------


def test_concurrent_create_only_one_succeeds(tmp_kb: Path) -> None:
    """5 threads each call create('same') — exactly one returns a meta, the rest raise."""
    nm = NamespaceManager(base_dir=tmp_kb)
    successes: list[NamespaceMeta] = []
    failures: list[Exception] = []
    barrier = threading.Barrier(5)

    def worker():
        barrier.wait()
        try:
            successes.append(nm.create("same"))
        except NamespaceExistsError as e:
            failures.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(successes) == 1
    assert len(failures) == 4
    assert (tmp_kb / "same").is_dir()


def test_concurrent_update_stats_no_lost_updates(tmp_kb: Path) -> None:
    """20 concurrent +1 chunks updates → final counter is exactly 20."""
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("counter-ns")

    def bump():
        nm.update_stats("counter-ns", chunks=1)

    threads = [threading.Thread(target=bump) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    final = nm.get("counter-ns")
    assert final is not None
    assert final.stats.chunks == 20


# ---------------------------------------------------------------------------
# 9) ImportRecord append + cap
# ---------------------------------------------------------------------------


def test_append_import_records_persisted(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("ns-imp")
    rec = ImportRecord(
        folder_path="/tmp/foo",
        started_at=datetime.now(timezone.utc),
        status="completed",
        file_count=5,
    )
    nm.append_import("ns-imp", rec)
    fetched = nm.get("ns-imp")
    assert fetched is not None
    assert len(fetched.imports) == 1
    assert fetched.imports[0].folder_path == "/tmp/foo"
    assert fetched.imports[0].file_count == 5


def test_append_import_to_missing_namespace_raises(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    rec = ImportRecord(
        folder_path="/tmp/foo",
        started_at=datetime.now(timezone.utc),
        status="completed",
    )
    with pytest.raises(NamespaceNotFoundError):
        nm.append_import("does-not-exist", rec)


def test_imports_cap_trims_oldest(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("ns-many")
    for i in range(MAX_IMPORTS_PER_MANIFEST + 5):
        nm.append_import(
            "ns-many",
            ImportRecord(
                folder_path=f"/tmp/{i}",
                started_at=datetime.now(timezone.utc),
                status="completed",
                file_count=i,
            ),
        )
    fetched = nm.get("ns-many")
    assert fetched is not None
    assert len(fetched.imports) == MAX_IMPORTS_PER_MANIFEST
    # The oldest (file_count=0..4) should have been dropped.
    assert fetched.imports[0].file_count == 5
    assert fetched.imports[-1].file_count == MAX_IMPORTS_PER_MANIFEST + 4


# ---------------------------------------------------------------------------
# 10) update_stats edge cases
# ---------------------------------------------------------------------------


def test_update_stats_unknown_field_raises(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("ns-stats")
    with pytest.raises(ValueError, match="Unknown stats field"):
        nm.update_stats("ns-stats", nonsense=1)


def test_update_stats_missing_namespace_raises(tmp_kb: Path) -> None:
    nm = NamespaceManager(base_dir=tmp_kb)
    with pytest.raises(NamespaceNotFoundError):
        nm.update_stats("nope", chunks=1)


def test_corrupt_manifest_treated_as_missing(tmp_kb: Path) -> None:
    """If the manifest is malformed, get() returns None and list() skips it."""
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("ns-corrupt")
    # Corrupt the manifest.
    (tmp_kb / "ns-corrupt" / "manifest.json").write_text("{not valid json")
    assert nm.get("ns-corrupt") is None
    assert all(m.name != "ns-corrupt" for m in nm.list())


# ---------------------------------------------------------------------------
# 11) KnowledgeService — lifecycle delegation + stubs
# ---------------------------------------------------------------------------


def test_KnowledgeService_constructs_without_args() -> None:
    """KnowledgeService() must NOT raise (placeholder removed in EPIC-002)."""
    svc = KnowledgeService()
    assert svc.list_namespaces() == [] or isinstance(svc.list_namespaces(), list)


def test_KnowledgeService_lifecycle(tmp_kb: Path) -> None:
    """Create → get → list → delete → list (empty) via KnowledgeService."""
    svc = KnowledgeService(NamespaceManager(base_dir=tmp_kb))
    assert svc.list_namespaces() == []

    meta = svc.create_namespace("svc-ns", description="from svc")
    assert meta.name == "svc-ns"

    fetched = svc.get_namespace("svc-ns")
    assert fetched is not None
    assert fetched.description == "from svc"

    listed = svc.list_namespaces()
    assert [m.name for m in listed] == ["svc-ns"]

    assert svc.delete_namespace("svc-ns") is True
    assert svc.list_namespaces() == []
    assert svc.get_namespace("svc-ns") is None


def test_KnowledgeService_create_invalid_id_raises(tmp_kb: Path) -> None:
    svc = KnowledgeService(NamespaceManager(base_dir=tmp_kb))
    with pytest.raises(InvalidNamespaceIdError):
        svc.create_namespace("BAD ID")


def test_KnowledgeService_create_duplicate_raises(tmp_kb: Path) -> None:
    svc = KnowledgeService(NamespaceManager(base_dir=tmp_kb))
    svc.create_namespace("dup")
    with pytest.raises(NamespaceExistsError):
        svc.create_namespace("dup")


def test_KnowledgeService_import_wired_in_epic_003(tmp_kb: Path) -> None:
    """EPIC-003 wired ``import_folder``/``get_job``/``list_jobs`` — they no
    longer raise NotImplementedError. They now have real behaviour:

    - ``import_folder`` validates the folder path; raises FileNotFoundError
      for missing folders.
    - ``get_job`` returns None for unknown ids.
    - ``list_jobs`` returns [] for namespaces with no jobs.

    Full ingestion behaviour is covered by ``test_knowledge_ingestion.py``;
    this test just confirms the placeholder is gone.
    """
    svc = KnowledgeService(NamespaceManager(base_dir=tmp_kb))
    # Folder doesn't exist → FileNotFoundError (not NotImplementedError).
    with pytest.raises(FileNotFoundError):
        svc.import_folder("ns", "/tmp/this-path-does-not-exist-xyz-12345")
    assert svc.get_job("unknown-job-id") is None
    assert svc.list_jobs("ns-without-jobs") == []
    # Cleanup the auto-created JobManager's executor (best-effort).
    try:
        svc._get_job_manager().shutdown(wait=False)
    except Exception:
        pass


def test_KnowledgeService_query_raises_NamespaceNotFound_for_missing_ns(tmp_kb: Path) -> None:
    """EPIC-004: ``query`` now raise
    :class:`NamespaceNotFoundError` (not ``NotImplementedError`` any more)
    when the requested namespace doesn't exist."""
    svc = KnowledgeService(NamespaceManager(base_dir=tmp_kb))
    try:
        with pytest.raises(NamespaceNotFoundError):
            svc.query("ns", "what is foo?")
    finally:
        svc.shutdown()
