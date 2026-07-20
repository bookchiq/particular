from __future__ import annotations

import pytest
from particular.errors import PUBLIC_ERROR_GUIDANCE, classify_error
from particular.exporters.musicxml import MusicXMLExportError
from particular.importers.musicxml import MusicXMLParseError
from particular.importers.security import ScoreSizeError, UnsafeScoreError
from particular.validation.arrangement import ArrangementValidationError


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (MusicXMLParseError("part P1 measure 3 is invalid"), "malformed_score"),
        (MusicXMLExportError("unsupported rehearsal mark"), "unsupported_notation"),
        (UnsafeScoreError("DOCTYPE declarations are not allowed"), "unsafe_archive"),
        (ScoreSizeError("MXL total size exceeds limit"), "oversized_file"),
        (ArrangementValidationError("tier note counts are not monotonic"), "internal_error"),
        (ValueError("unknown instrument profile override: P9"), "invalid_request"),
        (OSError("disk full at /var/tmp/secret"), "internal_error"),
    ],
)
def test_classify_error_maps_to_stable_code_and_safe_guidance(
    error: BaseException, code: str
) -> None:
    public = classify_error(error)

    assert public.code == code
    assert public.message == PUBLIC_ERROR_GUIDANCE[code]
    # Guidance never echoes the exception's content.
    assert str(error) not in public.message
    assert public.message and not public.message.endswith(":")


def test_size_error_is_distinguished_from_generic_unsafe_archive() -> None:
    assert classify_error(ScoreSizeError("too big")).code == "oversized_file"
    assert classify_error(UnsafeScoreError("nested archives")).code == "unsafe_archive"
