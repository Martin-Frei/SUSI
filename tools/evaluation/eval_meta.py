"""
SUSI Evaluation — Meta-Generator
==================================
Erzeugt eine kompakte _meta.csv nach jedem Grid-Lauf.
Fasst Config-Parameter, Auto-Scorer-Ergebnisse und Top-Kombinationen
in einer einzigen Zeile zusammen — für schnellen Überblick ohne die
große CSV öffnen zu müssen.

Aufruf standalone:
    python tools/evaluation/eval_meta.py --csv tools/evaluation/results/eval_xxx.csv

    Config ist optional beim Standalone-Aufruf:
    - MIT --config: Config-Parameter (Embeddings, Chunks, k-Werte etc.) werden
      aus der YAML gelesen und in die Meta-CSV geschrieben.
      Nur sinnvoll wenn die YAML noch dem Stand des Laufs entspricht.
    - OHNE --config: Score-Analyse, Metriken, Kategorien und beste Kombination
      werden trotzdem vollständig aus der CSV berechnet.
      Config-Spalten bleiben leer — für alte CSVs die richtige Wahl.

Aufruf aus grid_run.py (automatisch, Config immer korrekt):
    from eval_meta import schreibe_meta
    schreibe_meta(csv_path=output_path, config=config)

Output:
    eval_20260611_1400_meta.csv  (neben der Original-CSV)
"""

import csv
import json
import statistics
import argparse
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional


# ── Hilfsfunktionen ───────────────────────────────────────────────

def lade_csv(csv_path: str) -> list:
    """CSV als Liste von Dicts laden."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV nicht gefunden: {csv_path}")
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def lade_config(config_path: str) -> dict:
    """config.yaml laden."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def baue_meta_pfad(csv_path: str) -> str:
    """_meta.csv Pfad aus CSV-Pfad ableiten."""
    p = Path(csv_path)
    return str(p.parent / p.stem) + "_meta.csv"


# ── Analyse-Funktionen ────────────────────────────────────────────

def analysiere_scores(daten: list) -> dict:
    """
    Score-Verteilung und Korrektheit berechnen.

    Korrektheit = Score >= 2.
    Score-Verteilung 0-5 aus score_manuell.
    Grauzone = Einträge ohne score_manuell.
    """
    gesamt = len(daten)
    verteilung = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    korrekt = 0
    grauzone = 0
    auto_count = 0

    for row in daten:
        score_raw = row.get("score_manuell", "")
        if score_raw in ("", None):
            grauzone += 1
            continue
        try:
            score = int(float(score_raw))
        except ValueError:
            grauzone += 1
            continue

        if score in verteilung:
            verteilung[score] += 1
        if score >= 2:
            korrekt += 1

        # Auto vs manuell
        auto_raw = row.get("auto_score", "")
        if auto_raw not in ("", None):
            auto_count += 1

    bewertet = gesamt - grauzone
    korrektheit_pct = round(korrekt / bewertet * 100, 1) if bewertet > 0 else 0
    auto_pct = round(auto_count / bewertet * 100, 1) if bewertet > 0 else 0
    grauzone_pct = round(grauzone / gesamt * 100, 1) if gesamt > 0 else 0

    return {
        "gesamt_laeufe": gesamt,
        "korrektheit_pct": korrektheit_pct,
        "korrekt_n": korrekt,
        "grauzone_pct": grauzone_pct,
        "auto_pct": auto_pct,
        "score_0": verteilung[0],
        "score_1": verteilung[1],
        "score_2": verteilung[2],
        "score_3": verteilung[3],
        "score_4": verteilung[4],
        "score_5": verteilung[5],
    }


def analysiere_metriken(daten: list) -> dict:
    """BERTScore und ROUGE-L Durchschnitte berechnen."""
    bert_werte = []
    rouge_werte = []
    delta_werte = []

    for row in daten:
        try:
            if row.get("antwort_bert"):
                bert_werte.append(float(row["antwort_bert"]))
            if row.get("antwort_rougeL"):
                rouge_werte.append(float(row["antwort_rougeL"]))
            if row.get("delta"):
                delta_werte.append(float(row["delta"]))
        except ValueError:
            continue

    return {
        "bert_avg": round(statistics.mean(bert_werte), 4) if bert_werte else None,
        "rouge_avg": round(statistics.mean(rouge_werte), 4) if rouge_werte else None,
        "delta_avg": round(statistics.mean(delta_werte), 4) if delta_werte else None,
    }


def analysiere_kategorien(daten: list) -> dict:
    """Korrektheit pro Kategorie."""
    kategorien = {}
    for row in daten:
        kat = row.get("kategorie", "?")
        score_raw = row.get("score_manuell", "")
        if score_raw in ("", None):
            continue
        try:
            score = int(float(score_raw))
        except ValueError:
            continue

        if kat not in kategorien:
            kategorien[kat] = {"korrekt": 0, "gesamt": 0}
        kategorien[kat]["gesamt"] += 1
        if score >= 2:
            kategorien[kat]["korrekt"] += 1

    result = {}
    for kat, werte in sorted(kategorien.items()):
        g = werte["gesamt"]
        k = werte["korrekt"]
        result[f"kat_{kat}_pct"] = round(k / g * 100, 1) if g > 0 else 0
        result[f"kat_{kat}_n"] = f"{k}/{g}"
    return result


