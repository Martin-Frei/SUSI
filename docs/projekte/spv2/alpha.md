# StockPredict V2 – alpha.py Pipeline-Orchestrator

**Kategorie:** Projekt  
**Projekt:** StockPredict V2  
**Stand:** 22.05.2026  
**Status:** Aktiv  

## Zweck von alpha.py in StockPredict V2

alpha.py liegt unter `ml-pipeline/alpha.py` und ist der Einstiegspunkt der gesamten Alpha Routine in StockPredict V2. Es koordiniert alle 9 Pipeline-Steps sequenziell. alpha.py ist der Dirigent der Pipeline — es startet alle Steps in der richtigen Reihenfolge, tracked Erfolg und Fehler pro Step, unterscheidet zwischen kritischen und non-kritischen Fehlern und sendet am Ende eine E-Mail-Zusammenfassung mit den aktuellen Trading-Signalen.

## log_pipeline_start in alpha.py

Die Funktion `log_pipeline_start()` in alpha.py gibt Startup-Informationen ins Railway-Log aus: Startzeit, Anzahl der Symbole, Supabase URL und Environment. Sie lädt config.yaml um die Symbol-Listen zu lesen. Standard-logging reicht für Railway-Logs vollständig aus ohne externe Abhängigkeit.

## execute_pipeline_step in alpha.py

Die Funktion `execute_pipeline_step()` in alpha.py ist ein generischer Wrapper für jeden einzelnen Pipeline-Step. Er führt die übergebene Funktion aus, misst die Laufzeit, fängt alle Exceptions ab und gibt True oder False plus result zurück. Der Wrapper zentralisiert Error-Handling und Timing-Logging an einem Ort statt Code-Duplikation in jedem Step.

## run_alpha_routine in alpha.py

Die Funktion `run_alpha_routine()` in alpha.py iteriert über die pipeline_steps-Liste mit 9 Steps als Dicts mit name, description, function und critical. Bei critical=True bricht die Pipeline bei Fehler ab. Bei critical=False wird geloggt und weitergemacht. Ein DAG-Framework wie Airflow wäre massiver Overhead für eine single-machine sequentielle Pipeline — Railway Cronjob plus Plain Python ist die einfachste und robusteste Lösung.

## calculate_zscore_trade_signals in alpha.py

Die Funktion `calculate_zscore_trade_signals()` in alpha.py berechnet den HCV (Hybrid Confidence Value) aus LSTM- und XGBoost-Signals und wendet den HG Indicator-Filter an. Der HCV wird als gewichteter Durchschnitt aus LSTM-Signal mal LSTM-Konfidenz und XGBoost-Signal mal XGBoost-Konfidenz geteilt durch 2 berechnet. Ein Z-Score von mindestens 1.0 aktiviert TRADE, sonst SKIP. Diese Funktion schreibt nur für den E-Mail-Report — nicht in die Datenbank.

## generate_trading_summary und send_alpha_report in alpha.py

Die Funktion `generate_trading_summary()` in alpha.py formatiert die Trading-Signale als lesbaren Text für die E-Mail. Pro Zeile erscheinen Symbol, LSTM-Richtung, LSTM-Konfidenz, XGBoost-Richtung, XGBoost-Konfidenz, HCV und Trade-Status. Die Sortierung erfolgt nach Trade-Eligibility mit TRADE zuerst dann nach absolutem HCV. Die Funktion `send_alpha_report()` sendet die tägliche E-Mail via Resend API über REST und HTTP weil Railway ausgehende SMTP-Verbindungen blockiert. Der Report enthält Pipeline-Status mit Laufzeit, Performance-Update mit Hit Rates, HG Indicator Summary und alle Trading-Signale.

## get_latest_predictions und health_check in alpha.py

Die Funktion `get_latest_predictions()` in alpha.py holt die Predictions des aktuellen Tages aus Supabase für den E-Mail-Report — einfacher direkter Supabase-Call ohne Pagination da maximal 12 Rows zurückkommen. Die Funktion `health_check()` ist ein Pre-flight Check vor Pipeline-Start der prüft ob alle Environment Variables gesetzt sind: SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY, EMAIL_RECEIVER, EMAIL_SENDER und ob config/config.yaml existiert. Bei fehlendem Check startet die Pipeline nicht.

## main und kritische Steps in alpha.py

Die Funktion `main()` in alpha.py ist der Railway Entry Point und ruft in Reihenfolge auf: health_check() bei Fehler Abbruch, run_alpha_routine() mit den 9 Pipeline-Steps, sync_real_open_close() als Supabase SQL Function und sync_real_dir_and_hits() als Supabase SQL Function. Exit Code 0 signalisiert Erfolg, Exit Code 1 signalisiert Fehler für Railway-Monitoring. Die drei kritischen Steps sind Market Data Download, Feature Engineering und Download LATEST Models — bei Fehler bricht die Pipeline ab weil alle folgenden Steps auf diesen Daten aufbauen. Die sechs non-critical Steps sind LSTM Preprocessing, LSTM Predictions, XGBoost Preprocessing, XGBoost Predictions, Predictions Enrichment und Performance Update.

## **Stand 10.06.2026**