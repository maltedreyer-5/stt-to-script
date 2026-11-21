# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Interface texts in English and German.

Keys are stable identifiers and never shown. The interface language is
decided once per browser session on the server (``?lang=`` first, then the
``Accept-Language`` header, then English), so static labels and messages
produced while a job runs always use the same language.

The processing language of a job is chosen separately in the interface; it
only selects the prompt set and is independent of the interface language.
"""

from __future__ import annotations

UI_LANGUAGES = ("en", "de")
DEFAULT_UI_LANGUAGE = "en"

# Processing languages with their names in their own language.
PROCESSING_LANGUAGES = {
    "de": "Deutsch",
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "nl": "Nederlands",
    "pl": "Polski",
}

MESSAGES: dict[str, dict[str, str]] = {
    # --- page -----------------------------------------------------------
    "title": {"en": "STT to Script", "de": "STT to Script"},
    "intro": {
        "en": "Cleans up and structures speech-to-text transcripts with a language model. "
        "The text is processed in steps you choose; the result appears below and can be downloaded.",
        "de": "Bereinigt und gliedert Transkripte aus der Spracherkennung mit einem Sprachmodell. "
        "Der Text wird in den gewählten Schritten bearbeitet; das Ergebnis erscheint unten und lässt sich herunterladen.",
    },
    "language_switch": {"en": "[Deutsch](?lang=de)", "de": "[English](?lang=en)"},
    "tab_file": {"en": "Upload file", "de": "Datei hochladen"},
    "tab_text": {"en": "Paste text", "de": "Text einfügen"},
    "file_label": {"en": "Transcript file", "de": "Transkript-Datei"},
    "text_label": {"en": "Transcript", "de": "Transkript"},
    "text_placeholder": {"en": "Paste the transcript here …", "de": "Transkript hier einfügen …"},
    "input_both": {
        "en": "Both a file and pasted text are present. The file is used.",
        "de": "Es gibt sowohl eine Datei als auch eingefügten Text. Verwendet wird die Datei.",
    },
    "language_label": {"en": "Language of the transcript", "de": "Sprache des Transkripts"},
    "language_info": {
        "en": "The result stays in this language.",
        "de": "Das Ergebnis bleibt in dieser Sprache.",
    },
    "context_label": {"en": "Subject and context", "de": "Fachgebiet und Kontext"},
    "context_placeholder": {
        "en": "e.g. medicine; technical documentation; contract law",
        "de": "z. B. Medizin; technische Dokumentation; Vertragsrecht",
    },
    "context_info": {
        "en": "Subject areas, special terms or names help the model recognise technical terms correctly.",
        "de": "Fachgebiete, Fachbegriffe oder Namen helfen dem Modell, Fachbegriffe richtig zu erkennen.",
    },
    "preset_label": {"en": "Preset", "de": "Voreinstellung"},
    "preset_correction": {"en": "Correction", "de": "Korrektur"},
    "preset_revision": {"en": "Revision", "de": "Überarbeitung"},
    "preset_formatting": {"en": "Formatting", "de": "Formatierung"},
    "preset_rag": {"en": "Preparation for RAG", "de": "Aufbereitung für RAG"},
    "preset_custom": {"en": "Custom", "de": "Eigene Auswahl"},
    "steps_label": {"en": "Steps", "de": "Schritte"},
    "steps_info": {
        "en": "Steps always run in this order. Each step except 0 is one pass through the language model.",
        "de": "Die Schritte laufen immer in dieser Reihenfolge. Jeder Schritt außer 0 ist ein Durchgang durch das Sprachmodell.",
    },
    "step_preprocess": {
        "en": "0 Preprocessing: remove subtitle numbers and timestamps (no language model)",
        "de": "0 Vorverarbeitung: Untertitelnummern und Zeitstempel entfernen (ohne Sprachmodell)",
    },
    "step_correct": {
        "en": "1 Recognition errors: transcription errors, terms, punctuation",
        "de": "1 Erkennungsfehler: Transkriptionsfehler, Fachbegriffe, Zeichensetzung",
    },
    "step_clean": {
        "en": "2 Clean-up: filler words, false starts, repetitions",
        "de": "2 Bereinigung: Füllwörter, Satzabbrüche, Wiederholungen",
    },
    "step_style": {
        "en": "3 Style: factual, academic wording",
        "de": "3 Stil: sachlich-wissenschaftliche Formulierung",
    },
    "step_structure": {
        "en": "4 Structure: paragraphs and Markdown headings",
        "de": "4 Struktur: Absätze und Markdown-Überschriften",
    },
    "step_rag": {
        "en": "5 RAG: make sections self-contained, add a metadata header",
        "de": "5 RAG: Abschnitte für sich verständlich machen, Metadaten-Kopf ergänzen",
    },
    "keep_speakers_label": {"en": "Keep speaker labels", "de": "Sprecherkennungen behalten"},
    "keep_speakers_info": {
        "en": "Applies to step 0, e.g. “SPEAKER_00:” or WebVTT voice tags.",
        "de": "Gilt für Schritt 0, z. B. „SPEAKER_00:“ oder WebVTT-Sprecher-Tags.",
    },
    "estimate_empty": {
        "en": "The estimated duration appears here once there is a text.",
        "de": "Die geschätzte Dauer erscheint hier, sobald ein Text vorliegt.",
    },
    "estimate_line": {
        "en": "Estimated duration: **{range}** ({segments}, {passes}).",
        "de": "Geschätzte Dauer: **{range}** ({segments}, {passes}).",
    },
    "count_sections_one": {"en": "1 section", "de": "1 Abschnitt"},
    "count_sections_other": {"en": "{count} sections", "de": "{count} Abschnitte"},
    "count_passes_one": {"en": "1 pass", "de": "1 Durchgang"},
    "count_passes_other": {"en": "{count} passes", "de": "{count} Durchgänge"},
    "estimate_uncalibrated": {
        "en": " The estimate is not yet based on measurements of this installation.",
        "de": " Die Schätzung beruht noch nicht auf Messungen dieser Installation.",
    },
    "estimate_no_passes": {
        "en": "Only step 0 is selected; this takes no noticeable time.",
        "de": "Gewählt ist nur Schritt 0; das dauert keine spürbare Zeit.",
    },
    "estimate_unavailable": {
        "en": "No estimate: {reason}",
        "de": "Keine Schätzung: {reason}",
    },
    "keep_tab_open": {
        "en": "Keep this tab open until the result is shown. Closing it cancels the processing, and nothing is stored on the server.",
        "de": "Lassen Sie diesen Tab geöffnet, bis das Ergebnis angezeigt wird. Schließen bricht die Verarbeitung ab, und auf dem Server wird nichts gespeichert.",
    },
    "start_button": {"en": "Start processing", "de": "Verarbeitung starten"},
    "stop_button": {"en": "Cancel", "de": "Abbrechen"},
    "status_label": {"en": "Status", "de": "Status"},
    "status_waiting": {"en": "Ready.", "de": "Bereit."},
    "status_pass": {
        "en": "Step {index} of {count}: {name}. {done} of {total} sections done. Remaining: {range}.",
        "de": "Schritt {index} von {count}: {name}. {done} von {total} Abschnitten fertig. Restzeit: {range}.",
    },
    "status_done": {
        "en": "Finished in {duration}.",
        "de": "Fertig nach {duration}.",
    },
    "status_failed": {"en": "Processing stopped.", "de": "Verarbeitung abgebrochen."},
    "result_preview": {"en": "Preview", "de": "Vorschau"},
    "result_text": {"en": "Text", "de": "Text"},
    "downloads_label": {"en": "Downloads", "de": "Downloads"},
    "intermediates_label": {"en": "Intermediate results", "de": "Zwischenergebnisse"},
    "issues_heading": {"en": "Notes on this result", "de": "Hinweise zu diesem Ergebnis"},
    "issue_line": {
        "en": "Section {segment}, {name}: {message}",
        "de": "Abschnitt {segment}, {name}: {message}",
    },
    "encoding_guessed": {
        "en": "The file is not UTF-8. Detected character set: {encoding}. Check special characters in the result.",
        "de": "Die Datei ist nicht UTF-8. Erkannter Zeichensatz: {encoding}. Prüfen Sie Sonderzeichen im Ergebnis.",
    },
    "subtitles_detected": {
        "en": "The input contains subtitle timings, so step 0 was applied.",
        "de": "Die Eingabe enthält Untertitel-Zeitangaben, deshalb wurde Schritt 0 angewendet.",
    },
    "disclaimer": {
        "en": "Results are produced by a language model and can contain errors. Check them before further use.",
        "de": "Die Ergebnisse erzeugt ein Sprachmodell; sie können Fehler enthalten. Prüfen Sie sie vor der weiteren Verwendung.",
    },
    # --- pass names, used in status lines and issues ---------------------
    "pass_preprocess": {"en": "preprocessing", "de": "Vorverarbeitung"},
    "pass_correct_clean": {
        "en": "recognition errors and clean-up",
        "de": "Erkennungsfehler und Bereinigung",
    },
    "pass_correct": {"en": "recognition errors", "de": "Erkennungsfehler"},
    "pass_clean": {"en": "clean-up", "de": "Bereinigung"},
    "pass_style": {"en": "style", "de": "Stil"},
    "pass_structure": {"en": "structure", "de": "Struktur"},
    "pass_rag": {"en": "RAG", "de": "RAG"},
    # --- durations ------------------------------------------------------
    "duration_under_minute": {"en": "under 1 min", "de": "unter 1 min"},
    "duration_range": {"en": "about {low}–{high} min", "de": "ca. {low}–{high} min"},
    "duration_minutes": {"en": "{minutes} min", "de": "{minutes} min"},
    "duration_seconds": {"en": "{seconds} s", "de": "{seconds} s"},
    # --- input errors ---------------------------------------------------
    "error_no_input": {
        "en": "Upload a file or paste a text first.",
        "de": "Laden Sie zuerst eine Datei hoch oder fügen Sie einen Text ein.",
    },
    "error_no_steps": {
        "en": "Select at least one step.",
        "de": "Wählen Sie mindestens einen Schritt.",
    },
    "error_file_type": {
        "en": "Files of type “{extension}” cannot be processed. Allowed: {allowed}.",
        "de": "Dateien vom Typ „{extension}“ lassen sich nicht verarbeiten. Erlaubt: {allowed}.",
    },
    "error_file_missing": {
        "en": "The uploaded file is no longer available. Upload it again.",
        "de": "Die hochgeladene Datei ist nicht mehr verfügbar. Laden Sie sie erneut hoch.",
    },
    "error_file_empty": {"en": "The file is empty.", "de": "Die Datei ist leer."},
    "error_file_binary": {
        "en": "The file contains binary data. Upload a plain text file.",
        "de": "Die Datei enthält Binärdaten. Laden Sie eine reine Textdatei hoch.",
    },
    "error_file_unreadable": {
        "en": "The character set of the file could not be determined. Save it as UTF-8 and upload it again.",
        "de": "Der Zeichensatz der Datei ließ sich nicht bestimmen. Speichern Sie sie als UTF-8 und laden Sie sie erneut hoch.",
    },
    "error_file_too_large": {
        "en": "The file is {size_mb:.1f} MB; the limit is {max_mb} MB.",
        "de": "Die Datei hat {size_mb:.1f} MB; erlaubt sind {max_mb} MB.",
    },
    "error_text_too_short": {
        "en": "The text needs at least {minimum} characters.",
        "de": "Der Text braucht mindestens {minimum} Zeichen.",
    },
    "error_text_too_long": {
        "en": "The text is longer than {maximum:,} characters. Split it into several parts.",
        "de": "Der Text ist länger als {maximum:,} Zeichen. Teilen Sie ihn in mehrere Teile.",
    },
    "error_estimate_too_long": {
        "en": "The estimated duration ({range}) exceeds the limit of {limit} min. Split the text or select fewer steps.",
        "de": "Die geschätzte Dauer ({range}) überschreitet die Grenze von {limit} min. Teilen Sie den Text oder wählen Sie weniger Schritte.",
    },
    # --- processing errors and issues ------------------------------------
    "llm_unavailable": {
        "en": "the language model did not respond in time or was not reachable",
        "de": "das Sprachmodell hat nicht rechtzeitig geantwortet oder war nicht erreichbar",
    },
    "llm_truncated": {
        "en": "the answer was cut off by the model’s length limit; the section was left unchanged",
        "de": "die Antwort wurde durch das Längenlimit des Modells abgeschnitten; der Abschnitt blieb unverändert",
    },
    "llm_rejected": {
        "en": "the language model service rejected the request (access or model configuration)",
        "de": "der Sprachmodell-Dienst hat die Anfrage abgelehnt (Zugang oder Modellkonfiguration)",
    },
    "llm_rejected_segment": {
        "en": "the language model rejected this section; it was left unchanged",
        "de": "das Sprachmodell hat diesen Abschnitt abgelehnt; er blieb unverändert",
    },
    "llm_failed": {
        "en": "processing failed; the section was left unchanged",
        "de": "die Verarbeitung ist fehlgeschlagen; der Abschnitt blieb unverändert",
    },
    "possible_preface": {
        "en": "the beginning looks like an introductory remark by the model; check it",
        "de": "der Anfang sieht nach einer Vorrede des Modells aus; prüfen Sie ihn",
    },
    "possible_closing": {
        "en": "the end looks like a closing remark by the model; check it",
        "de": "das Ende sieht nach einer Schlussbemerkung des Modells aus; prüfen Sie es",
    },
    "main_heading": {
        "en": "the model added a top-level heading (#); check the heading levels",
        "de": "das Modell hat eine Hauptüberschrift (#) eingefügt; prüfen Sie die Gliederung",
    },
    "language_mismatch": {
        "en": "The text looks like {detected}, but {selected} is selected as its language. The model may translate it.",
        "de": "Der Text sieht nach {detected} aus, gewählt ist aber {selected}. Das Modell könnte ihn übersetzen.",
    },
    "length_changed": {
        "en": "the length changed considerably; check this section",
        "de": "die Länge hat sich stark verändert; prüfen Sie diesen Abschnitt",
    },
    "job_failed": {
        "en": "Processing stopped: {message}. Contact the operator of this installation if this persists.",
        "de": "Die Verarbeitung wurde abgebrochen: {message}. Wenden Sie sich an den Betrieb dieser Installation, wenn das wiederholt auftritt.",
    },
    "error_internal": {
        "en": "An unexpected error occurred. Contact the operator of this installation if this persists.",
        "de": "Ein unerwarteter Fehler ist aufgetreten. Wenden Sie sich an den Betrieb dieser Installation, wenn das wiederholt auftritt.",
    },
    "error_details": {"en": "Technical details: {detail}", "de": "Technische Details: {detail}"},
    "error_title": {"en": "Error", "de": "Fehler"},
}


def t(key: str, lang: str, **params: object) -> str:
    entry = MESSAGES[key]
    text = entry.get(lang) or entry[DEFAULT_UI_LANGUAGE]
    return text.format(**params) if params else text


def detect_language(query_lang: str | None, accept_language: str | None) -> str:
    if query_lang and query_lang.lower()[:2] in UI_LANGUAGES:
        return query_lang.lower()[:2]
    for tag in _parse_accept_language(accept_language or ""):
        if tag[:2] in UI_LANGUAGES:
            return tag[:2]
    return DEFAULT_UI_LANGUAGE


def _parse_accept_language(header: str) -> list[str]:
    weighted = []
    for position, part in enumerate(header.split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, _, params = piece.partition(";")
        quality = 1.0
        for param in params.split(";"):
            name, _, value = param.strip().partition("=")
            if name == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        if quality > 0:
            weighted.append((-quality, position, tag.strip().lower()))
    return [tag for _, _, tag in sorted(weighted)]


def count(key: str, number: int, lang: str) -> str:
    """``count("sections", 3, "de")`` -> "3 Abschnitte"."""
    return t(f"count_{key}_{'one' if number == 1 else 'other'}", lang, count=number)


def format_duration(seconds: float, lang: str) -> str:
    if seconds < 60:
        return t("duration_seconds", lang, seconds=max(1, round(seconds)))
    return t("duration_minutes", lang, minutes=round(seconds / 60))


def format_range(low: float, high: float, lang: str) -> str:
    if high < 60:
        return t("duration_under_minute", lang)
    low_min, high_min = max(1, round(low / 60)), max(1, round(high / 60))
    if low_min == high_min:
        return t("duration_minutes", lang, minutes=low_min)
    return t("duration_range", lang, low=low_min, high=high_min)
