"""Unit tests for the dirty-flag hot-reload check that runs inside the pool's
idle sweep.

Why these tests exist
---------------------
Before this change, ``MemoryPool._check_and_handle_config_dirty()`` was only
invoked from ``get_or_create()``.  That left a hole: the per-slot auto-sync
thread would keep using a stale ``AgenticMemorySystem`` (and a stale
embedding-function model name) until *something* called ``get_or_create()``.
Saving new model settings in the dashboard would write the dirty-flag
sentinel, but no consumer of the flag would actually evict the slot — so the
auto-sync thread kept exploding every ``sync_interval_s`` with errors like
``model "<old>" not found``.

The fix is to call ``_check_and_handle_config_dirty()`` at the top of every
sweep iteration, so the pool's own background thread can detect a settings
change and evict stale slots without waiting for an MCP tool call.

These tests exercise every branch of that hot-reload path:

  1. No flag exists                        → no-op
  2. First observation of the flag          → records baseline, no eviction
  3. Same mtime across two iterations       → idempotent (single-flight)
  4. New mtime but config unchanged         → no eviction (fingerprint match)
  5. New mtime AND config changed           → all slots evicted
  6. ``stat()`` raises ``OSError``          → logged, no crash, no eviction
  7. Idle eviction still works              → regression guard
  8. Concurrent ``get_or_create`` + sweep   → ``load_config`` called once
  9. Sweep wiring                           → ``_sweep_once`` invokes the check

All tests use lightweight fakes for ``AgenticMemorySystem`` (via
``_fake_system_factory``) and patch ``agentic_memory.config.load_config`` so
the fingerprint is fully under test control.  No real ML, no network, no
filesystem outside ``tempfile``.
"""

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Ensure the memory package is importable.
_MEMORY_DIR = Path(__file__).resolve().parent.parent.parent
if str(_MEMORY_DIR) not in sys.path:
    sys.path.insert(0, str(_MEMORY_DIR))

from pool_config import PoolConfig  # noqa: E402
import memory_pool  # noqa: E402
from memory_pool import MemoryPool  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _noop_preloader():
    """ML preloader stub — tests don't need any real ML."""
    pass


def _fake_system_factory(persist_dir: str = "", **kwargs):
    """Lightweight stand-in for ``AgenticMemorySystem``."""
    return SimpleNamespace(
        memories={},
        persist_dir=persist_dir,
        sync_to_disk=MagicMock(return_value={"written": 0}),
        tree=MagicMock(return_value="(empty)"),
        search=MagicMock(return_value=[]),
        read=MagicMock(return_value=None),
        add_note=MagicMock(),
    )


def _make_fake_cfg(llm_model: str = "model-A", embedding_model: str = "embed-A"):
    """Build a fake ``MemoryConfig``-shaped object with the fields used by
    ``_compute_config_fingerprint``.  We don't import the real dataclasses
    so the test stays self-contained and resilient to schema additions."""
    return SimpleNamespace(
        llm=SimpleNamespace(
            backend="ollama",
            model=llm_model,
            compatible_url="",
            compatible_key="",
        ),
        embedding=SimpleNamespace(
            backend="ollama",
            model=embedding_model,
            compatible_url="",
            compatible_key="",
        ),
        vector=SimpleNamespace(backend="zvec"),
        evolution=SimpleNamespace(
            context_aware=True,
            context_aware_tree=False,
            max_links=3,
        ),
        search=SimpleNamespace(
            similarity_weight=0.8,
            decay_half_life_days=30.0,
        ),
        sync=SimpleNamespace(conflict_resolution="last_modified"),
    )


def _pool_with_defaults(**overrides) -> MemoryPool:
    """Create a MemoryPool with test-friendly defaults — sweep + sync threads
    effectively disabled unless the test explicitly enables them."""
    defaults = dict(
        idle_timeout_s=0,           # idle sweep off
        max_instances=10,
        eviction_policy="lru",
        ml_preload=False,
        ml_ready_timeout_s=1,
        sync_interval_s=3600,        # auto-sync effectively disabled
        sync_on_kill=False,
        allowed_paths=None,
        sweep_interval_s=3600,       # sweep loop effectively disabled
    )
    defaults.update(overrides)
    return MemoryPool(
        config=PoolConfig(**defaults),
        system_factory=_fake_system_factory,
        ml_preloader=_noop_preloader,
    )


