"""
chunk_audit.py — Zeigt alle Chunks in ChromaDB mit Größen.
Markiert Chunks über dem Schwellenwert (default: 1000 chars).

Ausführen:
    python tools/evaluation/chunk_audit.py
    python tools/evaluation/chunk_audit.py --limit 1500
    python tools/evaluation/chunk_audit.py --only-oversized
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

# Projekt-Root für Config-Import
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from rag.config import load_config
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma


def main():
    parser = argparse.ArgumentParser(description="Chunk-Audit für ChromaDB")
    parser.add_argument("--limit", type=int, default=1000,
                        help="Schwellenwert in chars (default: 1000)")
    parser.add_argument("--only-oversized", action="store_true",
                        help="Nur übergroße Chunks anzeigen")
    parser.add_argument("--top", type=int, default=None,
                        help="Nur die N größten Chunks anzeigen")
    args = parser.parse_args()

    cfg = load_config()
    chroma_path = cfg["retrieval"]["chroma_path"]
    embed_model = cfg["retrieval"]["embedding_model"]

    print(f"📊 Chunk-Audit — ChromaDB: {chroma_path}")
    print(f"   Schwellenwert: {args.limit} chars\n")

    embeddings = OllamaEmbeddings(model=embed_model)
    db = Chroma(persist_directory=chroma_path, embedding_function=embeddings)

    # Alle Chunks laden
    collection = db.get(include=["documents", "metadatas"])
    docs = collection["documents"]
    metas = collection["metadatas"]

    if not docs:
        print("❌ Keine Chunks in ChromaDB gefunden.")
        return

    # Daten sammeln
    chunks = []
    for doc, meta in zip(docs, metas):
        source = meta.get("source", "?")
        chars = len(doc)
        chunks.append((chars, source, doc))

    # Nach Größe sortieren (größte zuerst)
    chunks.sort(key=lambda x: x[0], reverse=True)

    # ── Übergroße Chunks ──────────────────────────────────────────
    oversized = [(c, s, d) for c, s, d in chunks if c > args.limit]

    if oversized:
        print(f"🚨 {len(oversized)} Chunks über {args.limit} chars:\n")
        print(f"  {'Chars':>7}  {'Faktor':>6}  Quelle")
        print(f"  {'─'*7}  {'─'*6}  {'─'*50}")
        for chars, source, doc in oversized:
            faktor = chars / args.limit
            # Kürzen auf Ordner/Dateiname
            short = str(Path(source)).replace("docs\\", "").replace("docs/", "")
            preview = doc[:80].replace("\n", " ")
            print(f"  {chars:>7}  {faktor:>5.1f}×  {short}")
            print(f"           └─ {preview}...")
        print()
    else:
        print(f"✅ Keine Chunks über {args.limit} chars!\n")

    if args.only_oversized:
        return

    # ── Statistik pro Ordner ──────────────────────────────────────
    folder_stats = defaultdict(lambda: {"count": 0, "total": 0, "max": 0, "over": 0})

    for chars, source, doc in chunks:
        # Ersten Unterordner extrahieren (docs/lernen/... → lernen)
        parts = Path(source).parts
        try:
            docs_idx = list(parts).index("docs")
            folder = parts[docs_idx + 1] if len(parts) > docs_idx + 1 else "root"
        except ValueError:
            folder = "?"

        folder_stats[folder]["count"] += 1
        folder_stats[folder]["total"] += chars
        folder_stats[folder]["max"] = max(folder_stats[folder]["max"], chars)
        if chars > args.limit:
            folder_stats[folder]["over"] += 1

    print(f"📁 Statistik pro Ordner:\n")
    print(f"  {'Ordner':<15} {'Chunks':>7} {'Ø Chars':>8} {'Max':>7} {'Über':>5}")
    print(f"  {'─'*15} {'─'*7} {'─'*8} {'─'*7} {'─'*5}")

    for folder in sorted(folder_stats.keys()):
        s = folder_stats[folder]
        avg = s["total"] // s["count"] if s["count"] else 0
        over_marker = f"⚠ {s['over']}" if s['over'] > 0 else "✅"
        print(f"  {folder:<15} {s['count']:>7} {avg:>8} {s['max']:>7} {over_marker:>5}")

    # ── Gesamtstatistik ───────────────────────────────────────────
    total = len(chunks)
    avg_all = sum(c for c, _, _ in chunks) // total if total else 0
    max_all = chunks[0][0] if chunks else 0
    min_all = chunks[-1][0] if chunks else 0

    print(f"\n📈 Gesamt: {total} Chunks")
    print(f"   Ø {avg_all} chars | Min {min_all} | Max {max_all}")
    print(f"   Übergroß (>{args.limit}): {len(oversized)}")

    # ── Top N ─────────────────────────────────────────────────────
    if args.top:
        n = min(args.top, len(chunks))
        print(f"\n🔝 Top {n} größte Chunks:\n")
        for i, (chars, source, doc) in enumerate(chunks[:n]):
            short = str(Path(source)).replace("docs\\", "").replace("docs/", "")
            print(f"  {i+1:>3}. {chars:>7} chars | {short}")


if __name__ == "__main__":
    main()