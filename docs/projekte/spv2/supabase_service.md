# StockPredict V2 – supabase_service.py Supabase Utility Layer

**Kategorie:** Projekt  
**Projekt:** StockPredict V2  
**Stand:** 22.05.2026  
**Status:** Aktiv  

## Zweck von supabase_service.py in StockPredict V2

supabase_service.py liegt unter `ml-pipeline/supabase_service.py` und ist ein Thin Wrapper um den Supabase Python Client der Connection-Logik und Batch-Upload zentralisiert. supabase_service.py stellt zwei Klassen bereit die den direkten Supabase-Client kapseln. SupabaseManager übernimmt Batch-Uploads und Fetches. RailwaySupabaseService ist eine vereinfachte Facade darüber. Die Zentralisierung vermeidet Code-Duplikation in jedem einzelnen Script.

## SupabaseManager Klasse in supabase_service.py

Die Klasse `SupabaseManager` in supabase_service.py initialisiert den Supabase-Client mit SUPABASE_URL und SUPABASE_SERVICE_KEY aus den Environment Variables und stellt zwei Hauptmethoden bereit. `sync_csv_to_supabase()` konvertiert einen DataFrame in eine Records-Liste und uploaded ihn in Batches per Upsert mit Conflict-Resolution auf Symbol und Date für OHLCV-Tabellen. Die Default Batch-Size von 200 ist konservativ gewählt weil die Payload-Größe bei unbekannten Tabellen mit ggf. großen JSON-Spalten variieren kann — spezifische Scripts wie der Enricher nutzen 1.000 wo die Payload-Größe bekannt und stabil ist. `fetch_all_from_supabase()` implementiert das Pagination-Pattern für Tabellen mit mehr als 1.000 Rows weil Supabase standardmäßig bei 1.000 Rows abschneidet.

## RailwaySupabaseService Klasse in supabase_service.py

Die Klasse `RailwaySupabaseService` in supabase_service.py ist eine Facade-Klasse die SupabaseManager wrapped und eine vereinfachte API für die häufigsten Operationen bietet. `batch_upload()` delegiert direkt an SupabaseManager.sync_csv_to_supabase(). `fetch_data()` holt alle Rows für ein Symbol aus einer Tabelle ohne Pagination — nur für Tabellen mit garantiert unter 1.000 Rows pro Symbol geeignet wie aktuelle Predictions, nicht für historische Daten.

## Wann welche Klasse in StockPredict V2 nutzen

Die Wahl der richtigen Klasse in supabase_service.py hängt vom Anwendungsfall ab. Für OHLCV-Daten mit vielen Rows empfiehlt sich SupabaseManager.sync_csv_to_supabase(). Für aktuelle Predictions mit typisch 12 Rows reicht RailwaySupabaseService.fetch_data(). Für historische Predictions mit über 1.000 Rows sollte direkt der Supabase-Client mit dem fetch_all() Pagination-Pattern verwendet werden.

## Wichtige Supabase-Konventionen in StockPredict V2

Beim Arbeiten mit Supabase in StockPredict V2 gelten vier wichtige Konventionen. Bei RPC-Calls muss immer ein leeres Dict übergeben werden. Python-NaN muss vor dem Upsert in None konvertiert werden weil Supabase kein NaN akzeptiert. Timestamps werden als String im Format "%Y-%m-%d" übergeben. Bei mehr als 1.000 Rows muss Pagination verwendet werden weil das Supabase Default-Limit 1.000 Rows beträgt.

## **Stand 10.06.2026**