"""
SUSI Evaluation — Indexer
=========================
Baut EINMALIG alle ChromaDB Collections fuer den Grid-Lauf auf.
Jede Kombination aus (embedding_model, chunk_size, overlap, separator) 
bekommt eine eigene Collection.

Aufruf:
    python tools/evaluation/indexer.py
    python tools/evaluation/indexer.py --config tools/evaluation/config.yaml
    python tools/evaluation/indexer.py --dry-run   # nur Kombinationen anzeigen
"""

import os
import sys
import yaml
import json
import argparse
import itertools
from pathlib import Path
from datetime import datetime


# ── Pfad-Setup ────────────────────────────────────────────────────
# Script kann von verschiedenen Orten aufgerufen werden
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # SUSI/

def find_config(config_arg=None):
    """Config-Datei finden"""
    if config_arg:
        return Path(config_arg)
    # Standard-Pfade versuchen
    candidates = [
        SCRIPT_DIR / "config.yaml",
        PROJECT_ROOT / "tools" / "evaluation" / "config.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("config.yaml nicht gefunden. Pfad mit --config angeben.")


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_collection_name(embedding_model, chunk_size, overlap, separator_name):
    """Eindeutiger Collection-Name fuer ChromaDB"""
    # ChromaDB erlaubt nur alphanumerisch + Unterstriche + Bindestriche
    model_clean = embedding_model.replace(":", "_").replace("/", "_").replace(".", "_")
    return f"susi_eval_{model_clean}_c{chunk_size}_o{overlap}_{separator_name}"


def get_active_combinations(config):
    """Alle aktiven Parameter-Kombinationen berechnen"""
    de = config["data_engineering"]
    
    active_models = [
        m for m in de["embedding_models"] if m.get("active", False)
    ]
    chunk_sizes = de["chunk_sizes"]
    overlaps = de["chunk_overlaps"]
    separators = de["separators"]
    
    combos = list(itertools.product(
        active_models,
        chunk_sizes,
        overlaps,
        separators.items()  # (name, separator_list)
    ))
    return combos


def build_collection(docs_path, collection_name, embedding_model_name, 
                     chunk_size, overlap, separators, embedding_device="cpu"):
    """Eine ChromaDB Collection aufbauen"""
    from langchain_ollama import OllamaEmbeddings
    from langchain_chroma import Chroma
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.document_loaders import TextLoader
    
    print(f"\n  📦 Collection: {collection_name}")
    print(f"     Modell: {embedding_model_name} | Chunk: {chunk_size} | Overlap: {overlap}")
    
    # Embeddings initialisieren
    embeddings = OllamaEmbeddings(
        model=embedding_model_name,
        # CPU-Offloading wenn konfiguriert
    )
    
    # Collection-Pfad
    chroma_path = str(SCRIPT_DIR / "chroma_eval" / collection_name)
    
    # Pruefen ob Collection schon existiert
    index_file = Path(chroma_path) / "chroma.sqlite3"
    if index_file.exists():
        print(f"     ✅ Existiert bereits — uebersprungen")
        return {"status": "skipped", "collection": collection_name}
    
    # Text-Splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=separators
    )
    
    # Alle Markdown-Dateien laden
    docs_dir = Path(docs_path)
    if not docs_dir.exists():
        print(f"     ⚠️  docs-Ordner nicht gefunden: {docs_path}")
        return {"status": "error", "collection": collection_name, "error": "docs nicht gefunden"}
    
    all_files = list(docs_dir.rglob("*.md"))
    if not all_files:
        print(f"     ⚠️  Keine .md Dateien in {docs_path}")
        return {"status": "error", "collection": collection_name, "error": "keine .md Dateien"}
    
    print(f"     📚 {len(all_files)} Dateien werden verarbeitet...")
    
    # ChromaDB initialisieren
    db = Chroma(
        collection_name=collection_name,
        persist_directory=chroma_path,
        embedding_function=embeddings
    )
    
    total_chunks = 0
    errors = []
    
    for filepath in all_files:
        try:
            loader = TextLoader(str(filepath), encoding="utf-8")
            documents = loader.load()
            chunks = splitter.split_documents(documents)
            
            # Metadata anreichern
            for i, chunk in enumerate(chunks):
                chunk.metadata["source"] = str(filepath)
                chunk.metadata["chunk_index"] = i
                chunk.metadata["collection"] = collection_name
                chunk.metadata["chunk_size"] = chunk_size
                chunk.metadata["overlap"] = overlap
            
            # IDs generieren
            source_clean = str(filepath).replace("\\", "_").replace("/", "_").replace(".", "_")
            ids = [f"{source_clean}_{i}" for i in range(len(chunks))]
            
            db.add_documents(documents=chunks, ids=ids)
            total_chunks += len(chunks)
            
        except Exception as e:
            errors.append({"file": str(filepath), "error": str(e)})
    
    print(f"     ✅ {total_chunks} Chunks indexiert")
    if errors:
        print(f"     ⚠️  {len(errors)} Fehler")
    
    return {
        "status": "built",
        "collection": collection_name,
        "chunks": total_chunks,
        "files": len(all_files),
        "errors": errors
    }


