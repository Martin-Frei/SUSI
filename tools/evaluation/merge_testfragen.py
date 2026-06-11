"""
Fuegt neue Testfragen in testfragen_big_run.json ein.
Ausfuehren: python merge_testfragen.py
"""

import json
from pathlib import Path

# Pfade anpassen
BASIS_JSON = Path(r"C:\Users\tsinn\VSCode\Repos\SUSI_neu\tools\evaluation\testfragen_big_run.json")
AUSGABE_JSON = Path(r"C:\Users\tsinn\VSCode\Repos\SUSI_neu\tools\evaluation\testfragen_big_run.json")

# Neue Fragen
neue_fragen = [
    {"_comment": "=== NEUE FRAGEN AB 10.06.2026 ==="},
    {"_comment": "=== LERNEN — ai_act_vertiefung.md ==="},
    {
        "id": "lernen_aiact_01",
        "kategorie": "lernen",
        "quelle": "lernen/ai/ai_act_vertiefung.md",
        "frage": "Was ist der Unterschied zwischen DSGVO und EU AI Act?",
        "referenz": "Die DSGVO schützt personenbezogene Daten und ist technologieneutral. Der EU AI Act schützt vor Auswirkungen von KI-Systemen auf Grundrechte und ist explizit KI-bezogen mit Risikostufen. Beide gelten kumulativ — wer ein KI-System mit personenbezogenen Daten betreibt muss beide gleichzeitig einhalten."
    },
    {
        "id": "lernen_aiact_02",
        "kategorie": "lernen",
        "quelle": "lernen/ai/ai_act_vertiefung.md",
        "frage": "Was gilt seit 08.02.2026 laut EU AI Act?",
        "referenz": "Seit 08.02.2026 gilt die Vollanwendung für Hochrisiko-Systeme nach Anhang III. Das betrifft alle Anbieter und Betreiber von Hochrisiko-KI."
    },
    {
        "id": "lernen_aiact_03",
        "kategorie": "lernen",
        "quelle": "lernen/ai/ai_act_vertiefung.md",
        "frage": "Was passiert wenn man ein fremdes KI-Modell substantiell anpasst?",
        "referenz": "Wer ein fremdes Modell substantiell anpasst, umbenannt oder den Zweck wesentlich ändert rutscht nach Art. 25 AI Act in die Anbieter-Rolle mit erweiterten Pflichten wie Dokumentation, Konformitätsbewertung und Post-Market-Monitoring."
    },
    {
        "id": "lernen_aiact_04",
        "kategorie": "lernen",
        "quelle": "lernen/ai/ai_act_vertiefung.md",
        "frage": "Was ist der häufigste KI-Mythos im Mittelstand?",
        "referenz": "Der häufigste Mythos ist die Annahme dass wenn die Server in Frankfurt stehen man DSGVO-konform ist. Hosting-Ort allein sagt nichts über DSGVO-Konformität — Frankfurt ist eine notwendige aber keine hinreichende Bedingung."
    },
    {"_comment": "=== LERNEN — ki_deployment_tco.md ==="},
    {
        "id": "lernen_deploy_01",
        "kategorie": "lernen",
        "quelle": "lernen/ai/ki_deployment_tco.md",
        "frage": "Ab wie vielen Dauernutzern lohnt sich On-Premise Self-Hosting gegenüber API?",
        "referenz": "Self-Hosting wird gegenüber API erst wirtschaftlich wenn der Token-Verbrauch grob um Faktor 40 bis 50 über der Baseline liegt. Das entspricht 5.000 bis 8.000 Dauernutzern oder massiver 24/7-Agenten-Last."
    },
    {
        "id": "lernen_deploy_02",
        "kategorie": "lernen",
        "quelle": "lernen/ai/ki_deployment_tco.md",
        "frage": "Was kostet Claude Sonnet 4.6 über Bedrock pro Million Tokens?",
        "referenz": "Claude Sonnet 4.6 über Bedrock kostet 3,00 Dollar pro Million Input-Tokens und 15,00 Dollar pro Million Output-Tokens. Stand April 2026."
    },
    {
        "id": "lernen_deploy_03",
        "kategorie": "lernen",
        "quelle": "lernen/ai/ki_deployment_tco.md",
        "frage": "Was sind die fünf KI-Deployment-Stufen für Unternehmen?",
        "referenz": "Stufe 1 ist Free-Tier ohne AVV. Stufe 2 ist Business-Lizenz mit AVV und Admin-Features. Stufe 3 ist API beim Hyperscaler in EU-Regionen. Stufe 4 ist Open-Weight bei europäischem Anbieter ohne US-Mutter. Stufe 5 ist On-Premise mit eigenem GPU-Server."
    },
    {
        "id": "lernen_deploy_04",
        "kategorie": "lernen",
        "quelle": "lernen/ai/ki_deployment_tco.md",
        "frage": "Warum hebt Sovereign Cloud das CLOUD Act Risiko nicht vollständig auf?",
        "referenz": "Alle drei großen Hyperscaler haben eine US-Muttergesellschaft. Der US CLOUD Act und FISA Section 702 gelten auf Ebene der Konzernmutter unabhängig vom physischen Speicherort der Daten. Sovereign Cloud reduziert das Risiko deutlich löst das juristische Grundproblem aber nicht vollständig."
    },
    {"_comment": "=== PROJEKTE — GMM neue Dateien ==="},
    {
        "id": "proj_gmm_dach_01",
        "kategorie": "projekte",
        "quelle": "coding/gmm/dach_pipeline_13032026.md",
        "frage": "Wie berechnet der GMM Aggregator Option B den finalen Score?",
        "referenz": "Option B berechnet zuerst einen Score pro Topic (finance, geopolitics, energy, politics, general) und bildet dann den Durchschnitt aller Topic-Scores mit gleichem Gewicht. Der Vorteil ist dass viele Artikel zu einem Thema nicht den gesamten Score dominieren."
    },
    {
        "id": "proj_gmm_dach_02",
        "kategorie": "projekte",
        "quelle": "coding/gmm/dach_pipeline_13032026.md",
        "frage": "Was war das Schweizer Sentiment im GMM am 13.03.2026 und warum?",
        "referenz": "Die Schweiz hatte -0.06 bearish mit finance +0.13 positiv. Das positive Finance-Signal erklärt sich durch den CHF als Safe Haven — der Schweizer Franken steigt in Krisen weshalb das CH Finance-Signal positiv war während geopolitics bei -0.66 lag."
    },
    {
        "id": "proj_gmm_dash_01",
        "kategorie": "projekte",
        "quelle": "coding/gmm/dashboard_v1_13032026.md",
        "frage": "Wie viele Zonen hat das GMM Dashboard und wie sind sie aufgeteilt?",
        "referenz": "Das GMM Dashboard hat 28 Zonen aufgeteilt in vier Regionen: Europa mit 8 Zonen, Americas mit 7 Zonen, Asia mit 7 Zonen und Africa/Middle East mit 6 Zonen."
    },
    {
        "id": "proj_gmm_eu_01",
        "kategorie": "projekte",
        "quelle": "coding/gmm/europe_complete_15032026.md",
        "frage": "Wie viele Feeds und Länder deckt GMM Europe Complete ab?",
        "referenz": "GMM Europe Complete vom 15.03.2026 umfasst 52 aktive Feeds mit circa 1.411 unique Artikeln pro Run und 35 aktive Länder in 8 europäischen Regionen."
    },
    {
        "id": "proj_gmm_expand_01",
        "kategorie": "projekte",
        "quelle": "coding/gmm/global_expansion_15032026.md",
        "frage": "Was ist der Hybrid-Ansatz für Sentiment-Klassifikation in GMM nach der SpaCy Integration?",
        "referenz": "Stage 1 verwendet Keywords mit mindestens 2 Matches für schnelle spezifische Klassifikation. Stage 2 verwendet SpaCy als Fallback nur für nicht klassifizierte Artikel. Nach der Integration sank Finance von 87% auf 38%."
    },
    {
        "id": "proj_gmm_night_01",
        "kategorie": "projekte",
        "quelle": "coding/gmm/nightshift_28regions_15032026.md",
        "frage": "Was hat GMM am 15.03.2026 als Meilenstein erreicht?",
        "referenz": "Am 15.03.2026 wurden alle 28 geplanten Zonen an einem einzigen Tag abgedeckt. Das System umfasst 163 aktive Feeds mit circa 4.055 unique Artikeln pro Run auf 6 Kontinenten."
    },
    {
        "id": "proj_gmm_night_02",
        "kategorie": "projekte",
        "quelle": "coding/gmm/nightshift_28regions_15032026.md",
        "frage": "Wie sieht das Monetarisierungsmodell für GMM aus?",
        "referenz": "Free Tier bietet Weltkarte, Top Headlines und 24 Stunden Verzögerung. Pro Tier für 99 Euro pro Jahr bietet Echtzeit-Daten, Email Alerts und API Zugang. Enterprise Tier bietet Custom Alerts, Webhooks und White Label."
    },
    {
        "id": "proj_gmm_klass_01",
        "kategorie": "projekte",
        "quelle": "coding/gmm/klassifikation_deepseek.md",
        "frage": "Welche drei Optionen wurden für die GMM Klassifikation der general-Artikel evaluiert?",
        "referenz": "Option 1 ist DeepSeek Batch API — schnell, günstig und sofort realisierbar. Option 2 ist pgvector auf Supabase — zukunftssicher aber mehr Aufwand. Option 3 ist lokal mit Ollama — kostenlos aber nur wenn der PC läuft. Kurzfristig wurde DeepSeek Batch API gewählt."
    },
    {"_comment": "=== PROJEKTE — SPV2 Architektur ==="},
    {
        "id": "proj_spv2_arch_01",
        "kategorie": "projekte",
        "quelle": "coding/stockpredict/spv2_architektur.md",
        "frage": "Was sind die vier Kern-Komponenten von StockPredict V2?",
        "referenz": "Die vier Kern-Komponenten sind DataHandler, MasterEngineer, die Enrichment Pipeline und der Enhanced Backtester mit 12 Trading-Strategien."
    },
    {
        "id": "proj_spv2_arch_02",
        "kategorie": "projekte",
        "quelle": "coding/stockpredict/spv2_architektur.md",
        "frage": "Was ist der Holy Grail Indicator in StockPredict V2?",
        "referenz": "Der xlf_zscore ist der Holy Grail Indicator in StockPredict V2. Ein Z-Score größer gleich 1.0 aktiviert den Trade-Filter. Das Holy Grail Signal bei Z-Score größer gleich 2.0 wird intern nie öffentlich kommuniziert."
    },
    {"_comment": "=== SUSI — susi_dsgvo_ki.md ==="},
    {
        "id": "susi_dsgvo_01",
        "kategorie": "susi",
        "quelle": "coding/susi/susi_dsgvo_ki.md",
        "frage": "Warum ist SUSI DSGVO-konform by design?",
        "referenz": "SUSI verarbeitet alle Daten vollständig lokal. Kein einziger Byte verlässt den eigenen Rechner. Damit braucht man keinen AVV, es gibt keinen Drittanbieter und kein DSGVO-Problem für den persönlichen Einsatz."
    },
    {
        "id": "susi_dsgvo_02",
        "kategorie": "susi",
        "quelle": "coding/susi/susi_dsgvo_ki.md",
        "frage": "Wann gelten DSGVO-Regeln auch für SUSI?",
        "referenz": "Sobald SUSI im Auftrag anderer eingesetzt wird und dabei deren personenbezogene Daten verarbeitet gelten dieselben DSGVO-Regeln wie für jedes andere Werkzeug. Dann braucht man eine Rechtsgrundlage, gegebenenfalls einen AVV und muss Betroffenenrechte sicherstellen."
    }
]

# JSON laden
print(f"Lade {BASIS_JSON}...")
with open(BASIS_JSON, encoding="utf-8") as f:
    data = json.load(f)

# Fragen vor dem Merge zählen
vorher = len([f for f in data["full_run"]["fragen"] if "frage" in f])
print(f"Fragen vorher: {vorher}")

# Neue Fragen anhängen
data["full_run"]["fragen"].extend(neue_fragen)

# Fragen nach dem Merge zählen
nachher = len([f for f in data["full_run"]["fragen"] if "frage" in f])
print(f"Fragen nachher: {nachher}")
print(f"Neu hinzugefügt: {nachher - vorher}")

# Speichern
with open(AUSGABE_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Gespeichert: {AUSGABE_JSON}")

# Validierung
with open(AUSGABE_JSON, encoding="utf-8") as f:
    check = json.load(f)
print("JSON Validierung: OK")
