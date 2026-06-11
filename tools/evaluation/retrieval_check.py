"""
SUSI Evaluation — Retrieval Check
==================================
Misst NUR das Retrieval, kein LLM noetig. Beantwortet die Frage:
"War der richtige Chunk ueberhaupt in den Top-K?"

Damit zerlegst du den End-to-End-Score in zwei Fehlerklassen:
    Hit  + falsche Antwort  → Generation-Problem (Prompt/Modell)
    Miss                    → Retrieval-Problem (Reranker/Hybrid Search)

Aufruf:
    python tools/evaluation/retrieval_check.py
    python tools/evaluation/retrieval_check.py --fragen tools/evaluation/testfragen_big_run.json
    python tools/evaluation/retrieval_check.py --top-k 10

Voraussetzung:
    - Ollama laeuft (bge-m3 muss gepullt sein)
    - Collection wurde vorher mit indexer.py gebaut

Ausgabe:
    - Hit Rate gesamt + pro Kategorie
    - Hit@1 / Hit@3 / Hit@K (an welcher Position stand der richtige Chunk?)
    - Miss-Liste in der Konsole
    - CSV mit allen Misses in results/ fuer detaillierte Analyse
"""

import csv
import json
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ── Pfad-Setup (identisch zu indexer.py) ─────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # SUSI/


def load_config(config_arg=None):
    """Config-Datei finden und laden (gleiche Logik wie indexer.py)."""
    candidates = [Path(config_arg)] if config_arg else [
        SCRIPT_DIR / "config.yaml",
        PROJECT_ROOT / "tools" / "evaluation" / "config.yaml",
    ]
    for p in candidates:
        if p and p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f), p
    raise FileNotFoundError("config.yaml nicht gefunden. Pfad mit --config angeben.")


def get_collection_name(embedding_model, chunk_size, overlap, separator_name):
    """Identisch zu indexer.py — muss exakt denselben Namen erzeugen."""
    model_clean = embedding_model.replace(":", "_").replace("/", "_").replace(".", "_")
    return f"susi_eval_{model_clean}_c{chunk_size}_o{overlap}_{separator_name}"


def normalisiere_quelle(source_str: str, docs_root: Path) -> str:
    """
    Macht aus dem absoluten Windows-Pfad im ChromaDB-Metadata
    (z.B. C:\\...\\SUSI\\docs\\lernen\\ml\\ml_konzepte.md)
    einen relativen Pfad mit Forward-Slashes (lernen/ml/ml_konzepte.md),
    vergleichbar mit dem quelle-Feld der Testfragen.
    """
    p = Path(source_str)
    try:
        return p.relative_to(docs_root).as_posix()
    except ValueError:
        # Fallback falls Pfad-Praefix nicht matcht (z.B. anderer Rechner)
        return p.as_posix()


def quelle_matcht(quelle: str, retrieved_rel: str) -> bool:
    """
    Prueft ob ein retrievter Chunk zur erwarteten quelle gehoert.
    Exakter Vergleich zuerst, dann Suffix-Vergleich mit Separator-Schutz
    (damit 'susi_vision.md' nicht faelschlich 'xyz_susi_vision.md' matcht).
    """
    quelle = quelle.strip().lower()
    retrieved_rel = retrieved_rel.strip().lower()
    if retrieved_rel == quelle:
        return True
    return retrieved_rel.endswith("/" + quelle)


