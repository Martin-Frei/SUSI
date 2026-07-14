"""
SUSI Britannica Sync — Fetch-Orchestrator
===========================================
Holt Britannica-Artikel via API, konvertiert zu SUSIpedia-Markdown,
speichert Fortschritt im Index für Wiederaufnahme.

Startet manuell in einem Terminal, läuft bis STRG+C oder VSCode schließt.

Aufruf:
    python -m rag.britannica_sync --category science --key key1
    python -m rag.britannica_sync --category technology --key key1
    python -m rag.britannica_sync --update --key key1
    python -m rag.britannica_sync --status

Features:
    - Paginiert durch Britannica API (~1000 pro Fetch = 3 Stunden)
    - Speichert Fortschritt in tools/britannica_index.json
    - Bei Abbruch/401 Limit: alles gespeichert, --update setzt fort
    - Update-Modus: nur geänderte/neue Artikel oder Cache >30 Tage
    - Logs: console + logs/britannica_sync.log
    - Kann parallel zu Django/SUSI laufen (Thread-safe Index-Speichern)

Status-Tracking:
    - britannica_index.json hält ArticleID → {lastUpdated, file, fetched}
    - Bei Cache-Abbruch speichert der Index den Fortschritt
    - Nächstes --update fetcht nur noch die fehlenden Artikel
"""

import argparse
import json
import os
import sys
import time
import logging
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from .britannica_index import get_index

# ── Setup ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
WISSEN_DIR = PROJECT_ROOT / "docs" / "wissen"
LOGS_DIR = PROJECT_ROOT / "logs"

LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "britannica_sync.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# ── API Config ─────────────────────────────────────────────────
BASE_URL = "https://syndication.api.eb.com/production"
ARTICLE_TYPE_ID = 1  # Encyclopaedia Britannica (Premier)
FETCH_DELAY = 10      # Sekunden zwischen Requests (ca 5 pro Minute)
ARTICLES_PER_FILE = 50  # Artikel pro MD-Datei
BRITANNICA_BASE_URL = "https://www.britannica.com"

CATEGORY_MAP = {
    1: "art",
    2: "science",
    3: "people",
    4: "sports",
    5: "events",
    6: "plants",
    7: "places",
    8: "technology",
    9: "animals",
}

CATEGORY_NAME_TO_ID = {v: k for k, v in CATEGORY_MAP.items()}

# ── API Key Loader ─────────────────────────────────────────────
def load_api_key(key_name: str) -> str:
    """Lädt API-Key aus .env
    
    Args:
        key_name: "key1" oder "key2"
    
    Returns:
        API-Key String
    
    Raises:
        SystemExit wenn Key nicht gefunden
    """
    load_dotenv(ENV_PATH)
    env_var = f"BRITANICA_KEY{key_name[-1]}"  # key1 → BRITANICA_KEY1
    key = os.getenv(env_var)
    if not key:
        log.error(f"❌ {env_var} nicht in .env gefunden")
        sys.exit(1)
    return key

