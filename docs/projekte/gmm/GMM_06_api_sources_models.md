# Global Market Mood – api_sources.py und models.py

**Kategorie:** Projekt  
**Projekt:** Global Market Mood (GMM)  
**Stand:** 22.05.2026  
**Status:** Aktiv  

## Zweck von api_sources.py in Global Market Mood

api_sources.py liegt unter `marketmood/pipeline/api_sources.py` und ist die einzige Konfigurationsdatei der Global Market Mood Pipeline. Jeder Feed ist ein Dict mit 6 Feldern. Der Rest der Pipeline bezieht seine geografische und thematische Struktur aus dieser Datei. Neue Feeds hinzufügen bedeutet ein neues Dict in die Liste und active auf True setzen.

## Feed-Struktur in api_sources.py

Jeder Feed-Eintrag in api_sources.py definiert sechs Felder. name ist der Anzeigename im Dashboard und im Log. url ist die RSS Feed URL. region ist der ISO-Ländercode der die Verbindung Feed zu Artikel zu Weltkarten-Zone herstellt. language entscheidet ob ein Feed aktiv sein kann — VADER und DeepSeek sind auf Englisch optimiert weshalb alle Feeds mit Sprache DE oder FR auf active=False stehen. category ist ein initialer Hint der in V1 von DeepSeek überschrieben wird. active ist der An/Aus-Schalter.

## Geographische Abdeckung in api_sources.py

api_sources.py enthält über 200 Feeds für etwa 100 Länder auf allen Kontinenten. Europa umfasst DE, AT, CH, GB, FR, NL, SE, NO, PL, CZ, HU, RO und weitere. Amerika deckt US, CA, MX, BR, AR, CL, CO und PE ab. Asien enthält JP, CN, IN, SG, KR, TW, TH, VN, MY und ID. Afrika umfasst ZA, NG, KE, EG, MA, TN, GH, UG und TZ. Ozeanien deckt AU, NZ, PG und FJ ab. Der Nahe Osten enthält SA, AE, IL, TR, IR, QA und KW. Das Alleinstellungsmerkmal von Global Market Mood ist die globale Perspektive — ein System das nur Europa und USA abdeckt könnte durch Bloomberg ersetzt werden.

## Feed-Versionslogik in api_sources.py

V1 ist aktiv für DE, CH, AT, GB, FR, NL, BE, SE, NO, DK und FI sowie alle anderen aktiven Länder. V1.5 hat auf alle 100 plus Länder erweitert. V2 inactive enthält AT mit Deutsch das FinBERT-DE braucht sowie Feeds in Qualitätsprüfung. Dateibasierte Konfiguration ist einfacher zu versionieren via Git und zu reviewen als ein Datenbank-basiertes Feed-Management.

## Zweck von models.py in Global Market Mood

models.py liegt unter `accounts/models.py` und erweitert den Django Standard-User um ein UserProfile mit einem Tier-System. Dieses Tier steuert was ein eingeloggter User beim Global Market Mood Dashboard und bei SPV2 sehen darf. Es ist die Brücke zwischen dem technischen Authentifizierungssystem und dem Business-Modell.

## UserProfile Model in models.py

Das UserProfile in models.py verwendet OneToOneField statt ForeignKey weil ein User genau ein Profil hat. on_delete=CASCADE löscht das Profil mit dem User für DSGVO-Konformität. default=TIER_FREE sorgt dafür dass jeder neue User als Free-User startet. stripe_customer_id ist in V1 leer aber bereits im Schema für V2 wenn Stripe-Webhooks das Feld befüllen.

## Hilfsmethoden im UserProfile

Die drei Hilfsmethoden im UserProfile prüfen den aktuellen Tier des Users. is_pro() schließt auch Premium ein weil Premium eine Obermenge von Pro ist — ohne das müssten alle Views auf is_pro() OR is_premium() prüfen was fehleranfällig wäre. Die Methoden werden in Views verwendet um Inhalt zu schützen.

## Tier-Inhalte in Global Market Mood und SPV2

Die Tier-Inhalte unterscheiden sich je nach Produkt. Bei Global Market Mood sieht Free News älter als 12 Stunden, Pro sieht aktuelle News in Echtzeit und Premium hat zusätzlich Keyword-Suche. Bei SPV2 sieht Free gestrige Vorhersagen mit Trefferquote, Pro sieht heutige Vorhersagen und Premium sieht die Holy Grail Signale mit Z-Score gleich 1.0.

## Django Signals in models.py

Zwei Signals in models.py stellen sicher dass jeder neue User automatisch ein UserProfile bekommt. create_user_profile wird nur bei created=True ausgeführt und erstellt das Profil. save_user_profile wird bei jedem User-Save ausgeführt und synchronisiert Profil-Änderungen. Signals sind die Django-idiomatische Lösung — sie halten das User-Model unberührt statt AbstractUser zu verwenden was eine frühe schwer rückgängig zu machende Entscheidung wäre.

## **Stand 10.06.2026**