def lade_fragen(fragen_path: Path) -> list:
    """
    Laedt Testfragen und normalisiert sie auf ein einheitliches Format:
        {id, kategorie, frage, quelle}

    Erkennt automatisch zwei Formate:
    1. testfragen_big_run.json — flache Liste mit quelle-Feld
    2. testfragen.json — verschachtelt (smoke_test + full_evaluation.kategorien)
       mit quelldatei-Feld; Kategorie steckt im Schluessel
    """
    with open(fragen_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    fragen = []
    uebersprungen = 0

    if isinstance(data, list):
        # Format 1: big_run — flache Liste
        for q in data:
            if not isinstance(q, dict) or not q.get("frage"):
                continue  # _comment-Bloecke
            if not q.get("quelle"):
                uebersprungen += 1
                continue
            fragen.append({
                "id": q.get("id", ""),
                "kategorie": q.get("kategorie", "unbekannt"),
                "frage": q["frage"],
                "quelle": q["quelle"],
            })

    elif isinstance(data, dict):
        # Format 2: verschachtelte testfragen.json
        # Smoke-Test: keine quelldatei → nicht pruefbar, wird gezaehlt
        for q in data.get("smoke_test", {}).get("fragen", []):
            if q.get("quelldatei") or q.get("quelle"):
                fragen.append({
                    "id": q.get("id", ""),
                    "kategorie": "smoke",
                    "frage": q["frage"],
                    "quelle": q.get("quelldatei") or q.get("quelle"),
                })
            else:
                uebersprungen += 1

        # full_run.fragen direkt unterstuetzen
        full_run_fragen = data.get("full_run", {}).get("fragen", [])
        if full_run_fragen:
            for q in full_run_fragen:
                if not isinstance(q, dict) or not q.get("frage"):
                    continue
                quelle = q.get("quelle") or q.get("quelldatei")
                if not quelle:
                    uebersprungen += 1
                    continue
                fragen.append({
                    "id": q.get("id", ""),
                    "kategorie": q.get("kategorie", "unbekannt"),
                    "frage": q["frage"],
                    "quelle": quelle,
                })
        kategorien = data.get("full_evaluation", {}).get("kategorien", {})
        # Auch full_run.fragen unterstuetzen
        full_run_fragen = data.get("full_run", {}).get("fragen", [])
        if full_run_fragen:
            for q in full_run_fragen:
                if not isinstance(q, dict) or not q.get("frage"):
                    continue
                quelle = q.get("quelldatei") or q.get("quelle")
                if not quelle:
                    uebersprungen += 1
                    continue
                fragen.append({"id": q.get("id", ""), "kategorie": q.get("kategorie", "unbekannt"), "frage": q["frage"], "quelle": quelle})
        for kat_name, kat in kategorien.items():
            for q in kat.get("fragen", []):
                if not q.get("frage"):
                    continue
                quelle = q.get("quelldatei") or q.get("quelle")
                if not quelle:
                    uebersprungen += 1
                    continue
                fragen.append({
                    "id": q.get("id", ""),
                    "kategorie": kat_name,
                    "frage": q["frage"],
                    "quelle": quelle,
                })
    else:
        raise ValueError(f"Unbekanntes JSON-Format in {fragen_path}")

    if uebersprungen:
        print(f"⚠️  {uebersprungen} Frage(n) ohne quelle/quelldatei uebersprungen "
              f"(keine Ground Truth pruefbar)")

    return fragen


def main():
    parser = argparse.ArgumentParser(description="SUSI Eval — Retrieval Check")
    parser.add_argument("--config", help="Pfad zur config.yaml")
    parser.add_argument("--fragen",
                        default=str(SCRIPT_DIR / "testfragen_big_run.json"),
                        help="Pfad zur Testfragen-JSON")
    parser.add_argument("--top-k", type=int, default=None,
                        help="Ueberschreibt top_k aus der Config")
    args = parser.parse_args()

    # ── Config + Parameter ────────────────────────────────────────
    config, config_path = load_config(args.config)
    de = config["data_engineering"]

    active_models = [m for m in de["embedding_models"] if m.get("active")]
    if not active_models:
        raise ValueError("Kein aktives Embedding-Modell in der Config.")
    embedding_model = active_models[0]["name"]

    chunk_size = de["chunk_sizes"][0]
    overlap = de["chunk_overlaps"][0]
    sep_name = list(de["separators"].keys())[0]
    top_k = args.top_k or config["retrieval"]["top_k_values"][0]

    collection_name = get_collection_name(embedding_model, chunk_size, overlap, sep_name)
    chroma_path = str(SCRIPT_DIR / "chroma_eval" / collection_name)
    docs_root = PROJECT_ROOT / config["meta"]["docs_path"]

    print(f"⚙️  Config     : {config_path}")
    print(f"📦 Collection : {collection_name}")
    print(f"🔢 Top-K      : {top_k}")

    if not (Path(chroma_path) / "chroma.sqlite3").exists():
        raise FileNotFoundError(
            f"Collection nicht gefunden: {chroma_path}\n"
            f"Erst indexer.py laufen lassen."
        )

    # ── Testfragen laden (Auto-Detect: big_run oder testfragen.json) ──
    fragen_path = Path(args.fragen)
    fragen = lade_fragen(fragen_path)
    print(f"❓ Fragen     : {len(fragen)} pruefbar aus {fragen_path.name}")

    # ── ChromaDB oeffnen (exakt wie indexer.py) ──────────────────
    from langchain_ollama import OllamaEmbeddings
    from langchain_chroma import Chroma

    embeddings = OllamaEmbeddings(model=embedding_model)
    db = Chroma(
        collection_name=collection_name,
        persist_directory=chroma_path,
        embedding_function=embeddings
    )

    # ── Retrieval pro Frage ──────────────────────────────────────
    print(f"\n🔍 Pruefe Retrieval fuer {len(fragen)} Fragen...\n")

    hits_at = defaultdict(int)        # Position des ersten Treffers (1-basiert)
    kategorie_stats = defaultdict(lambda: {"hits": 0, "total": 0})
    misses = []

    for i, q in enumerate(fragen, 1):
        # similarity_search = gleiche Methode wie im grid_run (algorithm: similarity)
        results = db.similarity_search(q["frage"], k=top_k)

        retrieved = [normalisiere_quelle(r.metadata.get("source", ""), docs_root)
                     for r in results]

        # An welcher Position steht der richtige Chunk?
        rank = None
        for pos, rel in enumerate(retrieved, 1):
            if quelle_matcht(q["quelle"], rel):
                rank = pos
                break

        kat = q["kategorie"]
        kategorie_stats[kat]["total"] += 1

        if rank:
            hits_at[rank] += 1
            kategorie_stats[kat]["hits"] += 1
            status = f"✅ Hit@{rank}"
        else:
            misses.append({
                "frage_id": q.get("id", f"frage_{i}"),
                "kategorie": kat,
                "frage": q["frage"],
                "quelle_erwartet": q["quelle"],
                "quellen_retrieved": " | ".join(retrieved),
            })
            status = "❌ MISS"

        print(f"  [{i:>3}/{len(fragen)}] {status:<10} {q.get('id', ''):<16} {q['frage'][:60]}")

    # ── Auswertung ───────────────────────────────────────────────
    total = len(fragen)
    total_hits = sum(hits_at.values())
    hit_rate = total_hits / total if total else 0

    print(f"\n{'='*70}")
    print(f"📊 RETRIEVAL CHECK — {collection_name}")
    print(f"{'='*70}")
    print(f"   Hit Rate gesamt : {total_hits}/{total} = {hit_rate:.1%}")

    # Hit@K kumulativ: stand der Treffer auf Platz 1? In den Top 3?
    kumulativ = 0
    print(f"\n   Position des richtigen Chunks:")
    for k in range(1, top_k + 1):
        kumulativ += hits_at.get(k, 0)
        print(f"     Hit@{k} : {kumulativ}/{total} = {kumulativ/total:.1%}")

    print(f"\n   Pro Kategorie:")
    for kat, s in sorted(kategorie_stats.items()):
        rate = s["hits"] / s["total"] if s["total"] else 0
        print(f"     {kat:<12} : {s['hits']:>3}/{s['total']:<3} = {rate:.1%}")

    if misses:
        print(f"\n❌ {len(misses)} MISSES — richtige Datei NICHT in Top-{top_k}:")
        print(f"{'─'*70}")
        for m in misses:
            print(f"   {m['frage_id']:<16} erwartet: {m['quelle_erwartet']}")
            print(f"   {'':16} Frage   : {m['frage'][:70]}")
            print(f"   {'':16} bekommen: {m['quellen_retrieved'][:100]}")
            print()

        # Misses als CSV fuer detaillierte Analyse
        results_dir = SCRIPT_DIR / "results"
        results_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        csv_path = results_dir / f"retrieval_misses_{ts}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(misses[0].keys()))
            writer.writeheader()
            writer.writerows(misses)
        print(f"💾 Miss-Liste gespeichert: {csv_path}")

    # ── Interpretation ───────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"💡 INTERPRETATION")
    print(f"   Hit Rate {hit_rate:.0%} bedeutet: maximal {hit_rate:.0%} Korrektheit")
    print(f"   sind End-to-End ueberhaupt erreichbar — der Rest sind")
    print(f"   Retrieval-Fehler, die kein Prompt der Welt fixen kann.")
    if hit_rate < 0.85:
        print(f"   → Prioritaet: Retrieval verbessern (Reranker / Hybrid Search)")
    else:
        print(f"   → Retrieval ist solide. Prioritaet: Generation (Prompt/Modell)")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()