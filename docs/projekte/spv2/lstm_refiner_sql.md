# StockPredict V2 – lstm_refiner_sql.py LSTM Feature-Aufbereitung

**Kategorie:** Projekt  
**Projekt:** StockPredict V2  
**Stand:** 22.05.2026  
**Status:** Aktiv — Pipeline Step 4 von 9  

## Zweck von lstm_refiner_sql.py in StockPredict V2

lstm_refiner_sql.py liegt unter `ml-pipeline/lstm_refiner_sql.py` und übernimmt als Pipeline Step 4 von 9 die Feature-Aufbereitung für das LSTM-Modell in StockPredict V2. lstm_refiner_sql.py holt die von master_engineer.py berechneten Features aus Supabase, normalisiert sie mit einem vortrainierten Scaler und bereitet sie als zeitliche Input-Sequenzen für das LSTM-Modell vor. Das LSTM braucht Daten als 3D-Tensor mit den Dimensionen Samples, Zeitschritte und Features.

## Unterschied zu xgb_refiner.py in StockPredict V2

Der LSTM Refiner und der XGBoost Refiner in StockPredict V2 unterscheiden sich grundlegend im Input-Format. Der LSTM Refiner arbeitet mit Zeitfenster-Sequenzen als 3D-Tensor, lädt den Scaler aus Supabase Storage und hat explizite Zeitabhängigkeit mit konfigurierbarer Sequenz-Länge. Der XGBoost Refiner arbeitet mit einzelnen Feature-Vektoren als 2D-Matrix, verwendet Inline-Normalisierung und hat keine Zeitabhängigkeit.

## Sequenz-Aufbereitung für LSTM in lstm_refiner_sql.py

LSTM-Modelle lernen zeitliche Abhängigkeiten. Der StockPredict V2 LSTM Refiner erstellt für jeden Prediction-Tag ein Zeitfenster aus den letzten N Handelstagen — Tag T-N bis Tag T ergibt die Prediction für T+1. Die Sequenz-Länge ist in config.yaml konfiguriert.

## Scaler in lstm_refiner_sql.py

Der Scaler in lstm_refiner_sql.py — MinMaxScaler oder StandardScaler — wird beim Training gespeichert und muss für die Inference identisch angewendet werden. Er wird in Step 3 aus Supabase Storage geladen weil er modellspezifisch ist und der zentrale Ablageort sicherstellt dass Railway-Pipeline und lokale Scripts denselben Scaler nutzen.

## Verbindung zu anderen Steps in StockPredict V2

Der Datenfluss in StockPredict V2 läuft von master_engineer.py über processed_features in Supabase zu lstm_refiner_sql.py der Sequenzen und Skalierung vornimmt, dann zu lstm_predictor.py der LSTM Predictions generiert und in die predictions-Tabelle in Supabase schreibt.

## Warum LSTM für Aktienvorhersage in StockPredict V2

LSTM (Long Short-Term Memory) ist speziell für Zeitreihendaten entwickelt und bietet drei entscheidende Vorteile gegenüber Alternativen. LSTM hat ein Gedächtnis und kann relevante Informationen über viele Zeitschritte hinweg behalten. LSTM lernt durch das Forget Gate unwichtige Informationen zu vergessen. LSTM löst das Vanishing Gradient Problem klassischer RNNs bei langen Sequenzen.

Als Alternative wurde der Temporal Fusion Transformer evaluiert aber abgelehnt weil Transformer deutlich mehr Trainingsdaten und Rechenleistung benötigen — für 12 Symbole mit etwa 4 Jahren Historie ist LSTM pragmatischer. Prophet von Facebook wurde ebenfalls evaluiert aber abgelehnt weil es für Trend- und Saisonalitäts-Forecasting optimiert ist und nicht für tagesaktuelle Richtungsvorhersagen mit technischen Indikatoren als Features.

## **Stand 10.06.2026**