"""
SUSI Britannica Index Management
=================================
Geteilt zwischen:
  - britannica_sync.py (Fetch-Orchestrator)
  - agent_britannica.py (Live-Fallback-Agent)

Funktionen:
  - Index laden/speichern
  - Update-Logik (30-Tage-Cache, Änderungen)
  - Titel-Suche (für agent_britannica)
  - Status-Bericht
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = PROJECT_ROOT / "tools" / "britannica_index.json"


class BritannicaIndex:
    """Wrapper für britannica_index.json"""
    
    def __init__(self):
        self.data = self._load()
    
    def _load(self) -> dict:
        """Lädt Index oder erstellt neuen"""
        if INDEX_PATH.exists():
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return {
            "meta": {
                "created": str(date.today()),
                "last_full_fetch": None,
                "total_articles": 0,
                "total_fetched": 0,
                "key_used": "key1",
                "last_updated": str(datetime.now()),
            },
            "articles": {}
        }
    
    def save(self):
        """Speichert Index mit Backup"""
        if INDEX_PATH.exists():
            backup = INDEX_PATH.with_suffix(".json.bak")
            if backup.exists():
                backup.unlink()
            INDEX_PATH.rename(backup)
        
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def needs_fetch(self, article_id: str, api_lastUpdated: str) -> bool:
        """Prüft ob Artikel neu/geändert/Cache abgelaufen
        
        Args:
            article_id: Article ID als String
            api_lastUpdated: Datum von Britannica API
        
        Returns:
            True wenn Fetch nötig, False wenn aktuell
        """
        art_id_str = str(article_id)
        
        # Neu?
        if art_id_str not in self.data["articles"]:
            return True
        
        stored = self.data["articles"][art_id_str]
        api_date = api_lastUpdated[:10]
        stored_date = stored.get("lastUpdated", "1970-01-01")
        
        # Bei Britannica geändert?
        if api_date > stored_date:
            return True
        
        # 30-Tage-Cache-Regel (Britannica sagt Cache muss erneuert werden)
        fetched_str = stored.get("fetched", "1970-01-01")
        try:
            fetched_date = datetime.strptime(fetched_str, "%Y-%m-%d").date()
            days_old = (date.today() - fetched_date).days
            
            if days_old > 30:
                return True
        except ValueError:
            return True
        
        return False
    
    def add_article(self, article_id: str, article_data: dict):
        """Fügt Artikel zum Index hinzu
        
        Args:
            article_id: Article ID
            article_data: {
                "title": str,
                "lastUpdated": "YYYY-MM-DD",
                "category": str,
                "file": "britannica_science_001.md",
                "fetched": "YYYY-MM-DD",
                "url": "https://www.britannica.com/...",
            }
        """
        self.data["articles"][str(article_id)] = article_data
    
    def find_by_title(self, search_term: str) -> list[dict]:
        """Sucht Artikel nach Titel (für agent_britannica)
        
        Args:
            search_term: z.B. "Fuzzy Logic"
        
        Returns:
            Liste von Artikeln, sortiert nach Relevanz (kürzeste zuerst)
            [{
                "article_id": 2203,
                "title": "fuzzy logic",
                "file": "britannica_technology_001.md",
                "fetched": "2026-07-14",
                "url": "https://www.britannica.com/article/fuzzy-logic/2203"
            }]
        """
        search_lower = search_term.lower()
        results = []
        
        for art_id, art_data in self.data["articles"].items():
            title_lower = art_data.get("title", "").lower()
            
            # Substring-Suche
            if search_lower in title_lower:
                results.append({
                    "article_id": int(art_id),
                    "title": art_data["title"],
                    "file": art_data.get("file"),
                    "fetched": art_data.get("fetched"),
                    "url": art_data.get("url"),
                    "category": art_data.get("category"),
                })
        
        # Sortieren: kürzeste/beste Treffer zuerst
        return sorted(results, key=lambda x: len(x["title"]))
    
    def find_article_by_id(self, article_id: str) -> dict:
        """Findet einzelnen Artikel nach ID
        
        Args:
            article_id: Article ID
        
        Returns:
            Article-Daten oder None
        """
        return self.data["articles"].get(str(article_id))
    
    def get_status(self) -> str:
        """Status-String für CLI-Ausgabe"""
        meta = self.data["meta"]
        articles = self.data["articles"]
        
        # Pro Category aufschlüsseln
        by_category = {}
        for art in articles.values():
            cat = art.get("category", "unknown")
            by_category.setdefault(cat, {"total": 0, "fetched": 0})
            by_category[cat]["total"] += 1
            if art.get("fetched"):
                by_category[cat]["fetched"] += 1
        
        status_lines = [
            f"📊 Britannica Index Status",
            f"   Erstellt: {meta.get('created', '?')}",
            f"   Letzter Fetch: {meta.get('last_full_fetch', '?')}",
            f"   Letztes Update: {meta.get('last_updated', '?')}",
            f"   Artikel gesamt: {len(articles)}",
            f"   Davon gefetcht: {meta.get('total_fetched', 0)}",
        ]
        
        if by_category:
            status_lines.append(f"\n   Pro Category:")
            for cat in sorted(by_category.keys()):
                counts = by_category[cat]
                status_lines.append(f"     {cat}: {counts['fetched']}/{counts['total']}")
        
        return "\n".join(status_lines)


# Singleton für einfachere Nutzung
_index = None


def get_index() -> BritannicaIndex:
    """Gibt globale Index-Instanz zurück (Singleton)
    
    Laden ist teuer (JSON-Parse), daher cachen wir die Instanz.
    """
    global _index
    if _index is None:
        _index = BritannicaIndex()
    return _index


def reset_index():
    """Setzt Singleton zurück (für Tests)"""
    global _index
    _index = None