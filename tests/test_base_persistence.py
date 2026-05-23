"""Tests for base/persistence.py - AtomicJsonStore, JsonlAppender, SessionIdResolver.

Full coverage including backup fallback, atomic write, modify(), delete(),
append with and without auto_timestamp, read_filtered, count, and session
ID resolution with caching and invalidation.

ASCII-only (cp1252 safe).
"""
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch

from base.persistence import AtomicJsonStore, JsonlAppender, SessionIdResolver


# ---------------------------------------------------------------------------
# AtomicJsonStore
# ---------------------------------------------------------------------------

class TestAtomicJsonStore:
    """Tests for AtomicJsonStore file persistence."""

    @pytest.fixture
    def tmp_store(self, tmp_path):
        return AtomicJsonStore(tmp_path / "data.json")

    def test_path_property(self, tmp_store, tmp_path):
        assert tmp_store.path == tmp_path / "data.json"

    def test_exists_false_before_save(self, tmp_store):
        assert tmp_store.exists is False

    def test_exists_true_after_save(self, tmp_store):
        tmp_store.save({"x": 1})
        assert tmp_store.exists is True

    def test_save_and_load_round_trip(self, tmp_store):
        tmp_store.save({"count": 42})
        result = tmp_store.load()
        assert result == {"count": 42}

    def test_load_returns_default_factory_when_missing(self, tmp_path):
        store = AtomicJsonStore(tmp_path / "missing.json", default_factory=lambda: {"d": 0})
        assert store.load() == {"d": 0}

    def test_load_returns_explicit_default_when_missing(self, tmp_store):
        result = tmp_store.load(default={"explicit": True})
        assert result == {"explicit": True}

    def test_load_returns_empty_dict_by_default(self, tmp_store):
        result = tmp_store.load()
        assert result == {}

    def test_save_with_backup_creates_bak_file(self, tmp_store, tmp_path):
        tmp_store.save({"v": 1})
        tmp_store.save({"v": 2}, backup=True)
        bak = tmp_path / "data.json.bak"
        assert bak.exists()
        assert json.loads(bak.read_text())["v"] == 1

    def test_save_backup_without_existing_file_does_not_error(self, tmp_store):
        tmp_store.save({"v": 1}, backup=True)
        assert tmp_store.exists is True

    def test_load_falls_back_to_bak_on_corrupt_primary(self, tmp_path):
        store = AtomicJsonStore(tmp_path / "state.json")
        bak = tmp_path / "state.json.bak"
        bak.write_text('{"from_bak": true}', encoding="utf-8")
        (tmp_path / "state.json").write_text("NOT JSON", encoding="utf-8")
        result = store.load()
        assert result.get("from_bak") is True

    def test_modify_reads_applies_saves(self, tmp_store):
        tmp_store.save({"count": 10})
        result = tmp_store.modify(lambda d: d.update(count=d["count"] + 1))
        assert tmp_store.load()["count"] == 11

    def test_modify_returns_updated_data(self, tmp_store):
        tmp_store.save({"n": 5})
        updated = tmp_store.modify(lambda d: d.update(n=99))
        loaded = tmp_store.load()
        assert loaded["n"] == 99

    def test_modify_with_default_when_file_missing(self, tmp_store):
        tmp_store.modify(lambda d: d.update(new_key="hello"), default={"new_key": ""})
        assert tmp_store.load()["new_key"] == "hello"

    def test_delete_removes_file(self, tmp_store):
        tmp_store.save({"x": 1})
        assert tmp_store.delete() is True
        assert tmp_store.exists is False

    def test_delete_returns_false_when_missing(self, tmp_store):
        assert tmp_store.delete() is False

    def test_try_read_returns_none_for_non_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json", encoding="utf-8")
        result = AtomicJsonStore._try_read(f)
        assert result is None

    def test_try_read_returns_none_for_non_dict_json(self, tmp_path):
        f = tmp_path / "arr.json"
        f.write_text("[1,2,3]", encoding="utf-8")
        result = AtomicJsonStore._try_read(f)
        assert result is None

    def test_try_read_returns_none_for_missing_file(self, tmp_path):
        result = AtomicJsonStore._try_read(tmp_path / "nope.json")
        assert result is None

    def test_save_skips_backup_when_backup_false(self, tmp_store, tmp_path):
        tmp_store.save({"v": 1})
        tmp_store.save({"v": 2}, backup=False)
        bak = tmp_path / "data.json.bak"
        assert not bak.exists()

    def test_save_backup_oserror_is_swallowed(self, tmp_store):
        """save() continues when shutil.copy2 raises OSError during backup."""
        import shutil
        tmp_store.save({"v": 1})
        with patch.object(shutil, "copy2", side_effect=OSError("disk full")):
            tmp_store.save({"v": 2}, backup=True)
        assert tmp_store.load()["v"] == 2

    def test_dir_created_flag_cached_after_first_save(self, tmp_store):
        tmp_store.save({"a": 1})
        assert tmp_store._dir_created is True
        tmp_store.save({"a": 2})
        assert tmp_store.load()["a"] == 2


