"""
ingest.py
=========
Liest alle Markdown-Dateien aus der SUSIpedia und speichert sie als
Vektoren in ChromaDB. Nur geänderte oder neue Dateien werden verarbeitet
(Upsert-Strategie mit MD5-Hashing).

Konfiguration läuft über rag/susi_config.yaml — keine hardcodierten Werte.

KOMMENTAR-BLÖCKE:
    Abschnitte zwischen ##** und **## werden beim Indexieren übersprungen.

AUSFÜHREN:
    python rag/ingest.py

ALLES NEU INDEXIEREN:
    Remove-Item -Recurse -Force chroma_db\\*
    python rag/ingest.py
"""

from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from pathlib import Path
import hashlib
import json
import os
import re
import yaml

# ── Config laden ──────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "susi_config.yaml"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_config()

# ── Stellschrauben aus Config ─────────────────────────────────────
DOCS_PATH   = cfg["paths"]["docs"]
CHROMA_PATH = cfg["retrieval"]["chroma_path"]
HASH_FILE   = f"{CHROMA_PATH}/doc_hashes.json"
EMBED_MODEL = cfg["retrieval"]["embedding_model"]

# Chunk-Größen aus Config (mit Fallback auf bewährte Werte)
ingest_cfg = cfg.get("ingest", {})
CHUNK_SIZE_DEFAULT    = ingest_cfg.get("chunk_size_default", 1000)
CHUNK_SIZE_TECH       = ingest_cfg.get("chunk_size_tech", 1000)
CHUNK_OVERLAP_DEFAULT = ingest_cfg.get("chunk_overlap_default", 50)
CHUNK_OVERLAP_TECH    = ingest_cfg.get("chunk_overlap_tech", 50)

# Ordner die als technisch gelten
TECHNICAL_FOLDERS = ingest_cfg.get("technical_folders", ["coding", "technik", "lernen"])

# Kommentar-Block Tags
COMMENT_START = "##**"
COMMENT_END   = "**##"

# ── Hilfsfunktionen ───────────────────────────────────────────────

def get_file_hash(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def load_hashes() -> dict:
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r") as f:
            return json.load(f)
    return {}

def save_hashes(hashes: dict):
    with open(HASH_FILE, "w") as f:
        json.dump(hashes, f, indent=2)

def generate_chunk_id(source: str, chunk_index: int) -> str:
    return f"{source}::chunk_{chunk_index}"

def is_technical(filepath_str: str) -> bool:
    return any(folder in filepath_str for folder in TECHNICAL_FOLDERS)

def remove_comment_blocks(text: str) -> str:
    pattern = re.escape(COMMENT_START) + r".*?" + re.escape(COMMENT_END)
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# ── Haupt-Funktion ────────────────────────────────────────────────

def ingest_docs():
    print(f"⚙️  Config: {CONFIG_PATH}")
    print(f"   Embedding : {EMBED_MODEL}")
    print(f"   ChromaDB  : {CHROMA_PATH}")
    print(f"   Chunks    : default={CHUNK_SIZE_DEFAULT} | tech={CHUNK_SIZE_TECH}")
    print()
    print("🔍 Prüfe Dokumentänderungen...")

    saved_hashes   = load_hashes()
    current_hashes = {}
    changed_files  = []
    new_files      = []

    all_files = list(Path(DOCS_PATH).rglob("*.md"))

    for filepath in all_files:
        filepath_str = str(filepath)
        current_hash = get_file_hash(filepath_str)
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

        doc = Document(page_content=raw_text, metadata={"source": filepath_str})
        chunks = splitter.split_documents([doc])
        chunks = [c for c in chunks if c.page_content.strip()]

        if not chunks:
            print(f"  ⚠️  Keine verwertbaren Chunks – Datei übersprungen")
            continue

        for chunk in chunks:
            chunk.metadata["source"] = filepath_str

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