# StockPredict V2 – enricher.py Railway Predictions Enricher loakl

**Kategorie:** Projekt  
**Projekt:** StockPredict V2  
**Stand:** 22.05.2026  
**Status:** Aktiv — Pipeline Step 8 von 9  

## Zweck von enricher.py in StockPredict V2

enricher.py liegt unter `ml-pipeline/enricher.py` und übernimmt als Pipeline Step 8 von 9 das Anreichern der ML-Predictions mit Marktkontext und HG Indicator. Der StockPredict V2 Enricher holt alle noch nicht enrichten Predictions aus Supabase und fügt Marktkontext hinzu: VIX-Volatilität, XLF-Sektor-Indikatoren inklusive Z-Score, Bollinger Bands und Regime, die HG Indicator Klassifizierung und den LSTM Model Health Status. Alles wird per Upsert zurück in die predictions-Tabelle geschrieben.

## RailwayEnricher Klasse in enricher.py

Die Klasse `RailwayEnricher` in enricher.py enthält alle Methoden des StockPredict V2 Enrichers.

## __init__ in RailwayEnricher

`__init__()` lädt config.yaml und initialisiert den Supabase-Client mit SUPABASE_URL und SUPABASE_SERVICE_KEY aus den Environment Variables.

## _fetch_predictions in RailwayEnricher

`_fetch_predictions()` holt nur Predictions wo xlf_zscore IS NULL also noch nicht enriched und date_for größer gleich 2026-01-01 mit Limit 500. Der IS NULL Filter verhindert doppeltes Verarbeiten bereits enrichter Rows — ohne ihn würden bei jedem Pipeline-Run alle historischen Daten neu berechnet was die Laufzeit von 25 Minuten auf 2,5 Sekunden reduziert hat.

## _fetch_market_data in RailwayEnricher

`_fetch_market_data()` ist ein generischer Fetch aus einer beliebigen Supabase-Tabelle für ein Symbol. Er gibt einen nach Datum sortierten DataFrame zurück mit Limit 500 Rows. Ein generischer Fetch ist wiederverwendbar für VIX, XLF und zukünftige Symbole statt Code-Duplikation mit separaten Methoden.

## add_vix_data in RailwayEnricher

`add_vix_data()` mergt den VIX Closing-Preis auf die Predictions mit einem Plus-1 Business Day Shift. Der VIX von Tag T entspricht dem Marktumfeld für die Prediction am Tag T+1 weil die Pipeline um Mitternacht läuft und Predictions für den nächsten Handelstag generiert. Der VIX-Wert wird zusätzlich als explizite Spalte in predictions benötigt für Dashboard-Darstellung und Strategy-Filterung.

## add_xlf_regime in RailwayEnricher

`add_xlf_regime()` berechnet alle XLF-Sektor-Indikatoren und die HG Indicator Klassifizierung. Die berechneten Felder sind xlf_ma5, ma10, ma21 und ma50 als Moving Averages, xlf_zscore als Close minus MA21 geteilt durch Std21, xlf_bb_upper und lower als Bollinger Bands mit MA21 plus minus 2 mal Std21, xlf_bb_pct als Position im Bollinger Band zwischen 0 und 1, xlf_bb_width als Bandbreite relativ zu MA21, xlf_z_delta als Z-Score Differenz zum Vortag, xlf_z_trend als IMPROVING, FALLING oder STAGNATING, xlf_regime SLOW auf Basis MA10 vs MA50 mit 10 bis 13 Tagen Lag, xlf_regime_fast FAST auf Basis MA5 vs MA21 mit 3 bis 5 Tagen Lag sowie hg_logic mit den Werten STRONG_BUY, STOCK_STRENGTH, AVOID_WEAKNESS, WAIT und NEUTRAL.

Die HG Indicator Logic bestimmt den hg_logic-Wert anhand des Z-Scores und Trends. Der Z-Score Threshold von 1.0 stammt aus dem verifizierten Backtest über Januar 2022 bis Februar 2026 mit 1.551 Trades — unterhalb von 1.0 sinkt die Hit Rate signifikant. Bei Z-Score unter 1.0 gilt WAIT. Bei Trend IMPROVING gilt STRONG_BUY. Bei Trend FALLING oder STAGNATING und xgb_conf über 0.48 gilt STOCK_STRENGTH, sonst AVOID_WEAKNESS. Der Fallback ist NEUTRAL.

## add_model_health in RailwayEnricher

`add_model_health()` holt den aktuellsten LSTM-Training-Status pro Symbol aus beta_audit_log mit den Feldern status als PASSED, WARNING oder FAILED, f1_macro und val_loss. groupby("symbol").first() ermittelt den neuesten Eintrag pro Symbol und mappt ihn auf alle Prediction-Rows des jeweiligen Symbols.

## save_enriched_predictions in RailwayEnricher

`save_enriched_predictions()` schreibt die enrichten Daten per Upsert zurück in predictions mit Conflict-Resolution auf symbol und date_for, Batch-Size 1.000, NaN zu None Konvertierung weil Supabase kein Python-NaN akzeptiert und Timestamp zu String Konvertierung. Upsert statt Insert stellt sicher dass bei mehrfachem Lauf bestehende Rows sauber überschrieben werden statt Duplikate zu erzeugen.

## run_enrichment und run_enricher in enricher.py

`run_enrichment()` ist die Hauptmethode und orchestriert fetch, add_vix, add_xlf_regime, add_model_health und save sequenziell. `run_enricher()` ist der Railway Entry Point der von alpha.py Step 8 aufgerufen wird.

## **Stand 10.06.2026**