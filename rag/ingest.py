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
# RecursiveCharacterTextSplitter removed — replaced by split_by_headings()
# from langchain_text_splitters import RecursiveCharacterTextSplitter
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


def split_by_headings(text: str, source: str, max_chunk_chars: int = 1500) -> list[Document]:
    """
    Splittet eine Markdown-Datei an jedem ## Heading.

    Jeder Chunk bekommt den Datei-Header (alles vor dem ersten ##)
    vorangestellt, damit er self-contained ist:
      - Dateiname/Titel
      - Datum, Status, Kategorie
      - Quelle (bei Britannica-Dateien)

    Gefiltert werden:
      - ## **Stand ...** Footer (SUSIpedia-Konvention)
      - Leere Sektionen

    Übergroße Chunks (> max_chunk_chars) werden zusätzlich an
    Absatzgrenzen (\\n\\n) aufgesplittet. Der Header und die
    Heading-Zeile werden in jeden Sub-Chunk injiziert.

    Fallback: Wenn die Datei keine ## Headings hat, wird der
    gesamte Text als ein Chunk zurückgegeben (ggf. aufgesplittet).
    """
    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)

    # Header = alles vor dem ersten ## (Titel, Datum, Status etc.)
    header = parts[0].strip() if parts else ""
    sections = parts[1:] if len(parts) > 1 else []

    # Fallback: keine ## Headings → ganzer Text als ein Chunk
    if not sections:
        content = text.strip()
        if content:
            return _split_oversized(content, header, source, max_chunk_chars)
        return []

    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # ## **Stand DD.MM.YYYY** Footer rausfiltern
        if re.match(r"^## \*\*Stand\b", section):
            continue
        # Header + Section = self-contained Chunk
        content = f"{header}\n\n{section}" if header else section
        chunks.extend(_split_oversized(content, header, source, max_chunk_chars))

    return chunks


def _split_oversized(content: str, header: str, source: str,
                     max_chars: int) -> list[Document]:
    """Bricht einen Chunk an Absatzgrenzen (\\n\\n) auf wenn er
    max_chars überschreitet. Header und Heading-Zeile werden in
    jeden Sub-Chunk injiziert damit jeder self-contained bleibt.
    Einzelne Absätze die immer noch zu groß sind werden zusätzlich
    an Satzgrenzen aufgebrochen."""
    if len(content) <= max_chars:
        return [Document(page_content=content, metadata={"source": source})]

    # Heading-Zeile extrahieren (## ...) — wird in jeden Sub-Chunk injiziert
    lines = content.split("\n", 1)
    heading_line = lines[0] if lines[0].startswith("## ") else ""
    body = lines[1].strip() if len(lines) > 1 and heading_line else content

    # An Absatzgrenzen splitten
    paragraphs = re.split(r"\n\n+", body)

    # Overhead für Header + Heading in jedem Sub-Chunk
    overhead = len(header) + len(heading_line) + 4

    chunks = []
    current_parts = []
    current_len = overhead

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Einzelner Absatz zu groß → an Satzgrenzen aufbrechen
        if len(para) + overhead > max_chars:
            # Erst aktuellen Buffer abschließen
            if current_parts:
                _flush_chunk(chunks, current_parts, header, heading_line, source)
                current_parts = []
                current_len = overhead
            # Absatz in Sätze splitten
            sentences = re.split(r"(?<=\. )", para)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if current_parts and (current_len + len(sentence) + 1) > max_chars:
                    _flush_chunk(chunks, current_parts, header, heading_line, source)
                    current_parts = []
                    current_len = overhead
                current_parts.append(sentence)
                current_len += len(sentence) + 1
            continue

        added_len = len(para) + 2

        if current_parts and (current_len + added_len) > max_chars:
            _flush_chunk(chunks, current_parts, header, heading_line, source)
            current_parts = []
            current_len = overhead

        current_parts.append(para)
        current_len += added_len

    if current_parts:
        _flush_chunk(chunks, current_parts, header, heading_line, source)

    return chunks


def _flush_chunk(chunks: list, parts: list, header: str,
                 heading_line: str, source: str):
    """Baut einen Chunk aus Parts zusammen und hängt ihn an die Liste."""
    body_text = "\n\n".join(parts)
    chunk_parts = [p for p in [header, heading_line, body_text] if p]
    chunk_content = "\n\n".join(chunk_parts)
    chunks.append(Document(page_content=chunk_content, metadata={"source": source}))


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

        # Heading-Split: jedes ## wird ein eigener Chunk.
        # Der Datei-Header (alles vor dem ersten ##) wird in jeden
        # Chunk injiziert damit jeder Chunk self-contained ist.
        chunks = split_by_headings(raw_text, filepath_str)

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