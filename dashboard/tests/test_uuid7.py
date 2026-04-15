"""Unit tests for UUIDv7 helpers and time_id integration (EPIC-001)."""
import os
import time
import uuid
from datetime import datetime

os.environ.setdefault("OSTWIN_API_KEY", "test-key")

from dashboard.zvec_store import uuid7, extract_timestamp_from_uuid7


class TestUUID7Generation:
    def test_uuid7_returns_string(self):
        result = uuid7()
        assert isinstance(result, str)

    def test_uuid7_valid_uuid_format(self):
        result = uuid7()
        parsed = uuid.UUID(result)  # should not raise
        assert str(parsed) == result

    def test_uuid7_version_nibble_is_7(self):
        result = uuid7()
        parsed = uuid.UUID(result)
        assert parsed.version == 7

    def test_uuid7_uniqueness(self):
        ids = {uuid7() for _ in range(1000)}
        assert len(ids) == 1000

    def test_uuid7_monotonically_increasing(self):
        a = uuid7()
        b = uuid7()
        assert b > a or b == a  # lexicographic order preserves time

    def test_uuid7_sequential_timestamps_monotonic(self):
        a = uuid7()
        time.sleep(0.002)  # 2ms gap
        b = uuid7()
        ts_a = extract_timestamp_from_uuid7(a)
        ts_b = extract_timestamp_from_uuid7(b)
        assert ts_b >= ts_a


class TestExtractTimestamp:
    def test_round_trip_within_1_second(self):
        from datetime import timedelta
        before = datetime.now() - timedelta(milliseconds=2)  # UUIDv7 has ms precision, allow rounding
        uid = uuid7()
        after = datetime.now() + timedelta(milliseconds=2)
        ts = extract_timestamp_from_uuid7(uid)
        assert before <= ts <= after

    def test_extract_from_known_uuid7(self):
        uid = uuid7()
        ts = extract_timestamp_from_uuid7(uid)
        assert isinstance(ts, datetime)
        assert ts.year >= 2024

    def test_extract_from_invalid_returns_epoch(self):
        ts = extract_timestamp_from_uuid7("not-a-uuid")
        assert ts == datetime.fromtimestamp(0)

    def test_extract_from_empty_returns_epoch(self):
        ts = extract_timestamp_from_uuid7("")
        assert ts == datetime.fromtimestamp(0)


class TestTimeIdSortingLogic:
    """Verify that sorting by time_id (string comparison) produces chronological order."""

    def test_time_id_string_sort_matches_time_order(self):
        ids_with_times = []
        for _ in range(10):
            uid = uuid7()
            ts = extract_timestamp_from_uuid7(uid)
            ids_with_times.append((uid, ts))
            time.sleep(0.001)

        sorted_by_str = sorted(ids_with_times, key=lambda x: x[0])
        sorted_by_time = sorted(ids_with_times, key=lambda x: x[1])
        assert [x[0] for x in sorted_by_str] == [x[0] for x in sorted_by_time]