# ---------------------------------------------------------------------------
# JsonlAppender
# ---------------------------------------------------------------------------

class TestJsonlAppender:
    """Tests for JsonlAppender JSONL log file handling."""

    @pytest.fixture
    def appender(self, tmp_path):
        return JsonlAppender(tmp_path / "log.jsonl")

    def test_path_property(self, appender, tmp_path):
        assert appender.path == tmp_path / "log.jsonl"

    def test_exists_false_before_append(self, appender):
        assert appender.exists is False

    def test_append_creates_file(self, appender):
        appender.append({"event": "start"})
        assert appender.exists is True

    def test_append_adds_timestamp_by_default(self, appender):
        appender.append({"event": "x"})
        entries = appender.read_all()
        assert "timestamp" in entries[0]

    def test_append_no_timestamp_when_disabled(self, appender):
        appender.append({"event": "x", "timestamp": "custom"}, auto_timestamp=False)
        entries = appender.read_all()
        assert entries[0]["timestamp"] == "custom"

    def test_append_preserves_existing_timestamp(self, appender):
        appender.append({"event": "x", "timestamp": "2026-01-01"})
        entries = appender.read_all()
        assert entries[0]["timestamp"] == "2026-01-01"

    def test_read_all_empty_list_when_file_missing(self, appender):
        assert appender.read_all() == []

    def test_read_all_returns_all_entries(self, appender):
        for i in range(3):
            appender.append({"i": i}, auto_timestamp=False)
        entries = appender.read_all()
        assert len(entries) == 3

    def test_read_all_skips_corrupt_lines(self, appender, tmp_path):
        (tmp_path / "log.jsonl").write_text(
            '{"ok": 1}\n{INVALID}\n{"ok": 2}\n', encoding="utf-8"
        )
        entries = appender.read_all()
        assert len(entries) == 2

    def test_read_all_skips_blank_lines(self, appender, tmp_path):
        (tmp_path / "log.jsonl").write_text(
            '{"ok": 1}\n\n{"ok": 2}\n', encoding="utf-8"
        )
        entries = appender.read_all()
        assert len(entries) == 2

    def test_read_filtered_by_date(self, appender):
        appender.append({"event": "a", "timestamp": "2026-01-01T10:00:00"}, auto_timestamp=False)
        appender.append({"event": "b", "timestamp": "2026-01-02T10:00:00"}, auto_timestamp=False)
        results = appender.read_filtered(date="2026-01-01")
        assert len(results) == 1
        assert results[0]["event"] == "a"

    def test_read_filtered_by_field(self, appender):
        appender.append({"type": "INFO", "msg": "hello"}, auto_timestamp=False)
        appender.append({"type": "ERROR", "msg": "fail"}, auto_timestamp=False)
        results = appender.read_filtered(type="ERROR")
        assert len(results) == 1
        assert results[0]["msg"] == "fail"

    def test_read_filtered_by_date_and_field(self, appender):
        appender.append({"timestamp": "2026-01-01", "type": "INFO"}, auto_timestamp=False)
        appender.append({"timestamp": "2026-01-01", "type": "ERROR"}, auto_timestamp=False)
        appender.append({"timestamp": "2026-01-02", "type": "INFO"}, auto_timestamp=False)
        results = appender.read_filtered(date="2026-01-01", type="INFO")
        assert len(results) == 1

    def test_count_returns_zero_when_missing(self, appender):
        assert appender.count() == 0

    def test_count_returns_number_of_entries(self, appender):
        for _ in range(5):
            appender.append({"x": 1}, auto_timestamp=False)
        assert appender.count() == 5

    def test_count_skips_blank_lines(self, appender, tmp_path):
        """count() skips blank lines and counts only non-empty lines."""
        (tmp_path / "log.jsonl").write_text(
            '{"x": 1}\n\n{"x": 2}\n', encoding="utf-8"
        )
        assert appender.count() == 2