def _wait_until(predicate, timeout_s: float = 2.0, interval_s: float = 0.02) -> bool:
    """Poll *predicate* until it returns truthy or *timeout_s* elapses.
    Eviction is async (it runs in a background cleanup thread), so the tests
    use this to avoid flaky ``time.sleep(...)`` with arbitrary durations."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return predicate()


class _FakeFlagPath:
    """Stand-in for ``Path`` whose ``.stat()`` raises a configured exception.

    Used by the OSError test — Path objects are effectively immutable so we
    swap the module-level constant with this fake instead of patching a
    method on a real Path instance.
    """

    def __init__(self, exc: Exception):
        self._exc = exc

    def stat(self):
        raise self._exc


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
class _DirtyFlagTestBase(unittest.TestCase):
    """Shared setup: redirect the dirty-flag path into a tempdir and stub
    ``load_config`` so each test fully controls the fingerprint."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp(prefix="dirty-flag-test-")
        self.flag_path = Path(self.tmp_root) / ".memory_config_dirty"

        self._patch_flag = patch.object(memory_pool, "_CONFIG_DIRTY_FLAG", self.flag_path)
        self._patch_flag.start()

        self._fake_cfg = _make_fake_cfg()
        # ``_check_and_handle_config_dirty`` does ``from agentic_memory.config
        # import load_config`` lazily — patching the attribute on the module
        # is what the late binding picks up.
        self._patch_cfg = patch(
            "agentic_memory.config.load_config",
            return_value=self._fake_cfg,
        )
        self._patch_cfg.start()

        self.persist_dir = tempfile.mkdtemp(prefix="dirty-flag-persist-")
        self.pool = _pool_with_defaults(idle_timeout_s=3600)

    def tearDown(self):
        try:
            self.pool.kill_all()
        finally:
            self._patch_flag.stop()
            self._patch_cfg.stop()

    # -- helpers ----------------------------------------------------------
    def _write_flag(self, mtime: float | None = None) -> None:
        self.flag_path.parent.mkdir(parents=True, exist_ok=True)
        self.flag_path.write_text("1")
        if mtime is not None:
            os.utime(self.flag_path, (mtime, mtime))


class TestNoFlag(_DirtyFlagTestBase):
    """When the dirty flag does not exist the sweep must not touch slots."""

    def test_sweep_is_noop_without_flag(self):
        self.pool.get_or_create(self.persist_dir)
        self.assertEqual(self.pool.active_slots, 1)

        # No flag file → sweep should be a no-op.
        self.assertFalse(self.flag_path.exists())
        self.pool._sweep_once(timeout=3600)

        self.assertEqual(self.pool.active_slots, 1)
        self.assertIsNone(
            self.pool._config_fingerprint,
            "no flag → fingerprint must remain unrecorded",
        )


class TestFirstObservation(_DirtyFlagTestBase):
    """First time the pool sees the flag, it should baseline the fingerprint
    *without* evicting anything — there's no prior fingerprint to compare
    against, so eviction would be unjustified."""

    def test_records_baseline_only(self):
        slot = self.pool.get_or_create(self.persist_dir)  # baseline path stat
        self._write_flag(mtime=1000.0)

        self.pool._sweep_once(timeout=3600)

        self.assertEqual(self.pool.active_slots, 1, "no eviction on first observation")
        self.assertIsNotNone(self.pool._config_fingerprint)
        # The original slot must still be the same object.
        with self.pool._lock:
            self.assertIn(os.path.realpath(self.persist_dir), self.pool._slots)
            self.assertIs(self.pool._slots[os.path.realpath(self.persist_dir)], slot)


class TestUnchangedFingerprint(_DirtyFlagTestBase):
    """A new flag mtime with an unchanged config means the dashboard saved
    settings that didn't actually alter any field the runtime cares about
    (e.g. UI-only fields).  No eviction should occur."""

    def test_no_eviction_when_fingerprint_unchanged(self):
        # Establish baseline.
        self.pool.get_or_create(self.persist_dir)
        self._write_flag(mtime=1000.0)
        self.pool._sweep_once(timeout=3600)
        baseline = self.pool._config_fingerprint
        self.assertIsNotNone(baseline)

        # Bump mtime but leave the cfg untouched.
        self._write_flag(mtime=2000.0)
        self.pool._sweep_once(timeout=3600)

        self.assertEqual(self.pool.active_slots, 1)
        self.assertEqual(self.pool._config_fingerprint, baseline)


class TestChangedFingerprint(_DirtyFlagTestBase):
    """The headline scenario: the user changes their model in the dashboard.
    Sweep must evict every existing slot so the next access rebuilds them
    against the fresh config."""

    def test_evicts_all_slots_when_fingerprint_changes(self):
        # Two slots so we can prove "all" really means all.
        d1 = self.persist_dir
        d2 = tempfile.mkdtemp(prefix="dirty-flag-persist-2-")
        self.pool.get_or_create(d1)
        self.pool.get_or_create(d2)
        self.assertEqual(self.pool.active_slots, 2)

        # Establish baseline.
        self._write_flag(mtime=1000.0)
        self.pool._sweep_once(timeout=3600)
        baseline = self.pool._config_fingerprint

        # Settings change: bump model name and flag mtime.
        self._fake_cfg.llm.model = "model-B"
        self._fake_cfg.embedding.model = "embed-B"
        self._write_flag(mtime=2000.0)

        self.pool._sweep_once(timeout=3600)

        # Eviction is dispatched to a cleanup thread; wait briefly for the
        # slots dict to actually drain.
        self.assertTrue(
            _wait_until(lambda: self.pool.active_slots == 0),
            f"slots should drain after fingerprint change, got {self.pool.active_slots}",
        )
        self.assertNotEqual(self.pool._config_fingerprint, baseline)