def save_index_manifest(results, output_path):
    """Manifest aller gebauten Collections speichern"""
    manifest = {
        "erstellt": datetime.now().isoformat(),
        "collections": results
    }
    manifest_path = output_path / "index_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\n📋 Manifest gespeichert: {manifest_path}")


def main():
    parser = argparse.ArgumentParser(description="SUSI Eval — Indexer")
    parser.add_argument("--config", help="Pfad zur config.yaml")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Nur Kombinationen anzeigen, nichts bauen")
    parser.add_argument("--force", action="store_true",
                        help="Bestehende Collections ueberschreiben")
    args = parser.parse_args()
    
    # Config laden
    config_path = find_config(args.config)
    config = load_config(config_path)
    print(f"⚙️  Config: {config_path}")
    
    # Docs-Pfad bestimmen (relativ zum Projekt-Root)
    docs_path = PROJECT_ROOT / config["meta"]["docs_path"]
    
    # Kombinationen berechnen
    combos = get_active_combinations(config)
    
    print(f"\n📊 Kombinationen fuer den Indexer:")
    print(f"   Aktive Embedding-Modelle : {len([m for m in config['data_engineering']['embedding_models'] if m.get('active')])}")
    print(f"   Chunk Sizes              : {config['data_engineering']['chunk_sizes']}")
    print(f"   Overlaps                 : {config['data_engineering']['chunk_overlaps']}")
    print(f"   Separatoren              : {list(config['data_engineering']['separators'].keys())}")
    print(f"   ─────────────────────────────────────")
    print(f"   Collections gesamt       : {len(combos)}")
    
    if args.dry_run:
        print(f"\n🔍 DRY RUN — Collection-Namen:")
        for model, chunk_size, overlap, (sep_name, _) in combos:
            name = get_collection_name(model["name"], chunk_size, overlap, sep_name)
            print(f"   {name}")
        return
    
    # Output-Verzeichnis
    output_dir = SCRIPT_DIR / "chroma_eval"
    output_dir.mkdir(exist_ok=True)
    
    # Collections bauen
    print(f"\n🏗️  Baue {len(combos)} Collections...")
    print(f"   docs-Pfad: {docs_path}")
    print(f"   Ausgabe  : {output_dir}")
    
    embedding_device = config["data_engineering"].get("embedding_device", "cpu")
    results = []
    
    for i, (model, chunk_size, overlap, (sep_name, separators)) in enumerate(combos, 1):
        print(f"\n[{i}/{len(combos)}]", end="")
        
        collection_name = get_collection_name(model["name"], chunk_size, overlap, sep_name)
        
        # Force: bestehende loeschen
        if args.force:
            chroma_path = output_dir / collection_name
            if chroma_path.exists():
                import shutil
                shutil.rmtree(chroma_path)
                print(f" 🗑️  Alte Collection geloescht")
        
        result = build_collection(
            docs_path=str(docs_path),
            collection_name=collection_name,
            embedding_model_name=model["name"],
            chunk_size=chunk_size,
            overlap=overlap,
            separators=separators,
            embedding_device=embedding_device
        )
        result["embedding_model"] = model["name"]
        result["chunk_size"] = chunk_size
        result["overlap"] = overlap
        result["separator"] = sep_name
        results.append(result)
    
    # Manifest speichern
    save_index_manifest(results, SCRIPT_DIR)
    
    # Zusammenfassung
    built = sum(1 for r in results if r["status"] == "built")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    
    print(f"\n{'='*50}")
    print(f"✅ Fertig!")
    print(f"   Gebaut    : {built}")
    print(f"   Uebersprungen: {skipped}")
    print(f"   Fehler    : {errors}")
    print(f"\nNaechster Schritt: python tools/evaluation/grid_run.py")


if __name__ == "__main__":
    main()