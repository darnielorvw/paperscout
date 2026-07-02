import time
from typing import Any, Dict, Optional


class LRUCache:
    """
    Eine einfache In-Memory LRU (Least Recently Used) Cache-Implementierung
    mit einer TTL (Time To Live) für die Einträge.
    """

    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Initialisiert den Cache.
        :param max_size: Maximale Anzahl an Einträgen im Cache.
        :param ttl: Lebensdauer eines Eintrags in Sekunden.
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """Holt einen Eintrag aus dem Cache, falls er existiert und gültig ist."""
        if key not in self.cache:

            return None

        cached_item = self.cache[key]
        if time.time() - cached_item["timestamp"] > self.ttl:
            # Eintrag ist abgelaufen, entferne ihn
            del self.cache[key]
            return None

        # Markiere als "zuletzt verwendet", indem der Eintrag ans Ende verschoben wird
        self.cache[key] = self.cache.pop(key)
        return cached_item["data"]

    def set(self, key: str, value: Any):
        """Fügt einen neuen Eintrag zum Cache hinzu oder aktualisiert einen bestehenden."""
        # Prüfe, ob der Cache voll ist, bevor ein neuer Schlüssel hinzugefügt wird
        if key not in self.cache and len(self.cache) >= self.max_size:
            # Entferne den ältesten Eintrag (den ersten im Dictionary in Python 3.7+)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            print(f"🗑️ Cache voll. Ältester Eintrag entfernt: {oldest_key[:50]}...")

        # Füge den neuen Eintrag mit Zeitstempel hinzu
        self.cache[key] = {"data": value, "timestamp": time.time()}
