"""Unit tests for the in-memory LRU cache with TTL."""

import lib.cache as cache_module
from lib.cache import LRUCache


class TestLRUCache:
    def test_get_returns_none_for_a_missing_key(self):
        assert LRUCache().get("nope") is None

    def test_set_then_get_returns_the_value(self):
        c = LRUCache()
        c.set("k", {"v": 1})
        assert c.get("k") == {"v": 1}

    def test_entry_expires_after_the_ttl(self, monkeypatch):
        now = [1_000.0]
        monkeypatch.setattr(cache_module.time, "time", lambda: now[0])
        c = LRUCache(ttl=60)
        c.set("k", "v")

        now[0] += 59
        assert c.get("k") == "v"

        now[0] += 2  # now 61s after set, past the TTL
        assert c.get("k") is None
        assert "k" not in c.cache

    def test_evicts_the_oldest_entry_when_full(self):
        c = LRUCache(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)  # pushes "a" out
        assert c.get("a") is None
        assert c.get("b") == 2
        assert c.get("c") == 3

    def test_get_marks_an_entry_as_recently_used(self):
        c = LRUCache(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")  # "a" is now the most recently used, "b" the oldest
        c.set("c", 3)  # should evict "b", not "a"
        assert c.get("a") == 1
        assert c.get("b") is None
        assert c.get("c") == 3

    def test_updating_an_existing_key_does_not_trigger_eviction(self):
        c = LRUCache(max_size=1)
        c.set("a", 1)
        c.set("a", 2)
        assert c.get("a") == 2
