"""Stable, content-safe public error contract for director-facing surfaces.

Exception messages can name parts, measures, file paths, or future parser
internals, so director-facing boundaries must never echo them. ``classify_error``
maps any failure to a stable public code and fixed, actionable guidance.
"""

from __future__ import annotations

from dataclasses import dataclass

from particular.exporters.musicxml import MusicXMLExportError
from particular.importers.musicxml import MusicXMLParseError
from particular.importers.security import ScoreSizeError, UnsafeScoreError
from particular.validation.arrangement import ArrangementValidationError


@dataclass(frozen=True)
class PublicError:
    code: str
    message: str


# Stable public codes and the exact guidance shown to directors. Messages never
# include values derived from the uploaded score.
PUBLIC_ERROR_GUIDANCE: dict[str, str] = {
    "malformed_score": (
        "This file could not be read as MusicXML. Re-export it from your notation "
        "software as uncompressed MusicXML or a .mxl file, then try again."
    ),
    "unsupported_notation": (
        "This score uses notation Particular cannot preserve yet. Remove or simplify "
        "the unsupported passages, or export a part Particular supports."
    ),
    "unsafe_archive": (
        "This file was rejected by a safety check. Upload a MusicXML or .mxl file "
        "exported directly from notation software, not a modified or repackaged archive."
    ),
    "oversized_file": (
        "This file is too large or expands too much to process safely. Export a "
        "smaller score or a single movement, then try again."
    ),
    "invalid_request": (
        "The request could not be processed. Check the selected instrument profiles "
        "and file type, then try again."
    ),
    "internal_error": (
        "Something went wrong while creating the arrangement, so no parts were "
        "produced. Please try again."
    ),
}


def _code_for(error: BaseException) -> str:
    if isinstance(error, ScoreSizeError):
        return "oversized_file"
    if isinstance(error, UnsafeScoreError):
        return "unsafe_archive"
    if isinstance(error, MusicXMLExportError):
        return "unsupported_notation"
    if isinstance(error, MusicXMLParseError):
        return "malformed_score"
    if isinstance(error, ArrangementValidationError):
        return "internal_error"
    if isinstance(error, ValueError):
        return "invalid_request"
    return "internal_error"


def classify_error(error: BaseException) -> PublicError:
    """Map an exception to a stable public code and content-safe guidance."""

    code = _code_for(error)
    return PublicError(code, PUBLIC_ERROR_GUIDANCE[code])
