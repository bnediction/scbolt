#!/usr/bin/env python

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


@lru_cache(maxsize=1)
def _latex_can_render_pdf() -> bool:
    if shutil.which("latex") is None:
        return False

    try:
        import matplotlib as mpl
        from matplotlib.backends.backend_pdf import FigureCanvasPdf
        from matplotlib.figure import Figure

        with tempfile.TemporaryDirectory() as directory:
            outfile = Path(directory) / "latex-check.pdf"
            with mpl.rc_context({"text.usetex": True}):
                figure = Figure(figsize=(1, 1))
                FigureCanvasPdf(figure)
                axis = figure.add_subplot(111)
                axis.text(0.5, 0.5, r"$x$")
                figure.savefig(outfile)
        return True
    except Exception:
        return False


def use_latex_rendering() -> bool:
    """Return whether scBOLT figures should use Matplotlib's LaTeX backend."""

    value = os.environ.get("SCBOLT_USE_TEX", "auto").strip().lower()
    if value in {"0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    return _latex_can_render_pdf()


def set_default_plot_params(plotting=None):
    """Set BoNesisTools plotting defaults with automatic LaTeX fallback."""

    if plotting is None:
        import bonesistools as bt

        plotting = bt.sct.pl

    plotting.set_default_params(tex=use_latex_rendering())


def axis_label(label: str, component: int) -> str:
    """Return a TeX or plain-text axis label depending on TeX availability."""

    if use_latex_rendering():
        return r"$\mathrm{{{}_{{{}}}}}$".format(label, component)
    return f"{label}{component}"


def plain_text_label(label: str) -> str:
    """Convert common scBOLT TeX labels to plain text when TeX is unavailable."""

    if use_latex_rendering() or not isinstance(label, str):
        return label

    raw_string = re.fullmatch(r"r(['\"])(.*)\1", label)
    if raw_string:
        label = raw_string.group(2)

    match = re.fullmatch(r"\$\\mathrm\{([^{}]+)_\{([^{}]+)\}\}\$", label)
    if match:
        return f"{match.group(1)}{match.group(2)}"

    match = re.fullmatch(r"\$\\% \\mathrm\{([^{}]+)\}\$", label)
    if match:
        return f"% {match.group(1)}"

    return label


def plain_text_labels(value):
    """Recursively convert common scBOLT TeX labels when TeX is unavailable."""

    if isinstance(value, dict):
        return {key: plain_text_labels(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain_text_labels(item) for item in value]
    if isinstance(value, tuple):
        return tuple(plain_text_labels(item) for item in value)
    return plain_text_label(value)


def crop_pdf(path: str | Path) -> bool:
    """Crop a PDF with pdfcrop when available."""

    if shutil.which("pdfcrop") is None:
        return False

    path = Path(path)
    try:
        subprocess.run(
            ["pdfcrop", "--margins", "0 0 0 0", str(path), str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True
