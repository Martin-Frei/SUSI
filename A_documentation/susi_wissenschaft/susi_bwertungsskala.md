Hast du in diesen chat für mich eiene Score definition aus unseren grid läufen ?? nur ja oder nein

Manuelle Bewertungsskala:

0 = Falsch — inhaltlich falsch oder halluziniert
1 = Teilweise — Kernaussage stimmt, aber unvollständig oder ungenau
2 = Korrekt — vollständig und faktisch richtig

Auto-Score:

0 = automatisch bei Ausweichantworten wie:
    "Dazu fehlt mir noch was in der SUSIpedia"
    "Diese Information ist nicht verfügbar"
    "Ich habe keine Information"

Automatische Metriken:

BERTScore  → semantische Ähnlichkeit (0-1, >0.85 sehr gut)
ROUGE-L    → lexikalische Ähnlichkeit (schärfer bei falschen Namen/Fakten)
Delta      → antwort_bert - max_chunk_bert
             negativ = Generation-Problem (Chunk hatte Info, LLM verlor sie)
             positiv = Halluzination-Verdacht

Score-Definition SUSI RAG Evaluation

Skala: 0 bis 3

0 — Ausweichantwort
    SUSI antwortet "Diese Information ist nicht verfügbar"
    oder "Dazu fehlt mir noch was in der SUSIpedia"
    → automatisch erkannt (Auto-Scorer)

1 — Falsch oder unvollständig
    Antwort halluziniert, falscher Chunk gefunden,
    oder Kernaussage fehlt trotz vorhandener Info

2 — Korrekt aus Chunk
    Inhalt stimmt, aus dem richtigen Dokument,
    keine falschen Fakten

3 — RAG perfekt
    ROUGE-L > 0.10 + BERTScore > 0.65
    automatisch vom Auto-Scorer vergeben

Evaluationsläufe:

Smoke-Läufe (4 Fragen):
    eval_20260524_2115  768 Läufe  Baseline (nomic+bge)
    eval_20260525_0715  194 Läufe  bge+mxbai, c500-1500
    eval_20260525_1835  384 Läufe  bge+mxbai, c500-1000
    eval_20260525_2235  128 Läufe  bge+mxbai, c750-1500
    eval_20260527_0841  128 Läufe  bge+mxbai, c850-1300
    eval_20260527_0930   64 Läufe  bge, praezise_alt vs neu
    eval_20260527_1050   64 Läufe  Top-K Vergleich k3/5/7/9
    eval_20260527_1141   32 Läufe  CoT + hybrid Prompts
    eval_20260527_1154   80 Läufe  alle 5 Prompts
    eval_20260527_1218  160 Läufe  alle 5 Prompts + k3/k5

Full-Run (40 Fragen):
    eval_20260527_2234  240 Läufe  bge, c1000, k5, 3 Prompts

Bewertungsmethode:

Auto-Scorer:    ~86% aller Einträge automatisch
Human-in-Loop:  ~14% manuelle Nachbewertung
Metriken:       BERTScore (semantisch) + ROUGE-L (lexikalisch)
                + Delta (antwort_bert - max_chunk_bert)

Ja — aus deiner evaluator.py: 0 = Falsch, 1 = Teilweise, 2 = Korrekt (manuell + Judge), plus Auto-Score 0 für Ausweichantworten