# ---------------------------------------------------------------------------
# SessionIdResolver
# ---------------------------------------------------------------------------

class TestSessionIdResolver:
    """Tests for SessionIdResolver singleton with TTL caching."""

    def setup_method(self):
        """Reset singleton before each test."""
        SessionIdResolver.reset()

    def test_returns_empty_when_no_files(self, tmp_path):
        resolver = SessionIdResolver(config_dir=tmp_path)
        assert resolver.get() == ""

    def test_reads_from_current_session_file(self, tmp_path):
        sess_file = tmp_path / ".current-session.json"
        sess_file.write_text(
            '{"current_session_id": "SESSION-20260523-120000-ABCD"}',
            encoding="utf-8",
        )
        resolver = SessionIdResolver(config_dir=tmp_path)
        assert resolver.get() == "SESSION-20260523-120000-ABCD"

    def test_falls_back_to_progress_file(self, tmp_path):
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "session-progress.json").write_text(
            '{"session_id": "SESSION-FALLBACK-0001"}', encoding="utf-8"
        )
        resolver = SessionIdResolver(config_dir=tmp_path)
        assert resolver.get() == "SESSION-FALLBACK-0001"

    def test_current_session_takes_priority_over_progress(self, tmp_path):
        sess_file = tmp_path / ".current-session.json"
        sess_file.write_text(
            '{"current_session_id": "SESSION-PRIMARY"}', encoding="utf-8"
        )
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "session-progress.json").write_text(
            '{"session_id": "SESSION-FALLBACK"}', encoding="utf-8"
        )
        resolver = SessionIdResolver(config_dir=tmp_path)
        assert resolver.get() == "SESSION-PRIMARY"

    def test_ignores_non_session_prefixed_ids(self, tmp_path):
        sess_file = tmp_path / ".current-session.json"
        sess_file.write_text(
            '{"current_session_id": "NOT-A-SESSION-ID"}', encoding="utf-8"
        )
        resolver = SessionIdResolver(config_dir=tmp_path)
        assert resolver.get() == ""

    def test_caches_result_within_ttl(self, tmp_path):
        resolver = SessionIdResolver(config_dir=tmp_path)
        sid1 = resolver.get()
        resolver._cached_id = "SESSION-CACHED"
        resolver._cache_time = time.time()
        sid2 = resolver.get()
        assert sid2 == "SESSION-CACHED"

    def test_force_refresh_bypasses_cache(self, tmp_path):
        resolver = SessionIdResolver(config_dir=tmp_path)
        resolver._cached_id = "SESSION-STALE"
        resolver._cache_time = time.time()
        fresh = resolver.get(force_refresh=True)
        assert fresh == ""

    def test_invalidate_clears_cache(self, tmp_path):
        resolver = SessionIdResolver(config_dir=tmp_path)
        resolver._cached_id = "SESSION-X"
        resolver._cache_time = time.time()
        resolver.invalidate()
        assert resolver._cached_id == ""
        assert resolver._cache_time == 0.0

    def test_singleton_pattern(self, tmp_path):
        r1 = SessionIdResolver(config_dir=tmp_path)
        r2 = SessionIdResolver(config_dir=tmp_path)
        assert r1 is r2

    def test_current_session_file_property(self, tmp_path):
        resolver = SessionIdResolver(config_dir=tmp_path)
        assert resolver.current_session_file == tmp_path / ".current-session.json"

    def test_progress_file_property(self, tmp_path):
        resolver = SessionIdResolver(config_dir=tmp_path)
        assert resolver.progress_file == tmp_path / "logs" / "session-progress.json"

    def test_read_session_id_returns_empty_for_corrupt_file(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("INVALID JSON", encoding="utf-8")
        result = SessionIdResolver._read_session_id(bad, "key")
        assert result == ""

    def test_read_session_id_returns_empty_for_missing_file(self, tmp_path):
        result = SessionIdResolver._read_session_id(tmp_path / "nope.json", "key")
        assert result == ""

    def test_cache_expires_after_ttl(self, tmp_path):
        resolver = SessionIdResolver(config_dir=tmp_path)
        resolver._cached_id = "SESSION-EXPIRED"
        resolver._cache_time = time.time() - (SessionIdResolver._CACHE_TTL + 1)
        result = resolver.get()
        assert result == ""
