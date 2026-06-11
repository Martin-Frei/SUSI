# StockPredict V2 – xgb_refiner.py XGBoost Feature-Aufbereitung

**Kategorie:** Projekt  
**Projekt:** StockPredict V2  
**Stand:** 22.05.2026  
**Status:** Aktiv — Pipeline Step 6 von 9  

## Zweck von xgb_refiner.py in StockPredict V2

xgb_refiner.py liegt unter `ml-pipeline/xgb_refiner.py` und übernimmt als Pipeline Step 6 von 9 die Feature-Aufbereitung für das XGBoost-Modell in StockPredict V2. xgb_refiner.py holt die von master_engineer.py berechneten Features aus der Supabase processed_features-Tabelle, normalisiert die JSON-Struktur und bereitet die Feature-Matrix für XGBoost vor. Verarbeitete Daten werden strukturiert zurück in Supabase geschrieben.

## XGBRefiner Klasse in xgb_refiner.py

Die Klasse `XGBRefiner` in xgb_refiner.py kapselt die gesamte Feature-Aufbereitung für XGBoost in drei Hauptmethoden. `__init__()` initialisiert den Supabase-Client mit SUPABASE_KEY und lädt den konfigurierten processed-Pfad aus dem zentralen Config-Manager. `_load_from_supabase()` lädt Features für ein Symbol aus processed_features via fetch_all_from_supabase() dem zentralen Pagination-Helper. Die processed_features-Tabelle speichert Features in drei JSON-Spalten statt einer Wide Table mit 75 plus Spalten weil JSON-Columns in Supabase einfacher zu erweitern sind ohne Schema-Migration. Die JSON-Normalisierung nutzt pd.json_normalize auf die Spalten Price_Data, Indicators und Targets und kombiniert sie per pd.concat mit Date und Symbol. `_upsert_to_cloud()` trennt den DataFrame in Feature-Gruppen und uploaded strukturiert. Target-Spalten sind alles mit target im Namen plus HL_Spread_pct. Price-Spalten umfassen Close. Feature-Spalten sind alles andere außer Date und Symbol. NaN-Werte werden in None konvertiert, Records werden row-by-row für JSON-Kompatibilität aufgebaut und per Batch-Upload via Supabase Upsert hochgeladen.

## Warum XGBoost als zweites Modell in StockPredict V2

XGBoost und LSTM in StockPredict V2 sind fundamental verschiedene Modellklassen die sich gegenseitig ergänzen. LSTM ist ein rekurrentes neuronales Netz das stark bei Zeitreihen-Mustern und Long-term Dependencies ist, mit Sequenzen als Input arbeitet und wenig interpretierbar ist. XGBoost ist ein Gradient Boosting Trees Modell das stark bei tabellarischen Features und Robustheit ist, mit einzelnen Feature-Vektoren arbeitet und über Feature Importance interpretierbar ist. Zwei unterschiedliche Modellklassen im Ensemble reduzieren das Overfitting-Risiko — wenn beide Modelle einig sind ist die Prediction zuverlässiger.

## **Stand 10.06.2026**