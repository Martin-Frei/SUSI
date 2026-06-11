# StockPredict V2 – performance_checker.py Performance Tracking

**Kategorie:** Projekt  
**Projekt:** StockPredict V2  
**Stand:** 22.05.2026  
**Status:** Aktiv — Pipeline Step 9 von 9  

## Zweck von performance_checker.py in StockPredict V2

performance_checker.py liegt unter `ml-pipeline/performance_checker.py` und übernimmt als Pipeline Step 9 von 9 das Performance Tracking in StockPredict V2. Das Script holt alle Predictions mit bekanntem real_open und real_close aus Supabase, berechnet die tatsächliche Marktrichtung UP, DOWN oder NEUTRAL und schreibt hit_lstm, hit_xgb und real_dir zurück. Die zentrale Frage die performance_checker.py beantwortet ist: Hat das Modell recht gehabt?

## SupabasePerformanceChecker Klasse in performance_checker.py

Die Klasse `SupabasePerformanceChecker` in performance_checker.py enthält alle Methoden des StockPredict V2 Performance Trackers. `__init__()` initialisiert den Supabase-Client und lädt die 12 Banksymbole aus config.yaml.

## _fetch_all Funktion in performance_checker.py

Die Funktion `_fetch_all()` in performance_checker.py ist ein Pagination Helper der über alle Pages iteriert bis alle Rows geladen sind. Supabase gibt standardmäßig maximal 1.000 Rows zurück. Ohne Pagination werden historische Daten still abgeschnitten was zu falschen Hit-Rate-Berechnungen ohne sichtbaren Fehler führt. SPV2 hat für 12 Symbole über mehrere Jahre bereits weit über 1.000 Rows. Der zentrale Helper wird von mehreren Methoden genutzt statt Code-Duplikation mit direktem range() in jedem Query.

## sync_hits Funktion in performance_checker.py

Die Funktion `sync_hits()` in performance_checker.py ist die Kernfunktion. Sie iteriert über alle 12 Banksymbole und führt vier Schritte aus. Zuerst holt sie alle Predictions mit real_open IS NOT NULL und real_close IS NOT NULL. Dann berechnet sie real_dir pro Prediction: UP wenn real_close größer als real_open, DOWN wenn kleiner und NEUTRAL wenn gleich. Dann berechnet sie hit_lstm als 1 wenn lstm_dir gleich real_dir sonst 0 und hit_xgb analog. Schließlich schreibt sie hit_lstm, hit_xgb und real_dir per row-by-row Update zurück. Row-by-row Update wird verwendet weil jede Row unterschiedliche Werte hat — ein Batch-Update würde einen gemeinsamen Wert auf alle Rows setzen was hier nicht möglich ist.

## load_rows Funktion in performance_checker.py

Die Funktion `load_rows()` in performance_checker.py bereitet Daten für das Terminal-Dashboard vor. Sie holt alle Predictions mit _fetch_all() Pagination und berechnet pro Symbol die Hit-Rate für LSTM und XGB in Prozent, die letzten 10 Predictions als Icon-String mit ✅ ❌ und 🔷, den Probability-String mit DOWN-, NEUTRAL- und UP-Prozent, die aktuelle Richtungs-Prediction sowie den Status MATCH wenn beide Modelle einig sind oder DISP wenn uneinig. Nur die 5 Predictions mit höchster lstm_conf pro Datum werden berücksichtigt — analog zur Live-Strategie.

## display Funktion in performance_checker.py

Die Funktion `display()` in performance_checker.py gibt ein formatiertes Terminal-Dashboard mit Symbol, LSTM Hit-Rate, XGB Hit-Rate, Richtungs-Predictions und Match-Status aus. Sie wird nur bei manuellem Aufruf von performance_checker.py verwendet und nicht in der Railway-Pipeline.

## run_performance_checker in performance_checker.py

Die Funktion `run_performance_checker()` in performance_checker.py ist der Railway Entry Point und ruft nur sync_hits() auf ohne display(). Sie wird von alpha.py in Step 9 aufgerufen.

## **Stand 10.06.2026**