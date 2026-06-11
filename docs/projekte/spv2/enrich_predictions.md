# StockPredict V2 – enrich_predictions.py Offline CSV-Enricher

**Kategorie:** Projekt  
**Projekt:** StockPredict V2  
**Stand:** 22.05.2026  
**Status:** Aktiv — Legacy Dev-Tool, nicht Teil der Railway-Pipeline  

## Zweck von enrich_predictions.py in StockPredict V2

enrich_predictions.py liegt unter `ml-pipeline/enrich_predictions.py` und ist ein lokales Dev-Tool in StockPredict V2 das Enrichment auf Basis lokaler CSV-Dateien für Backtests durchführt. enrich_predictions.py ist ein Legacy-Script aus der SPV2-Entwicklungsphase. Es liest lokale CSV-Dateien statt Supabase und schreibt eine predictions_enriched.csv. Es wird für lokale Backtests und Analysen verwendet und ist nicht Teil der Railway-Pipeline. Der Output predictions_enriched.csv ist der Input für simulate_top_n_hg.py.

## Unterschied zum Railway Enricher in StockPredict V2

Der Railway Enricher und der CSV-Enricher in StockPredict V2 unterscheiden sich in mehreren Aspekten. Der Railway Enricher liest Input aus Supabase predictions, Marktdaten aus Supabase ohlcv_data, schreibt Output per Supabase Upsert, bezieht Model Health aus beta_audit_log und führt einen Business Day Shift durch. Der CSV-Enricher liest dagegen aus predictions.csv, bezieht Marktdaten aus VIX.csv und XLF.csv, schreibt Output in predictions_enriched.csv, bezieht Model Health aus LSTM Training-Log-Files und führt keinen Business Day Shift durch da er für Offline-Analyse gedacht ist.

## Konfiguration der Pfade in enrich_predictions.py

Die Pfade in enrich_predictions.py werden als Konstanten definiert damit sie zentral geändert werden können. PREDICTIONS_CSV zeigt auf die Input-Datei, OUTPUT_CSV auf die Ausgabedatei, VIX_CSV und XLF_CSV auf die Marktdaten und LOG_DIR mit LOG_PATTERN auf die LSTM Training-Logs.

## Funktionen in enrich_predictions.py

Die StockPredict V2 enrich_predictions.py Pipeline besteht aus fünf Hauptfunktionen die sequenziell aufgerufen werden. `load_predictions()` lädt predictions.csv mit parse_dates auf date_for und gibt einen DataFrame zurück. `add_vix()` lädt VIX.csv, renamed auf vix_close und führt einen Left-Join auf date_for durch ohne Business Day Shift weil die Daten bei Offline-Analyse bereits auf das korrekte Datum normalisiert sind. `add_xlf_regime()` berechnet identisch zum Railway Enricher MA5, MA10, MA21, MA50, Z-Score, Bollinger Bands, xlf_z_delta, xlf_z_trend, xlf_regime und hg_logic. `parse_training_logs()` parst LSTM Training-Log-Files via Regex und extrahiert pro Symbol lstm_health, lstm_f1, lstm_val_loss und lstm_neutral_pct — statt Supabase beta_audit_log weil dieses Script ohne Supabase-Connection funktionieren soll. `add_health_data()` matched Health-Daten per Forward-Fill auf Prediction-Daten pro Symbol. `save_enriched()` speichert predictions_enriched.csv mit Original-Spaltenreihenfolge und gibt einen Preview der ersten 3 Rows aus.

## **Stand 10.06.2026**