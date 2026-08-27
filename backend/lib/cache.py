import time
from typing import Any, Dict, Optional


class LRUCache:
    """
    A simple in-memory LRU (Least Recently Used) cache implementation
    with a TTL (Time To Live) for entries.
    """

    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Initializes the cache.
        :param max_size: Maximum number of entries in the cache.
        :param ttl: Lifetime of an entry in seconds.
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """Retrieves an entry from the cache if it exists and is still valid."""
        if key not in self.cache:

            return None

        cached_item = self.cache[key]
        if time.time() - cached_item["timestamp"] > self.ttl:
            # Entry has expired, remove it
            del self.cache[key]
            return None

        # Mark as "most recently used" by moving the entry to the end
        self.cache[key] = self.cache.pop(key)
        return cached_item["data"]

    def set(self, key: str, value: Any):
        """Adds a new entry to the cache or updates an existing one."""
        # Check if the cache is full before adding a new key
        if key not in self.cache and len(self.cache) >= self.max_size:
            # Remove the oldest entry (the first one in the dict in Python 3.7+)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            print(f"🗑️ Cache full. Removed oldest entry: {oldest_key[:50]}...")

        # Add the new entry with a timestamp
        self.cache[key] = {"data": value, "timestamp": time.time()}
