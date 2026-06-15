"""
ingest.py
=========
Liest alle Markdown-Dateien aus der SUSIpedia und speichert sie als
Vektoren in ChromaDB. Nur geänderte oder neue Dateien werden verarbeitet
(Upsert-Strategie mit MD5-Hashing).

KOMMENTAR-BLÖCKE (NEU):
    Abschnitte in Markdown-Dateien die mit ##** beginnen und mit **## enden
    werden beim Indexieren vollständig übersprungen. Diese Blöcke sind für
    persönliche Notizen, offene Punkte oder temporäre Kommentare gedacht
    die nicht in ChromaDB landen sollen.

    Beispiel in einer .md Datei:
        ## Normaler Abschnitt
        Dieser Text wird indexiert und ist für SUSI abrufbar.

        ##** Offene Punkte **##
        - Das hier wird ignoriert
        - Nur Kommentar für den Autor
        **##

    Alles zwischen ##** und **## wird aus dem Text entfernt bevor
    die Chunks erzeugt werden.

CHUNK-STRATEGIE:
    Persönliche Ordner (standard): chunk_size=300, overlap=50
    Technische Ordner (coding, technik, lernen): chunk_size=500, overlap=100
    Die Ordner-Erkennung läuft automatisch über TECHNICAL_FOLDERS.

STELLSCHRAUBEN:
    DOCS_PATH           → Pfad zur SUSIpedia (relativ zum Projektroot)
    CHROMA_PATH         → Pfad zur ChromaDB
    HASH_FILE           → Pfad zur Hash-Datei für Änderungserkennung
    CHUNK_SIZE_DEFAULT  → Chunk-Größe für persönliche Ordner
    CHUNK_SIZE_TECH     → Chunk-Größe für technische Ordner
    CHUNK_OVERLAP_DEFAULT → Overlap für persönliche Ordner
    CHUNK_OVERLAP_TECH  → Overlap für technische Ordner
    TECHNICAL_FOLDERS   → Liste der Ordner die als technisch gelten
    COMMENT_START       → Öffnungs-Tag für Kommentar-Blöcke
    COMMENT_END         → Schließ-Tag für Kommentar-Blöcke
    EMBED_MODEL         → Ollama Embedding-Modell

AUSFÜHREN:
    python rag/ingest.py

ALLES NEU INDEXIEREN:
    Remove-Item -Recurse -Force chroma_db\\*
    python rag/ingest.py
"""

from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from pathlib import Path
import hashlib
import json
import os
import re

# ── Stellschrauben ────────────────────────────────────────────────────────────

DOCS_PATH   = "docs"
CHROMA_PATH = "chroma_db"
HASH_FILE   = "chroma_db/doc_hashes.json"

# Chunk-Größen
CHUNK_SIZE_DEFAULT    = 300
CHUNK_SIZE_TECH       = 500
CHUNK_OVERLAP_DEFAULT = 50
CHUNK_OVERLAP_TECH    = 100

# Ordner die als technisch gelten → größere Chunks
TECHNICAL_FOLDERS = ["coding", "technik", "lernen"]

# Kommentar-Block Tags
COMMENT_START = "##**"
COMMENT_END   = "**##"

# Embedding-Modell
EMBED_MODEL = "nomic-embed-text"

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def get_file_hash(filepath: str) -> str:
    """MD5 Hash einer Datei berechnen."""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def load_hashes() -> dict:
    """Gespeicherte Hashes laden."""
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r") as f:
            return json.load(f)
    return {}


def save_hashes(hashes: dict):
    """Aktuelle Hashes speichern."""
    with open(HASH_FILE, "w") as f:
        json.dump(hashes, f, indent=2)


def generate_chunk_id(source: str, chunk_index: int) -> str:
    """Eindeutige ID pro Chunk generieren."""
    return f"{source}::chunk_{chunk_index}"


def is_technical(filepath_str: str) -> bool:
    """
    Prüft ob eine Datei in einem technischen Ordner liegt.
    Entscheidet welche Chunk-Größe verwendet wird.
    """
    return any(folder in filepath_str for folder in TECHNICAL_FOLDERS)