def beste_kombination(daten: list) -> dict:
    """Die beste Parameter-Kombination nach Korrektheit."""
    gruppen = {}
    for row in daten:
        score_raw = row.get("score_manuell", "")
        if score_raw in ("", None):
            continue
        try:
            score = int(float(score_raw))
        except ValueError:
            continue

        key = (
            row.get("embedding_model", ""),
            row.get("chunk_size", ""),
            row.get("top_k", ""),
            row.get("algorithm", ""),
            row.get("llm_model", ""),
            row.get("system_prompt_name", ""),
        )
        if key not in gruppen:
            gruppen[key] = {"korrekt": 0, "gesamt": 0}
        gruppen[key]["gesamt"] += 1
        if score >= 2:
            gruppen[key]["korrekt"] += 1

    if not gruppen:
        return {"beste_kombi": "keine Daten"}

    beste = max(gruppen.items(), key=lambda x: x[1]["korrekt"] / x[1]["gesamt"])
    key, werte = beste
    pct = round(werte["korrekt"] / werte["gesamt"] * 100, 1)

    return {
        "beste_embedding": key[0],
        "beste_chunk": key[1],
        "beste_k": key[2],
        "beste_algo": key[3],
        "beste_llm": key[4],
        "beste_prompt": key[5],
        "beste_korrektheit": f"{pct}% ({werte['korrekt']}/{werte['gesamt']})",
    }


def extrahiere_config_params(config: dict) -> dict:
    """Aktive Parameter aus config.yaml extrahieren."""
    de = config.get("data_engineering", {})
    ret = config.get("retrieval", {})
    gen = config.get("generation", {})

    aktive_embeddings = [
        m["name"] for m in de.get("embedding_models", [])
        if m.get("active", False)
    ]
    aktive_llms = [
        m["name"] for m in gen.get("llm_models", [])
        if m.get("active", False)
    ]
    aktive_prompts = [
        p["name"] for p in gen.get("system_prompts", [])
        if p.get("active", False)
    ]
    aktive_algos = [
        a["name"] for a in ret.get("algorithms", [])
        if a.get("active", False)
    ]

    return {
        "config_embeddings": "|".join(aktive_embeddings),
        "config_chunks": "|".join(str(c) for c in de.get("chunk_sizes", [])),
        "config_overlap": "|".join(str(o) for o in de.get("chunk_overlaps", [])),
        "config_top_k": "|".join(str(k) for k in ret.get("top_k_values", [])),
        "config_algos": "|".join(aktive_algos),
        "config_llms": "|".join(aktive_llms),
        "config_prompts": "|".join(aktive_prompts),
        "config_temperatures": "|".join(str(t) for t in gen.get("temperatures", [])),
    }


# ── Hauptfunktion ─────────────────────────────────────────────────

def schreibe_meta(csv_path: str, config: Optional[dict] = None,
                  config_path: Optional[str] = None) -> str:
    """
    Meta-CSV generieren und schreiben.

    Kann entweder ein bereits geladenes config-Dict oder einen
    config_path entgegennehmen.

    Args:
        csv_path:    Pfad zur eval_DATUM.csv
        config:      Bereits geladene config.yaml als Dict (aus grid_run.py)
        config_path: Pfad zur config.yaml (für standalone-Aufruf)

    Returns:
        Pfad zur geschriebenen _meta.csv
    """
    print(f"\n📊 Generiere Meta-CSV...")

    # Daten laden
    daten = lade_csv(csv_path)
    if not daten:
        print("  ⚠️  CSV leer — keine Meta-CSV generiert")
        return ""

    # Config laden falls nicht übergeben
    if config is None and config_path:
        config = lade_config(config_path)

    # Analyse
    scores = analysiere_scores(daten)
    metriken = analysiere_metriken(daten)
    kategorien = analysiere_kategorien(daten)
    beste = beste_kombination(daten)

    # Config-Parameter
    config_params = {}
    if config:
        config_params = extrahiere_config_params(config)

    # Alle Felder zusammenführen
    meta_row = {
        "csv_quelle": Path(csv_path).name,
        "erstellt_am": datetime.now().strftime("%Y-%m-%d %H:%M"),
        **scores,
        **metriken,
        **kategorien,
        **beste,
        **config_params,
    }

    # Schreiben
    meta_path = baue_meta_pfad(csv_path)
    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(meta_row.keys()))
        writer.writeheader()
        writer.writerow(meta_row)

    print(f"  ✅ Meta-CSV geschrieben: {Path(meta_path).name}")
    print(f"     Korrektheit: {scores['korrektheit_pct']}% "
          f"({scores['korrekt_n']}/{scores['gesamt_laeufe']})")
    print(f"     Beste Kombi: {beste.get('beste_korrektheit', '?')} — "
          f"{beste.get('beste_embedding', '?')} | "
          f"c{beste.get('beste_chunk', '?')} | "
          f"k{beste.get('beste_k', '?')} | "
          f"{beste.get('beste_prompt', '?')}")

    return meta_path


# ── Standalone ────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Standalone-Aufruf für bestehende CSVs.

    Beispiel:
        python tools/evaluation/eval_meta.py --csv tools/evaluation/results/eval_xxx.csv
        python tools/evaluation/eval_meta.py --csv eval_xxx.csv --config config.yaml
    """
    parser = argparse.ArgumentParser(description="SUSI Eval — Meta-CSV Generator")
    parser.add_argument("--csv", required=True, help="Pfad zur eval CSV")
    parser.add_argument("--config", default=None, help="Pfad zur config.yaml (optional)")
    args = parser.parse_args()

    meta_path = schreibe_meta(
        csv_path=args.csv,
        config_path=args.config
    )

    if meta_path:
        print(f"\n✅ Fertig: {meta_path}")