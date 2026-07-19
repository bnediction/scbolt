#!/usr/bin/env python

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path


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

        plotting = bt.omics.pl

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


def plot_categorical_embedding(
    adata,
    obs: str,
    embedding: str,
    outfile: str | Path,
    *,
    figheight: float = 5,
    figwidth: float = 6,
    label: str = "dim",
) -> None:
    """Plot categorical labels on an embedding and write the figure to PDF."""

    if obs not in adata.obs:
        raise KeyError(f"column '{obs}' not found in adata.obs")
    if embedding not in adata.obsm:
        raise KeyError(f"embedding '{embedding}' not found in adata.obsm")

    import bonesistools as bt
    import matplotlib.pyplot as plt

    plotting = bt.omics.pl

    if hasattr(adata.obs[obs], "cat"):
        adata.obs[obs] = adata.obs[obs].cat.remove_unused_categories()

    n_components = 3 if adata.obsm[embedding].shape[1] > 2 else 2
    figure = plotting.embedding(
        adata,
        obs=obs,
        representation=embedding,
        figheight=figheight,
        figwidth=figwidth,
        xlabel=axis_label(label, 1),
        ylabel=axis_label(label, 2),
        zlabel=axis_label(label, 3),
        legend={
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": plotting.get_color("black"),
            "shadow": False,
        },
        text={
            "fontsize": 12,
            "fontweight": "extra bold",
        },
        background_visible=False,
        n_components=n_components,
    )
    if figure is None:
        raise RuntimeError("embedding plot did not return a figure and axis")

    fig, ax = figure
    plotting.set_default_axis(ax)
    plt.savefig(outfile, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    crop_pdf(outfile)


def plot_continuous_embedding(
    adata,
    obs: str,
    embedding: str,
    outfile: str | Path,
    *,
    figheight: float = 5,
    figwidth: float = 6,
    label: str = "dim",
    colorbar_label: str | None = None,
    colorbar_scale: float = 0.8,
    s: float = 4,
) -> None:
    """Plot continuous values on an embedding and write the figure to PDF."""

    if obs not in adata.obs:
        raise KeyError(f"column '{obs}' not found in adata.obs")
    if embedding not in adata.obsm:
        raise KeyError(f"embedding '{embedding}' not found in adata.obsm")

    import bonesistools as bt
    import matplotlib.pyplot as plt

    plotting = bt.omics.pl
    n_components = 3 if adata.obsm[embedding].shape[1] > 2 else 2
    figure = plotting.embedding(
        adata,
        obs=obs,
        representation=embedding,
        figheight=figheight,
        figwidth=figwidth,
        xlabel=axis_label(label, 1),
        ylabel=axis_label(label, 2),
        zlabel=axis_label(label, 3),
        colorbar_scale=colorbar_scale,
        s=s,
        background_visible=False,
        n_components=n_components,
    )
    if figure is None:
        raise RuntimeError("embedding plot did not return a figure and axis")

    fig, ax = figure
    if colorbar_label is not None and len(fig.axes) > 1:
        fig.axes[-1].set_ylabel(plain_text_label(colorbar_label))
    plotting.set_default_axis(ax)
    plt.savefig(outfile, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    crop_pdf(outfile)


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
