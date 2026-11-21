# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Reading uploaded text files and detecting their character encoding.

Unambiguous cases are decided deterministically: a byte order mark, or bytes
that decode as strict UTF-8.

For other input, the language of the transcript selects a pair of code pages:
Windows-1252 and ISO-8859-15 for Western European languages, Windows-1250 and
ISO-8859-2 for Polish. The Windows code pages use the byte range 0x80-0x9F for
printable characters; in the ISO code pages that range holds control
characters, which do not occur in text. Bytes in that range therefore select
the Windows code page, their absence the ISO code page. Statistical detection
cannot make this distinction reliably for these pairs. It is used only if the
language is unknown or the chosen code page cannot decode the bytes.

``latin-1`` is not used as a fallback: it decodes any byte sequence and would
hide a wrong decision.
"""

from __future__ import annotations

import codecs
import os
from dataclasses import dataclass
from pathlib import Path

from charset_normalizer import from_bytes

ALLOWED_EXTENSIONS = (".txt", ".text", ".md", ".markdown", ".srt", ".vtt")
SUBTITLE_EXTENSIONS = (".srt", ".vtt")

# Order matters: the UTF-32 LE mark starts with the UTF-16 LE mark.
_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


# (Windows code page, ISO code page) per transcript language.
_WESTERN = ("cp1252", "iso8859_15")
CODE_PAGES = {lang: _WESTERN for lang in ("de", "en", "fr", "es", "it", "pt", "nl")}
CODE_PAGES["pl"] = ("cp1250", "iso8859_2")
ENCODING_NAMES = {
    "cp1252": "Windows-1252",
    "cp1250": "Windows-1250",
    "iso8859_15": "ISO-8859-15",
    "iso8859_2": "ISO-8859-2",
}


class InputError(ValueError):
    """A problem with the user's input. ``code`` is a message key in :mod:`i18n`."""

    def __init__(self, code: str, **params: object):
        super().__init__(code)
        self.code = code
        self.params = params


@dataclass(frozen=True)
class DecodedText:
    text: str
    encoding: str
    guessed: bool  # True if the encoding was detected heuristically


def check_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise InputError(
            "error_file_type", extension=extension or "-", allowed=", ".join(ALLOWED_EXTENSIONS)
        )
    return extension


def decode_bytes(data: bytes, language: str | None = None) -> DecodedText:
    if not data.strip():
        raise InputError("error_file_empty")
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            try:
                return DecodedText(_clean(data.decode(encoding)), encoding, guessed=False)
            except UnicodeDecodeError:
                raise InputError("error_file_unreadable") from None
    if b"\x00" in data:
        # NUL bytes without a UTF-16/32 byte order mark: binary data.
        raise InputError("error_file_binary")
    try:
        return DecodedText(_clean(data.decode("utf-8")), "utf-8", guessed=False)
    except UnicodeDecodeError:
        pass
    if language in CODE_PAGES:
        windows, iso = CODE_PAGES[language]
        codec = windows if any(0x80 <= byte <= 0x9F for byte in data) else iso
        try:
            text = _clean(data.decode(codec))
        except UnicodeDecodeError:
            pass  # e.g. Mac Roman: leave it to the statistical detection
        else:
            if _control_ratio(text) <= 0.01:
                return DecodedText(text, ENCODING_NAMES[codec], guessed=True)
    best = from_bytes(data).best()
    if best is None:
        raise InputError("error_file_unreadable")
    text = _clean(str(best))
    if _control_ratio(text) > 0.01:
        # A "successful" guess that is mostly control characters is binary data.
        raise InputError("error_file_binary")
    return DecodedText(text, best.encoding, guessed=True)


def read_upload(
    path: str | os.PathLike[str], max_bytes: int, language: str | None = None
) -> DecodedText:
    """Read and decode an uploaded file, enforcing extension and size limits."""
    path = Path(path)
    check_extension(path.name)
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        raise InputError("error_file_missing") from None
    if size > max_bytes:
        raise InputError(
            "error_file_too_large", size_mb=size / 1_048_576, max_mb=max_bytes // 1_048_576
        )
    return decode_bytes(path.read_bytes(), language)


def _control_ratio(text: str) -> float:
    controls = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\t")
    return controls / max(len(text), 1)


def _clean(text: str) -> str:
    """Normalise line endings and drop a stray byte order mark."""
    return text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