# ── API Calls ──────────────────────────────────────────────────
def fetch_article_list(api_key: str, category_id: int | None = None) -> list[dict]:
    """Holt komplette Artikelliste paginiert von Britannica
    
    Args:
        api_key: API-Key
        category_id: Optional, z.B. 8 für "technology"
    
    Returns:
        Liste von {articleId, title, lastUpdated, ...}
    
    Bricht bei HTTP 401 (Limit) ab und speichert Fortschritt
    """
    articles = []
    page = 1
    total = None
    
    while True:
        params = {"articleTypeId": ARTICLE_TYPE_ID, "page": page}
        if category_id:
            params["categoryId"] = category_id
        
        try:
            resp = requests.get(
                f"{BASE_URL}/articles",
                headers={"x-api-key": api_key},
                params=params,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                log.warning("⚠️  API-Limit erreicht (401)")
                return articles
            raise
        except requests.exceptions.RequestException as e:
            log.error(f"❌ Netzwerkfehler: {e}")
            return articles
        
        if total is None:
            total = data["totalCount"]
            cat_name_temp = CATEGORY_MAP.get(category_id) if category_id else "alle"
            cat_name: str = cat_name_temp if cat_name_temp else "alle"
            log.info(f"📊 {total} Artikel insgesamt (Category: {cat_name})")
        
        articles.extend(data["articles"])
        log.info(f"   Seite {page}: +{len(data['articles'])} Artikel → {len(articles)}/{total}")
        
        if len(articles) >= total:
            break
        
        page += 1
        time.sleep(FETCH_DELAY)
    
    return articles

def fetch_article_xml(api_key: str, article_id: int) -> str:
    """Holt XML-Content eines einzelnen Artikels
    
    Args:
        api_key: API-Key
        article_id: Britannica Article ID
    
    Returns:
        XML-String
    
    Raises:
        requests.HTTPError bei API-Fehler
    """
    resp = requests.get(
        f"{BASE_URL}/article/{article_id}/xml",
        headers={"x-api-key": api_key},
        timeout=10
    )
    resp.raise_for_status()
    return resp.text

def xml_to_chunk(xml_content: str) -> dict | None:
    """Parst Britannica-XML zu Python-Dict
    
    Args:
        xml_content: XML String vom /article/.../xml Endpoint
    
    Returns:
        {
            "title": "artificial intelligence (AI)",
            "text": "Plaintext Gist...",
            "url": "https://www.britannica.com/article/artificial-intelligence/9711",
            "article_id": 9711,
            "last_updated": "2025-09-11",
        }
        
        Gibt None zurück wenn XML nicht parsbar
    """
    try:
        soup = BeautifulSoup(xml_content, "lxml-xml")
    except Exception as e:
        log.warning(f"   ⚠️  XML-Parser Fehler: {e}")
        return None
    
    article = soup.find("article")
    
    if not article:
        return None
    
    # Metadaten
    article_id_raw = article.get("articleid")
    article_id = int(str(article_id_raw)) if article_id_raw else 0
    
    url_path_raw = article.get("url")
    url_path = str(url_path_raw) if url_path_raw else ""
    full_url = f"{BRITANNICA_BASE_URL}{url_path}"
    
    # Datum: "2025-Sep-11 08:58:22" → "2025-09-11"
    raw_date_raw = article.get("lastupdate")
    raw_date = str(raw_date_raw) if raw_date_raw else ""
    try:
        parsed_date = datetime.strptime(raw_date, "%Y-%b-%d %H:%M:%S")
        last_updated = parsed_date.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        last_updated = str(date.today())
    
    # Titel
    title_tag = article.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Unknown"
    
    # Content: alle <p>-Tags → Plaintext
    # <e type="bold"> und <xref> werden automatisch entfernt
    paragraphs = article.find_all("p")
    text_parts = []
    for p in paragraphs:
        plain = p.get_text(separator=" ", strip=True)
        if plain:
            text_parts.append(plain)
    
    text = " ".join(text_parts)
    
    if not text:
        return None
    
    return {
        "title": title,
        "text": text,
        "url": full_url,
        "article_id": article_id,
        "last_updated": last_updated,
    }

# ── Markdown Building ──────────────────────────────────────────
def chunk_to_markdown(chunk: dict) -> str:
    """Formatiert einen Chunk als SUSIpedia-konformen ##-Abschnitt
    
    Args:
        chunk: Dict von xml_to_chunk()
    
    Returns:
        Markdown String:
        ```
        ## Artificial Intelligence (AI)
        
        Artificial intelligence (AI), the ability of a digital computer...
        Quelle: https://www.britannica.com/article/artificial-intelligence/9711
        
        ```
    """
    heading = chunk["title"]
    lines = [
        f"## {heading}",
        "",
        chunk["text"],
        f"Quelle: {chunk['url']}",
        "",
    ]
    return "\n".join(lines)

def get_md_filename(category: str, file_number: int) -> str:
    """Dateiname für MD-Datei
    
    Args:
        category: "science", "technology", etc.
        file_number: 1, 2, 3, ...
    
    Returns:
        "britannica_science_001.md"
    """
    return f"britannica_{category}_{file_number:03d}.md"

def build_md_file(chunks: list[dict], category: str, file_number: int) -> str:
    """Baut komplette MD-Datei aus Chunks
    
    Args:
        chunks: Liste von Chunk-Dicts
        category: Category-Name
        file_number: Datei-Nummer
    
    Returns:
        Vollständiger Markdown-Inhalt
    """
    header = f"""# Britannica Wissen — {category.title()} ({file_number:03d})
Datum: {date.today()}
Quelle: Encyclopaedia Britannica API (scope: gist)
Status: aktiv

"""
    
    body = "\n".join([chunk_to_markdown(c) for c in chunks])
    
    footer = f"\n## Stand {date.today()}\n"
    
    return header + body + footer

# ── Main Sync ──────────────────────────────────────────────────
def run_sync(api_key: str, category_id: int | None = None, update_mode: bool = False):
    """Hauptfunktion — orchestriert Fetch + Index + MD-Schreiben
    
    Args:
        api_key: API-Key
        category_id: Optional, nur diese Category fetchen
        update_mode: True = nur geänderte/neue Artikel (--update)
                     False = alle Artikel der Category (--category)
    
    Workflow:
        1. Fetch Artikelliste von API
        2. Index prüfen: welche brauchen Fetch?
        3. Artikel-XMLs holen (mit 2sec Verzögerung)
        4. In MDs schreiben (50 pro Datei)
        5. Index speichern (alle 10 Artikel)
        6. Bei Abbruch/401: alles gespeichert, --update setzt fort
    """
    
    log.info("=" * 70)
    log.info("🚀 Britannica Sync gestartet")
    log.info(f"   Modus: {'UPDATE (nur Änderungen)' if update_mode else 'FULL FETCH'}")
    log.info(f"   Category: {CATEGORY_MAP.get(category_id) if category_id else 'alle'}")
    log.info(f"   Zeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 70)
    
    index = get_index()
    
    # 1. Artikelliste holen
    log.info("\n📋 Lade Artikelliste von API...")
    api_articles = fetch_article_list(api_key, category_id)
    
    if not api_articles:
        log.warning("⚠️  Keine Artikel gefunden")
        return
    
    # 2. Filtern — was muss gefetcht werden?
    log.info(f"\n🔍 Prüfe Index: welche Artikel sind neu/geändert/Cache>30d...")
    to_fetch = [
        art for art in api_articles
        if index.needs_fetch(str(art["articleId"]), art["lastUpdated"])
    ]
    
    already_current = len(api_articles) - len(to_fetch)
    log.info(f"📊 {len(to_fetch)} zu fetchen, {already_current} bereits aktuell")
    
    if not to_fetch:
        log.info("\n✅ Alle Artikel sind aktuell — nichts zu tun")
        index.data["meta"]["last_updated"] = str(datetime.now())
        index.save()
        return
    
    # 3. Zielverzeichnis erstellen
    WISSEN_DIR.mkdir(parents=True, exist_ok=True)
    
    # 4. Fetchen + Schreiben
    log.info(f"\n🔄 Starte Fetch-Loop: {len(to_fetch)} Artikel, ~{len(to_fetch)*2}sec = ~{len(to_fetch)*2/60:.1f}min")
    log.info("   Tip: Bei API-Limit (401) — Fortschritt gespeichert, --update setzt fort\n")
    
    chunks_buffer = []
    category_name_temp = CATEGORY_MAP.get(category_id) if category_id else "unknown"
    category_name: str = category_name_temp if category_name_temp else "unknown"
    file_number = 1
    fetched_count = 0
    error_count = 0
    
    # Existierende Dateinummer ermitteln (für --resume)
    existing_files = list(WISSEN_DIR.glob(f"britannica_{category_name}_*.md"))
    if existing_files:
        last_num = max(int(f.stem.split("_")[-1]) for f in existing_files)
        file_number = last_num + 1
    
    log.info(f"📝 Schreibe nach: britannica_{category_name}_{file_number:03d}.md")
    
    try:
        for i, art in enumerate(to_fetch):
            art_id = str(art["articleId"])
            try:
                # XML fetchen
                xml = fetch_article_xml(api_key, art["articleId"])
                chunk = xml_to_chunk(xml)
                
                if chunk is None:
                    log.warning(f"   ⚠️  {art['title'][:60]} — XML parse error")
                    error_count += 1
                    continue
                
                chunks_buffer.append(chunk)
                fetched_count += 1
                
                # Index aktualisieren
                target_file = get_md_filename(category_name, file_number)
                index.add_article(art_id, {
                    "title": art["title"],
                    "lastUpdated": art["lastUpdated"][:10],
                    "category": category_name,
                    "file": target_file,
                    "fetched": str(date.today()),
                    "url": chunk["url"],
                })
                
                # MD-Datei schreiben wenn Buffer voll
                if len(chunks_buffer) >= ARTICLES_PER_FILE:
                    md_content = build_md_file(chunks_buffer, category_name, file_number)
                    md_path = WISSEN_DIR / get_md_filename(category_name, file_number)
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    log.info(f"   💾 {md_path.name} ({len(chunks_buffer)} Artikel)")
                    chunks_buffer = []
                    file_number += 1
                
                # Fortschritt
                log.info(f"   ✅ {fetched_count:4d}/{len(to_fetch):4d} — {art['title'][:50]}")
                
                # Rate-Limiting
                time.sleep(FETCH_DELAY)
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    log.warning("\n⚠️  API-Limit erreicht (401)")
                    log.info(f"   Fortschritt: {fetched_count}/{len(to_fetch)} Artikel gefetcht")
                    log.info("   Index gespeichert — nächstes Mal mit --update fortsetzen")
                    break
                error_count += 1
                log.error(f"   ❌ {art['title'][:50]} — HTTP {e.response.status_code}")
            
            except KeyboardInterrupt:
                log.warning("\n\n⏸️  Sync unterbrochen (STRG+C)")
                break
            
            except Exception as e:
                error_count += 1
                log.error(f"   ❌ {art['title'][:50]} — {str(e)[:60]}")
            
            # Index regelmäßig speichern (alle 10 Artikel)
            if fetched_count % 10 == 0:
                index.save()
        
        # Restliche Chunks schreiben
        if chunks_buffer:
            md_content = build_md_file(chunks_buffer, category_name, file_number)
            md_path = WISSEN_DIR / get_md_filename(category_name, file_number)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            log.info(f"   💾 {md_path.name} ({len(chunks_buffer)} Artikel)")
        
        # Index final speichern
        index.data["meta"]["last_full_fetch"] = str(date.today())
        index.data["meta"]["total_fetched"] = sum(
            1 for a in index.data["articles"].values() if a.get("fetched")
        )
        index.data["meta"]["last_updated"] = str(datetime.now())
        index.save()
        
        # Summary
        log.info("\n" + "=" * 70)
        log.info("🎉 Britannica Sync abgeschlossen")
        log.info(f"   ✅ {fetched_count} Artikel gefetcht")
        if error_count > 0:
            log.info(f"   ⚠️  {error_count} Fehler")
        log.info(f"   📊 {index.data['meta']['total_fetched']} Artikel gesamt im Index")
        log.info(f"   📁 Geschrieben nach: docs/wissen/britannica_*.md")
        log.info("=" * 70)
        log.info("\n💡 Nächster Schritt:")
        log.info("   python rag/ingest.py")
        log.info("   (um neue Chunks in ChromaDB zu schreiben)\n")
    
    except KeyboardInterrupt:
        log.warning("\n\n⏸️  Sync unterbrochen (STRG+C)")
        log.info("   Fortschritt wurde gespeichert")
        log.info("   Nächstes Mal mit --update weitermachen")

# ── CLI ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="SUSI Britannica Sync — Fetcht Artikel von Britannica API",
        epilog="Beispiele:\n"
               "  python -m rag.britannica_sync --category science --key key1\n"
               "  python -m rag.britannica_sync --update --key key1\n"
               "  python -m rag.britannica_sync --status",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--category",
        choices=list(CATEGORY_NAME_TO_ID.keys()),
        help="Welche Category fetchen (science, technology, ...)"
    )
    parser.add_argument(
        "--key",
        choices=["key1", "key2"],
        default="key1",
        help="Welcher API-Key aus .env (default: key1)"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Nur geänderte/neue Artikel fetchen (30-Tage-Cache-Regel)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Index-Status anzeigen"
    )
    
    args = parser.parse_args()
    
    # --status Mode
    if args.status:
        index = get_index()
        print("\n" + index.get_status() + "\n")
        return
    
    # Validierung: --category oder --update erforderlich
    if not args.category and not args.update:
        parser.error("--category oder --update erforderlich")
    
    # API-Key laden
    api_key = load_api_key(args.key)
    category_id = CATEGORY_NAME_TO_ID.get(args.category) if args.category else None
    
    # Sync starten
    run_sync(api_key, category_id, update_mode=args.update)

if __name__ == "__main__":
    main()