"""Optional print-ready PDF rendering via an external MuseScore.

PDF export is deliberately optional: the engine and its wheel stay
dependency-free, and MuseScore is an external tool the host may or may not
provide. When it is present, a tier's MusicXML is rendered to a print-ready
PDF; when it is absent, callers fall back explicitly rather than failing, in
line with the "PDF where the toolchain supports it, with an explicit fallback"
contract.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# An explicit path override wins; otherwise these common executable names are
# probed on PATH. MuseScore 3 and 4 both accept ``-o out.pdf in.musicxml``.
MUSESCORE_ENV = "PARTICULAR_MUSESCORE"
MUSESCORE_NAMES = (
    "mscore",
    "musescore",
    "MuseScore4",
    "MuseScore3",
    "mscore4portable",
    "mscore3portable",
)
# MuseScore can hang on malformed input; bound every render.
RENDER_TIMEOUT_SECONDS = 60.0


class PdfRenderError(RuntimeError):
    """Raised when PDF export is unavailable or MuseScore fails to render."""


def find_musescore() -> str | None:
    """Locate a usable MuseScore executable, honoring ``PARTICULAR_MUSESCORE``."""

    override = os.environ.get(MUSESCORE_ENV)
    if override:
        return override if Path(override).exists() else None
    for name in MUSESCORE_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def pdf_export_available() -> bool:
    """Whether a MuseScore executable is available for PDF export."""

    return find_musescore() is not None


def render_pdf(
    musicxml: bytes,
    musescore: str | None = None,
    timeout: float = RENDER_TIMEOUT_SECONDS,
) -> bytes:
    """Render MusicXML to PDF bytes with MuseScore.

    Raises :class:`PdfRenderError` when no executable is available or the render
    fails, so callers can present the explicit fallback.
    """

    executable = musescore or find_musescore()
    if executable is None:
        raise PdfRenderError("no MuseScore executable is available for PDF export")
    with tempfile.TemporaryDirectory(prefix="particular-pdf-") as workdir:
        source = Path(workdir) / "score.musicxml"
        output = Path(workdir) / "score.pdf"
        source.write_bytes(musicxml)
        try:
            subprocess.run(
                [executable, "-o", str(output), str(source)],
                check=True,
                capture_output=True,
                timeout=timeout,
                # Let MuseScore run headless on servers without a display.
                env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            )
        except (subprocess.SubprocessError, OSError) as error:
            raise PdfRenderError("MuseScore failed to render the score") from error
        if not output.exists():
            raise PdfRenderError("MuseScore produced no PDF output")
        return output.read_bytes()