def remove_comment_blocks(text: str) -> str:
    """
    Entfernt alle Kommentar-Blöcke aus dem Text.
    Alles zwischen COMMENT_START und COMMENT_END wird gelöscht.

    Beispiel:
        ##** Offene Punkte **##
        - wird ignoriert
        **##
    """
    # Regex: alles zwischen ##** und **## entfernen (auch über mehrere Zeilen)
    pattern = re.escape(COMMENT_START) + r".*?" + re.escape(COMMENT_END)
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    # Doppelte Leerzeilen bereinigen die nach dem Entfernen entstehen
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# ── Haupt-Funktion ────────────────────────────────────────────────────────────

def ingest_docs():
    print("🔍 Prüfe Dokumentänderungen...")

    saved_hashes  = load_hashes()
    current_hashes = {}
    changed_files  = []
    new_files      = []

    all_files = list(Path(DOCS_PATH).rglob("*.md"))

    for filepath in all_files:
        filepath_str  = str(filepath)
        current_hash  = get_file_hash(filepath_str)
        current_hashes[filepath_str] = current_hash

        if filepath_str not in saved_hashes:
            new_files.append(filepath_str)
            print(f"  🆕 Neu: {filepath}")
        elif saved_hashes[filepath_str] != current_hash:
            changed_files.append(filepath_str)
            print(f"  📝 Geändert: {filepath}")

    files_to_process = new_files + changed_files

    if not files_to_process:
        print("✅ Keine Änderungen – ChromaDB ist aktuell!")
        save_hashes(current_hashes)
        return

    print(f"\n📚 Verarbeite {len(files_to_process)} Datei(en)...")

    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    total_chunks   = 0
    skipped_blocks = 0

    for filepath_str in files_to_process:
        print(f"\n  ⚙️  Verarbeite: {filepath_str}")

        # Alte Chunks löschen
        try:
            existing = db.get(where={"source": filepath_str})
            if existing and existing["ids"]:
                db.delete(ids=existing["ids"])
                print(f"  🗑️  {len(existing['ids'])} alte Chunks gelöscht")
        except Exception as e:
            print(f"  ⚠️  Keine alten Chunks gefunden: {e}")

        # Datei lesen
        try:
            raw_text = Path(filepath_str).read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ❌ Fehler beim Lesen: {e}")
            continue

        # Kommentar-Blöcke entfernen
        comment_count = raw_text.count(COMMENT_START)
        if comment_count > 0:
            raw_text = remove_comment_blocks(raw_text)
            skipped_blocks += comment_count
            print(f"  🚫 {comment_count} Kommentar-Block(e) übersprungen")

        # Chunk-Größe je nach Ordner-Typ
        if is_technical(filepath_str):
            chunk_size    = CHUNK_SIZE_TECH
            chunk_overlap = CHUNK_OVERLAP_TECH
        else:
            chunk_size    = CHUNK_SIZE_DEFAULT
            chunk_overlap = CHUNK_OVERLAP_DEFAULT

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["## ", "### ", "\n\n", "\n"]
        )

        # Text in Document-Objekt wrappen für LangChain
        doc = Document(page_content=raw_text, metadata={"source": filepath_str})
        chunks = splitter.split_documents([doc])

        # Leere Chunks rausfiltern
        chunks = [c for c in chunks if c.page_content.strip()]

        if not chunks:
            print("  ⚠️  Keine verwertbaren Chunks – Datei übersprungen")
            continue

        # Metadata sicherstellen
        for chunk in chunks:
            chunk.metadata["source"] = filepath_str

        # IDs generieren und in ChromaDB speichern
        ids = [generate_chunk_id(filepath_str, i) for i in range(len(chunks))]
        db.add_documents(documents=chunks, ids=ids)
        total_chunks += len(chunks)
        print(f"  ✅ {len(chunks)} Chunks indexiert")

    save_hashes(current_hashes)

    print(f"\n🎉 Fertig! {total_chunks} Chunks in ChromaDB gespeichert")
    print(f"📊 Gesamt: {len(all_files)} Dateien überwacht")
    if skipped_blocks > 0:
        print(f"🚫 {skipped_blocks} Kommentar-Block(e) insgesamt übersprungen")


if __name__ == "__main__":
    ingest_docs()