class TestIdempotentAcrossIterations(_DirtyFlagTestBase):
    """Sweeping repeatedly with the same flag mtime must not cause repeated
    evictions — otherwise every sweep would churn slots unnecessarily."""

    def test_repeated_sweeps_with_same_mtime_are_idempotent(self):
        self.pool.get_or_create(self.persist_dir)

        # Baseline.
        self._write_flag(mtime=1000.0)
        self.pool._sweep_once(timeout=3600)

        # Trigger a real change.
        self._fake_cfg.llm.model = "model-B"
        self._write_flag(mtime=2000.0)
        self.pool._sweep_once(timeout=3600)
        self.assertTrue(_wait_until(lambda: self.pool.active_slots == 0))

        # Recreate; second sweep with the same mtime should leave it alone.
        self.pool.get_or_create(self.persist_dir)
        self.pool._sweep_once(timeout=3600)
        self.pool._sweep_once(timeout=3600)
        self.assertEqual(self.pool.active_slots, 1)


class TestStatErrorHandling(_DirtyFlagTestBase):
    """Filesystem hiccups while reading the flag must not propagate — the
    sweep loop has to keep running."""

    def test_oserror_does_not_propagate(self):
        self.pool.get_or_create(self.persist_dir)

        # Swap the module-level constant for a fake whose .stat() raises.
        fake = _FakeFlagPath(OSError("simulated stat failure"))
        with patch.object(memory_pool, "_CONFIG_DIRTY_FLAG", fake):
            try:
                self.pool._sweep_once(timeout=3600)
            except OSError as exc:
                self.fail(f"sweep must swallow OSError, got {exc!r}")

        # Slot should be untouched.
        self.assertEqual(self.pool.active_slots, 1)

    def test_filenotfounderror_is_silent(self):
        # File simply doesn't exist — no log, no eviction.
        self.assertFalse(self.flag_path.exists())
        self.pool.get_or_create(self.persist_dir)
        self.pool._sweep_once(timeout=3600)
        self.assertEqual(self.pool.active_slots, 1)


class TestIdleEvictionStillWorks(unittest.TestCase):
    """Regression guard: adding the dirty-flag check to the sweep must not
    break the existing idle-eviction behaviour."""

    def test_sweep_still_kills_idle_slot(self):
        pool = _pool_with_defaults(idle_timeout_s=1, sweep_interval_s=3600)
        try:
            tmp = tempfile.mkdtemp(prefix="idle-eviction-")
            pool.get_or_create(tmp)
            with pool._lock:
                pool._slots[os.path.realpath(tmp)].last_activity = (
                    time.monotonic() - 10
                )
            pool._sweep_once(timeout=1)
            self.assertEqual(pool.active_slots, 0)
        finally:
            pool.kill_all()


class TestSingleFlightUnderConcurrency(_DirtyFlagTestBase):
    """When ``get_or_create`` and ``_sweep_once`` race against the same flag
    transition, only one of them should re-fingerprint.  The other must
    notice the bumped mtime and skip the work."""

    def test_load_config_called_once_per_mtime_change(self):
        self.pool.get_or_create(self.persist_dir)
        self._write_flag(mtime=1000.0)
        self.pool._sweep_once(timeout=3600)  # baseline

        # Wrap load_config to count calls during the racy section.
        call_count = {"n": 0}
        original = self._fake_cfg

        def counting_load_config():
            call_count["n"] += 1
            return original

        with patch("agentic_memory.config.load_config", side_effect=counting_load_config):
            self._fake_cfg.llm.model = "model-B"
            self._write_flag(mtime=2000.0)

            errors: list[Exception] = []

            def worker(fn):
                try:
                    fn()
                except Exception as exc:  # pragma: no cover - bubble up
                    errors.append(exc)

            t1 = threading.Thread(target=worker, args=(lambda: self.pool._sweep_once(3600),))
            t2 = threading.Thread(
                target=worker,
                args=(lambda: self.pool.get_or_create(self.persist_dir),),
            )
            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

        self.assertEqual(errors, [])
        self.assertEqual(
            call_count["n"],
            1,
            f"load_config should run exactly once per mtime change, got {call_count['n']}",
        )


class TestSweepWiring(_DirtyFlagTestBase):
    """Smoke test: ``_sweep_once`` must actually call the dirty-flag check.
    If a future refactor moves the call elsewhere, this test catches it."""

    def test_sweep_once_invokes_dirty_check(self):
        self.pool.get_or_create(self.persist_dir)
        with patch.object(
            self.pool,
            "_check_and_handle_config_dirty",
            wraps=self.pool._check_and_handle_config_dirty,
        ) as spy:
            self.pool._sweep_once(timeout=3600)
            spy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
