from __future__ import annotations

from pathlib import Path

import pytest
from particular.exporters.pdf import (
    MUSESCORE_ENV,
    PdfRenderError,
    find_musescore,
    pdf_export_available,
    render_pdf,
)


def test_env_override_selects_an_existing_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "mscore"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv(MUSESCORE_ENV, str(fake))

    assert find_musescore() == str(fake)
    assert pdf_export_available() is True


def test_env_override_pointing_nowhere_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MUSESCORE_ENV, "/no/such/musescore")

    assert find_musescore() is None
    assert pdf_export_available() is False


def test_render_without_any_executable_raises_for_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MUSESCORE_ENV, "/no/such/musescore")

    with pytest.raises(PdfRenderError):
        render_pdf(b"<score-partwise></score-partwise>")


def test_render_surfaces_a_failing_executable_as_render_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An executable that always exits non-zero stands in for a broken MuseScore.
    failing = tmp_path / "mscore"
    failing.write_text("#!/bin/sh\nexit 3\n")
    failing.chmod(0o755)
    monkeypatch.setenv(MUSESCORE_ENV, str(failing))

    with pytest.raises(PdfRenderError):
        render_pdf(b"<score-partwise></score-partwise>")


def test_render_reads_back_a_produced_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A stub that writes the requested output file exercises the success path
    # without a real MuseScore: it parses ``-o <output> <input>``.
    stub = tmp_path / "mscore"
    stub.write_text(
        '#!/bin/sh\nwhile [ "$1" != "-o" ]; do shift; done\nprintf "%%PDF-1.4 stub" > "$2"\n'
    )
    stub.chmod(0o755)
    monkeypatch.setenv(MUSESCORE_ENV, str(stub))

    pdf = render_pdf(b"<score-partwise></score-partwise>")

    assert pdf.startswith(b"%PDF")
