# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""File decoding, configuration parsing, interface texts and prompt files."""

from __future__ import annotations

import codecs
import string

import pytest

from stt_to_script import i18n
from stt_to_script.config import ConfigError, Settings
from stt_to_script.prompts import LANGUAGE_NAMES, PASS_PROMPTS, PROMPT_SETS, PromptLibrary
from stt_to_script.textio import InputError, decode_bytes, read_upload

# --- decoding -----------------------------------------------------------------

GERMAN = "Grüße aus der Vorlesung: „Statistik“ kostet 5 € – das ist üblich. " * 4
POLISH = "Zażółć gęślą jaźń. Wykład dotyczy statystyki i prawdopodobieństwa. " * 4
GREEK = "Καλημέρα σας. Η διάλεξη αφορά τη στατιστική και τις πιθανότητες. " * 4


@pytest.mark.parametrize(
    "data, expected_encoding",
    [
        (GERMAN.encode("utf-8"), "utf-8"),
        (b"\xef\xbb\xbf" + GERMAN.encode("utf-8"), "utf-8-sig"),
        (GERMAN.encode("utf-16"), "utf-16"),
        (codecs.BOM_UTF16_BE + GERMAN.encode("utf-16-be"), "utf-16"),
        (GERMAN.encode("utf-32"), "utf-32"),
    ],
)
def test_unambiguous_encodings(data, expected_encoding):
    decoded = decode_bytes(data)
    assert decoded.text == GERMAN
    assert decoded.encoding == expected_encoding and not decoded.guessed


@pytest.mark.parametrize("text, codec", [(GERMAN, "cp1252"), (POLISH, "cp1250"), (GREEK, "cp1253")])
def test_legacy_encodings_are_detected_not_mangled(text, codec):
    decoded = decode_bytes(text.encode(codec))
    assert decoded.guessed
    assert decoded.text == text


ITALIAN = "Città, perché e più: è così che lavoriamo all'università. Però già fatto. " * 4
PORTUGUESE = "Ação e informação: não é só isso, também há opções e decisões à parte. " * 4


@pytest.mark.parametrize(
    "text, codec, language",
    [
        (ITALIAN, "cp1252", "it"),
        (PORTUGUESE, "cp1252", "pt"),
        (GERMAN, "cp1252", "de"),
        (POLISH, "cp1250", "pl"),
        (POLISH, "iso8859_2", "pl"),
    ],
)
def test_transcript_language_narrows_the_encoding_guess(text, codec, language):
    decoded = decode_bytes(text.encode(codec), language)
    assert decoded.guessed and decoded.text == text


def test_line_endings_are_normalised():
    assert decode_bytes(b"a\r\nb\rc").text == "a\nb\nc"


@pytest.mark.parametrize(
    "data, code",
    [
        (b"", "error_file_empty"),
        (b"  \n ", "error_file_empty"),
        (b"PK\x03\x04\x00\x00binary\x00data", "error_file_binary"),
    ],
)
def test_rejected_content(data, code):
    with pytest.raises(InputError) as info:
        decode_bytes(data)
    assert info.value.code == code


def test_read_upload_checks_extension_and_size(tmp_path):
    bad = tmp_path / "notes.pdf"
    bad.write_bytes(b"%PDF")
    with pytest.raises(InputError) as info:
        read_upload(bad, 1000)
    assert info.value.code == "error_file_type"
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * 2_000_000)
    with pytest.raises(InputError) as info:
        read_upload(big, 1_048_576)
    assert info.value.code == "error_file_too_large"
    ok = tmp_path / "Mitschrift.SRT"
    ok.write_text("Inhalt", encoding="utf-8")
    assert read_upload(ok, 1000).text == "Inhalt"


# --- configuration ----------------------------------------------------------

BASE = {"STT_TO_SCRIPT_API_BASE_URL": "http://localhost:8000/v1/", "STT_TO_SCRIPT_MODEL": "m"}


def test_minimal_configuration_and_defaults():
    settings = Settings.from_env(BASE)
    assert settings.api_base_url == "http://localhost:8000/v1"
    assert settings.chat_completions_url == "http://localhost:8000/v1/chat/completions"
    assert settings.host == "127.0.0.1" and settings.port == 7860
    assert settings.temperature == 0.3 and settings.max_tokens is None
    assert settings.api_key is None and settings.auth is None


def test_missing_required_values_are_all_reported():
    with pytest.raises(ConfigError) as info:
        Settings.from_env({})
    assert "API_BASE_URL" in str(info.value) and "MODEL" in str(info.value)


def test_empty_value_switches_an_optional_parameter_off():
    settings = Settings.from_env(
        {**BASE, "STT_TO_SCRIPT_TEMPERATURE": "", "STT_TO_SCRIPT_MAX_TOKENS": "4096"}
    )
    assert settings.temperature is None and settings.max_tokens == 4096


