# StockPredict V2 – Projektübersicht

**Kategorie:** Projekt  
**Projekt:** StockPredict V2  
**Stand:** 22.05.2026  
**Status:** Aktiv — produktiv auf Railway  

## Was StockPredict V2 ist

StockPredict V2 ist eine vollautomatisierte ML-Pipeline zur täglichen Vorhersage von Kursbewegungen UP, DOWN oder NEUTRAL für 12 US-Bankaktien. Das System läuft produktiv auf Railway, nutzt Supabase als PostgreSQL-Backend und Django als Frontend.

## Universum und Daten in StockPredict V2

StockPredict V2 deckt 12 US-Bankaktien ab: AXP, BAC, BLK, C, COF, GS, JPM, MS, PNC, TFC, USB und WFC. Zusätzlich werden 6 Makro-Symbole verwendet: XLF, VIX, DXY, SPX, QQQ und XLP. Datenquellen sind Yahoo Finance und die FRED API. Pro Symbol werden 30 plus technische Indikatoren als Features berechnet.

## Tech Stack in StockPredict V2

Der StockPredict V2 Tech Stack besteht aus mehreren Komponenten. Cloud-Deployment erfolgt über Railway mit zwei Services — Web und ML-Pipeline. Als Datenbank wird Supabase PostgreSQL verwendet. Backend und Frontend basieren auf Django mit Tailwind CSS. Die ML-Modelle sind LSTM über PyTorch und XGBoost im Ensemble. E-Mail-Versand läuft über die Resend API da Railway SMTP blockiert. Die Programmiersprache ist Python 3.x.

## Pipeline-Übersicht Alpha Routine in StockPredict V2

Die StockPredict V2 Alpha Routine läuft Montag bis Freitag um 00:00 UTC als Railway Cronjob mit etwa 20 bis 30 Minuten Laufzeit. Schritt 1 lädt OHLCV und Earnings von Yahoo Finance. Schritt 2 berechnet 75 plus technische Features. Schritt 3 lädt LSTM Weights und Scaler aus Supabase Storage. Schritt 4 bereitet Features für LSTM auf. Schritt 5 generiert LSTM Predictions. Schritt 6 bereitet Features für XGBoost auf. Schritt 7 generiert XGBoost Predictions. Schritt 8 reichert mit VIX, XLF Regime, HG Indicator und Model Health an. Schritt 9 gleicht Real-Marktdaten mit Predictions ab. Die Schritte 1 bis 3 sind kritisch und brechen die Pipeline bei Fehler ab. Die Schritte 4 bis 9 sind non-critical und die Pipeline läuft weiter.

## HG Indicator und HG Logik in StockPredict V2

Der HG Indicator in StockPredict V2 ist ein Sektor-Filter auf Basis des XLF Z-Scores berechnet als XLF Close minus MA21 geteilt durch Std21. Ein Threshold von mindestens 1.0 aktiviert den Filter. Die HG Logic klassifiziert in fünf Signale: STRONG_BUY wenn Z-Score mindestens 1.0 und Z-Trend sich verbessert, STOCK_STRENGTH wenn Z-Score mindestens 1.0 und Z-Trend fällt oder stagniert und XGB-Konfidenz über 48%, AVOID_WEAKNESS wenn Z-Score mindestens 1.0 und Z-Trend fällt oder stagniert und XGB-Konfidenz unter 48%, WAIT wenn Z-Score unter 1.0 und NEUTRAL als Fallback. Strategy B kombiniert LSTM-Richtung UP, XLF Z-Score mindestens 1.0 und LSTM-Konfidenz mindestens 35% für die Top 5 Signale pro Tag.

## Backtest-Ergebnisse in StockPredict V2

Der StockPredict V2 Backtest über Januar 2022 bis Februar 2026 mit 50 Monaten ohne HG Logik zeigt 1.551 Trades mit einer Hit Rate von 66,2%, einem PnL von circa 72.543 Euro, einem maximalen Drawdown von -4,1% bei 10.000 Euro Positionsgröße pro Trade und 30.000 Euro Startkapital.

## Wichtige technische Konventionen in StockPredict V2

Mehrere technische Konventionen sind bei der StockPredict V2 Entwicklung kritisch. Das Supabase Row Limit beträgt standardmäßig 1.000 Rows weshalb immer die fetch_all() Pagination verwendet werden muss. Bei Supabase RPC muss immer ein leeres Dict übergeben werden. Python-NaN wird von Supabase nicht akzeptiert und muss vor dem Upsert in None konvertiert werden. Der Upsert-Conflict-Key ist symbol und date_for als Unique Constraint in der predictions-Tabelle. XLF und VIX von Tag T matchen die Prediction für T+1 als Business Day Shift. Railway blockiert SMTP weshalb die Resend API als HTTP-Workaround verwendet wird.

## File-Übersicht StockPredict V2

Die StockPredict V2 Pipeline besteht aus spezialisierten Dateien. alpha.py ist der Pipeline-Orchestrator. enricher.py ist der Railway Predictions Enricher für Step 8. enrich_predictions.py ist der Offline CSV-Enricher als Dev-Tool. performance_checker.py übernimmt das Performance Tracking für Step 9. supabase_service.py ist der Supabase Utility Layer. xgb_refiner.py bereitet XGBoost Features auf für Step 6. lstm_refiner_sql.py bereitet LSTM Features auf für Step 4.

## **Stand 10.06.2026**