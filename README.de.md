# testvariance

**CI-Ergebnisse unter gleichen Bedingungen vergleichen, mit nachvollziehbaren Beobachtungen.**

[English](README.md) · [简体中文](README.zh-CN.md) · [Русский](README.ru.md)

Eine lokale Python-Bibliothek mit CLI für kanonische JSONL-Testhistorien. Sie gruppiert nach Test, Revision und Umgebung, zeigt gemischte Ergebnisse und erfolgreiche Wiederholungen und summiert gemessene Wiederholungszeiten. Zur Laufzeit genügt die Standardbibliothek von Python 3.10+.

## Zweck und Grenzen

Ein erfolgreicher Lauf nach einem Fehler beweist allein keine Testinstabilität: Code oder Umgebung könnten sich geändert haben. testvariance hält diese Gruppen getrennt. Das Werkzeug wiederholt keine Tests, greift nicht auf CI-Konten zu, diagnostiziert keine Ursachen und isoliert keine Tests automatisch. [pytest-rerunfailures](https://github.com/pytest-dev/pytest-rerunfailures) führt pytest-Wiederholungen aus; [test-summary/action](https://github.com/test-summary/action) stellt Berichte in GitHub Actions dar. Dieses unabhängig implementierte Projekt analysiert bereitgestellte Historien offline, mit expliziter Vergleichbarkeit und transparenten Messlücken.

## Installation und Beispiel

Eine Veröffentlichung im Paketindex wird nicht vorausgesetzt. Im Repository-Verzeichnis:

```sh
python -m pip install .
testvariance analyze examples/outcomes.jsonl --format text
testvariance analyze examples/outcomes.jsonl --format json
cat examples/outcomes.jsonl | testvariance analyze - --fail-on-mixed
```

Das Beispiel enthält 7 Beobachtungen, 4 vergleichbare Gruppen und 1 Gruppe mit gemischten Ergebnissen. Der letzte Befehl endet absichtlich mit Status 1. Die gemischte Gruppe hat eine Fehlerhäufigkeit von 1/3, einen wiederhergestellten Lauf, 2,5 gemessene Wiederholungssekunden und eine Wiederholung ohne Zeitmessung. Der Fehler einer anderen Revision bleibt getrennt. Ohne Installation in einer POSIX-Shell: `PYTHONPATH=src python -m testvariance analyze examples/outcomes.jsonl`.

## Eingabeformat

Ein UTF-8-JSON-Objekt pro nicht leerer Zeile:

```json
{"test_id":"suite/test","revision":"a1b2c3","environment":"linux-py312","run_id":"build-101","attempt":1,"outcome":"fail","duration_seconds":12.5}
```

- Pflichtfelder: `test_id`, `revision`, `environment`, `run_id`, `attempt`, `outcome`.
- Die vier Kennungen sind Zeichenketten mit höchstens 4096 Zeichen, die nicht nur aus Leerraum bestehen. Groß-/Kleinschreibung und Leerraum bleiben unverändert; es erfolgt keine Normalisierung. Nutzen Sie vollständige Commit-Kennungen und bilden Sie relevante Plattform-, Abhängigkeits- und Konfigurationsunterschiede in der Umgebungskennung ab.
- `attempt` ist eine positive Ganzzahl, kein boolescher Wert. Sie bezeichnet die ursprüngliche Versuchsnummer dieses Tests, dieser Revision, Umgebung und dieses Laufs, nicht die Zeilennummer.
- `outcome` ist genau `pass`, `fail`, `error` oder `skip`.
- Optionales `duration_seconds`: eine endliche, nicht negative Zahl oder `null`. Fehlend/null bedeutet unbekannt; 0 ist ein bekannter Nullwert.
- Unbekannte Felder, doppelte JSON-Feldnamen, ungültiges UTF-8, NaN/Infinity und doppelte Beobachtungsschlüssel werden abgewiesen. Der Schlüssel lautet `(test_id, revision, environment, run_id, attempt)`. Auch identische Duplikate sind ungültig.
- Grenzen: insgesamt 32 MiB, 64 KiB pro physischer Zeile einschließlich Zeilenumbruch, 100000 Beobachtungen. Leerzeilen zählen zum Byte-Limit; leere Eingaben sind gültig; UTF-8-BOM wird nicht akzeptiert. Auch die summierte Dauer muss endlich bleiben.

JUnit/XML-Import ist nicht enthalten. Konvertieren Sie Berichte vorher und bewahren Sie verlässliche Metadaten und Versuchsnummern; leiten Sie Revision oder Umgebung nicht aus Dateinamen ab.

## Bericht verstehen

Standardausgabe ist JSON mit `schema_version: 1`. Gruppen werden nach ihren drei Kennungen sortiert, Läufe nach `run_id`, Versuche nur innerhalb eines Laufs nach ihrer Nummer. Die Eingabezeilen dürfen beliebig angeordnet sein. Laufkennungen werden nicht als zeitliche Reihenfolge interpretiert.

- `counts` zählt Beobachtungen je Ergebnis; `executed_attempts` schließt skip aus.
- `failure_frequency = (fail + error) / (pass + fail + error)` ist eine nach Versuchen gewichtete beobachtete Häufigkeit, keine Ausfallwahrscheinlichkeit eines Builds. Bei ausschließlich übersprungenen Versuchen ist sie null.
- `failure_frequency_wilson_95` ist ein nominelles 95%-Wilson-Intervall, ohne ausgeführte Versuche null. Wiederholungen sind oft korreliert, selektiv und abhängig; die tatsächliche Abdeckung muss daher nicht 95% betragen. Das Intervall ist beschreibend, keine Garantie und kein Konfidenzwert für Testinstabilität.
- `mixed_outcomes` bedeutet mindestens ein pass und ein fail/error in derselben vergleichbaren Gruppe, gegebenenfalls aus verschiedenen Läufen. Das zeigt Variation, beweist aber weder Nichtdeterminismus noch eine Ursache.
- `recovered_runs` zählt Läufe mit pass im letzten beobachteten Versuch und einem früheren fail/error. pass→fail und fail→pass→skip zählen nicht. „Letzter“ meint die höchste bereitgestellte Nummer, nicht den nachgewiesenen Abschluss des CI-Laufs.
- `observed_retry_seconds` summiert bekannte Dauern bereitgestellter Versuche mit Nummer größer 1, einschließlich skip mit Zeitmessung. `retry_missing_duration_count` zählt solche Wiederholungen ohne Dauer.
- `missing_attempt_count` je Lauf zählt fehlende Nummern von 1 bis zur höchsten bereitgestellten Nummer. Für fehlende Versuche werden keine Kosten geschätzt. Die Summe der Ausführungszeiten ist weder reale Wartezeit noch Geldbetrag.
- `observed_duration_seconds` und `missing_duration_count` beziehen sich auf alle bereitgestellten Versuche. Eine beobachtete Summe von null bei fehlenden Dauern belegt keine kostenfreie Ausführung.

Berichte enthalten Ihre Kennungen und sind entsprechend vertraulich zu behandeln. Das Werkzeug nutzt kein Netzwerk und erfasst weder stdout, Fehlermeldungen, Stacktraces noch Umgebungsvariablen. Steuerzeichen werden in Textberichten maskiert; Validierungsfehler geben keine Quelldaten wieder. Berichtskennungen werden dadurch nicht anonymisiert.

## Exitcodes und Bibliothek

0 steht für einen gültigen Bericht. 1 wird nur mit ausdrücklich gesetztem `--fail-on-mixed` und mindestens einer gemischten Gruppe ausgegeben; der vollständige Bericht erscheint trotzdem. 2 bedeutet ungültige Eingabe, falsche CLI-Nutzung oder einen E/A-Fehler. Ungültige Eingaben erzeugen keinen Teilbericht. Verwenden Sie diese CI-Schranke bewusst, nicht als automatisches Urteil über Testinstabilität.

```python
from testvariance import analyze, load_jsonl
with open("examples/outcomes.jsonl", "rb") as source:
    report = analyze(load_jsonl(source))
print(report["mixed_group_count"])
```

`Observation` validiert die direkte Erstellung; `analyze` weist Duplikate ebenfalls zurück. `InputError` ist eine Unterklasse von `ValueError`. Die Daten werden innerhalb der genannten Grenzen im Speicher gehalten. Die Bibliothek schreibt keine Dateien und verändert keine Beobachtungen.

## Entwicklung und Ausblick

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

Tests benötigen nur Python; zum Bauen müssen setuptools und wheel installiert sein. CI umfasst Linux mit Python 3.10–3.13, Windows mit Python 3.12 sowie die installierte CLI. Siehe [Beiträge](CONTRIBUTING.md), [Sicherheit](SECURITY.md), [Format](docs/FORMAT.md). Geplant sind ressourcenbegrenzte JUnit/Jest-Adapter, versioniertes Zusammenführen von Historien mit klarer Konfliktregel und transparente Evidenz-/Kostenranglisten. Diese Funktionen sowie Historienspeicher, automatische Isolation und Ursachendiagnose sind in 0.1.0 nicht enthalten. MIT-Lizenz.