@pytest.mark.parametrize(
    "name, value, fragment",
    [
        ("STT_TO_SCRIPT_PORT", "abc", "integer"),
        ("STT_TO_SCRIPT_CHUNK_CHARS", "10", "at least"),
        ("STT_TO_SCRIPT_EXTRA_BODY", "[1]", "JSON object"),
        ("STT_TO_SCRIPT_EXTRA_BODY", '{"messages": []}', "must not set messages"),
        ("STT_TO_SCRIPT_API_BASE_URL", "localhost:8000", "http://"),
        ("STT_TO_SCRIPT_SHOW_ERROR_DETAILS", "vielleicht", "true or false"),
    ],
)
def test_invalid_values(name, value, fragment):
    with pytest.raises(ConfigError) as info:
        Settings.from_env({**BASE, name: value})
    assert fragment in str(info.value)


def test_auth_errors_never_echo_the_password():
    with pytest.raises(ConfigError) as info:
        Settings.from_env({**BASE, "STT_TO_SCRIPT_AUTH": "geheimespasswort"})
    assert "geheimespasswort" not in str(info.value)
    assert Settings.from_env({**BASE, "STT_TO_SCRIPT_AUTH": "anna:pa:ss"}).auth == ("anna", "pa:ss")


# --- interface texts --------------------------------------------------------


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


@pytest.mark.parametrize("key", sorted(i18n.MESSAGES))
def test_every_text_exists_in_every_language_with_the_same_placeholders(key):
    entry = i18n.MESSAGES[key]
    assert set(entry) == set(i18n.UI_LANGUAGES)
    assert all(entry.values())
    assert fields(entry["en"]) == fields(entry["de"])


@pytest.mark.parametrize(
    "query, header, expected",
    [
        (None, None, "en"),
        (None, "", "en"),
        (None, "de-DE,de;q=0.9,en;q=0.8", "de"),
        (None, "fr-FR,fr;q=0.9,de;q=0.8,en;q=0.7", "de"),
        (None, "en;q=0.5,de;q=0.9", "de"),
        (None, "de;q=0", "en"),
        ("de", "en-US", "de"),
        ("xx", "de", "de"),
    ],
)
def test_language_detection(query, header, expected):
    assert i18n.detect_language(query, header) == expected


def test_duration_formatting():
    assert i18n.format_range(10, 40, "de") == "unter 1 min"
    assert i18n.format_range(90, 300, "en") == "about 2–5 min"
    assert i18n.format_range(60, 80, "de") == "1 min"


# --- prompts ------------------------------------------------------------------


def test_shipped_prompts_are_complete():
    PromptLibrary().validate()


@pytest.mark.parametrize("prompt_set", PROMPT_SETS)
@pytest.mark.parametrize("name", PASS_PROMPTS)
def test_rendering_fills_every_placeholder(prompt_set, name):
    language = "de" if prompt_set == "de" else "fr"
    rendered = PromptLibrary().render(name, language, chunk="TEXT", context="", outline="## A")
    assert "{" not in rendered.replace("{chunk}", "")  # no unfilled placeholder left
    assert rendered.rstrip().endswith("TEXT")
    if prompt_set == "generic":
        assert LANGUAGE_NAMES[language] in rendered


def test_placeholder_text_inside_the_transcript_is_not_replaced():
    rendered = PromptLibrary().render(
        "style", "de", chunk="Wir schreiben {context} und {chunk}.", context="Medizin"
    )
    assert rendered.endswith("Wir schreiben {context} und {chunk}.\n\n")
    assert "KONTEXT UND FACHGEBIET: Medizin" in rendered


def test_empty_context_uses_the_fallback_of_the_prompt_set():
    assert "Allgemeiner Text ohne spezifisches Fachgebiet" in PromptLibrary().render(
        "style", "de", chunk="x", context="  "
    )
    assert "General text without specific subject area" in PromptLibrary().render(
        "style", "nl", chunk="x", context=""
    )


def test_outline_prefix_only_for_structure_and_only_when_present():
    library = PromptLibrary()
    with_outline = library.render("structure", "de", chunk="x", context="", outline="## Einleitung")
    assert with_outline.index("## Einleitung") < with_outline.index("Du bearbeitest einen Text")
    assert "GLIEDERUNG" not in library.render("structure", "de", chunk="x", context="")
    assert "GLIEDERUNG" not in library.render("style", "de", chunk="x", context="", outline="## A")


def test_prompt_override_directory(tmp_path):
    (tmp_path / "generic").mkdir()
    (tmp_path / "generic" / "style.txt").write_text(
        "EIGEN {context} {language} {chunk}", encoding="utf-8"
    )
    library = PromptLibrary(tmp_path)
    assert library.render("style", "it", chunk="c", context="k") == "EIGEN k Italian c"
    assert library.render("style", "de", chunk="c", context="k").startswith("\nDu bearbeitest")


POLISH_WITH_S = "Ścieżka i źródło: się, jeśli, właśnie. Wykład dotyczy statystyki. " * 4


@pytest.mark.parametrize(
    "text, codec, language, shown",
    [
        (ITALIAN, "iso8859_15", "it", "ISO-8859-15"),
        (GERMAN, "cp1252", "de", "Windows-1252"),
        (POLISH_WITH_S, "cp1250", "pl", "Windows-1250"),
        (POLISH_WITH_S, "iso8859_2", "pl", "ISO-8859-2"),
    ],
)
def test_windows_or_iso_code_page_by_control_range(text, codec, language, shown):
    decoded = decode_bytes(text.encode(codec), language)
    assert decoded.text == text and decoded.encoding == shown
