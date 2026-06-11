# Global Market Mood – supabase_client.py und scheduler.py

**Kategorie:** Projekt  
**Projekt:** Global Market Mood (GMM)  
**Stand:** 22.05.2026  
**Status:** Aktiv  

## Zweck von supabase_client.py in Global Market Mood

supabase_client.py liegt unter `marketmood/pipeline/supabase_client.py` und übernimmt als Schritt 5 von 5 die Persistenz aller Pipeline-Daten in Supabase PostgreSQL. supabase_client.py ist die einzige Datenbankschicht der Global Market Mood Pipeline. Alle anderen Module sind zustandslos und verarbeiten Daten im Arbeitsspeicher. Nur dieser Client schreibt auf die Festplatte und liest von dort.

## Warum Supabase in Global Market Mood

Supabase wurde für Global Market Mood gewählt weil die Daten bereits dort lagen. Es ist PostgreSQL mit einer REST-API-Schicht, einem Python-SDK und einem kostenlosen Tier. Railway PostgreSQL wäre ein zweiter Datenbankservice mit mehr Kosten und Komplexität. SQLite erlaubt keinen Cloud-Zugriff und keinen Multi-Process-Zugriff auf Railway. MongoDB hat kein SQL und schlechtere Query-Fähigkeiten für Zeitreihen. AWS RDS ist für V3 geplant aber für V1 zu komplex und teuer. Das Django ORM würde alle Global Market Mood Daten in der Django-DB speichern was schlecht zur losen Pipeline-Architektur passt.

## get_client Funktion in supabase_client.py

Die Funktion `get_client()` in supabase_client.py initialisiert und gibt einen Supabase-Client zurück. Der Service Key wird dem Anon Key vorgezogen weil Supabase Row-Level-Security hat — der Service Key umgeht RLS was für serverseitiges Schreiben nötig ist. Kein Singleton-Pattern wird verwendet weil Supabase-Clients leichtgewichtig sind und ein Singleton bei Verbindungsabbrüchen nicht automatisch reconnecten könnte.

## save_articles Funktion in supabase_client.py

Die Funktion `save_articles()` in supabase_client.py schreibt jeden analysierten Artikel in die articles-Tabelle via upsert. upsert mit on_conflict=url verhindert Duplikate wenn die Pipeline zweimal läuft. Artikel-für-Artikel statt Bulk-Insert wird verwendet weil Fehler pro Artikel isoliert bleiben. V2 und V3 Felder wie finbert_compound, spacy_entities und translation sind bereits im Schema als None vorbereitet damit V2 keine Migration braucht.

## get_articles Funktion in supabase_client.py

Die Funktion `get_articles()` in supabase_client.py holt die neuesten Artikel einer Region aus Supabase. order mit desc=True stellt sicher dass bei limit(50) immer die 50 aktuellsten Artikel zurückgegeben werden.

## get_latest_mood Funktion in supabase_client.py

Die Funktion `get_latest_mood()` in supabase_client.py berechnet on-the-fly den Stimmungsdurchschnitt der letzten 50 Artikel einer Region als Fallback wenn kein aktueller Snapshot in mood_snapshots vorhanden ist. Im Gegensatz zum Aggregator verwendet es einfachen Artikel-Durchschnitt ohne Topic-Gewichtung — für den Fallback-Fall ausreichend.

## Zweck von scheduler.py in Global Market Mood

scheduler.py liegt unter `marketmood/scheduler.py` und ist der Dirigent der Global Market Mood Pipeline. Er startet sie alle 3 Stunden automatisch und hält sie am Laufen solange Django läuft — kein manueller Eingriff nötig.

## Warum APScheduler in scheduler.py

APScheduler läuft im selben Prozess wie Django ohne extra Service und ohne extra Kosten. Railway Cron würde einen HTTP-Request an die Django-App schicken was einen unnötigen Netzwerk-Hop bedeutet. Celery braucht einen eigenen Worker-Prozess plus Redis oder RabbitMQ als Message Broker — zwei extra Services und mehr Kosten. Linux Cron hat auf Railway-Containern keine persistente Konfiguration. Django Management Commands würden für jeden Lauf einen neuen Django-Prozess starten.

## run_pipeline Funktion in scheduler.py

Die Funktion `run_pipeline()` in scheduler.py ruft die 5 Pipeline-Schritte sequentiell auf. Lazy Imports innerhalb der Funktion verhindern Circular-Import-Fehler beim Django-Start. Die Schritte sind voneinander abhängig weshalb Parallelisierung nicht möglich ist ohne das Design fundamental zu ändern. Der globale Exception-Handler loggt Fehler ohne zu crashen — APScheduler startet die Pipeline beim nächsten Intervall wieder.

## cleanup_articles Funktion in scheduler.py

Die Funktion `cleanup_articles()` in scheduler.py delegiert an ein Django Management Command das alte Artikel nach 20 Tagen löscht. Management Commands können unabhängig getestet werden, haben Zugriff auf das ORM und trennen sauber Orchestrierung von Implementierung.

## start Funktion in scheduler.py

Die Funktion `start()` in scheduler.py erstellt den Scheduler, registriert beide Jobs und startet ihn. replace_existing=True verhindert Fehler bei Django-Neustart. DjangoJobStore speichert Job-Metadaten in der Django-Datenbank für Monitoring. BackgroundScheduler läuft in einem separaten Thread ohne den Request-Thread zu blockieren. start() wird in apps.py in der ready()-Methode aufgerufen — genau einmal nach vollständigem Django-Start. Der Job-Name gmm_hourly ist technischer Debt — er läuft alle 3 Stunden weil das Intervall nach der Migration zur Kostensenkung erhöht wurde.

## **Stand 10.06.2026**