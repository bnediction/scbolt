#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

import anndata as ad
import bonesistools as bt
import matplotlib.pyplot as plt
import pandas as pd


def crop_pdf(path: Path) -> None:
    try:
        os.system(f"pdfcrop --margins '0 0 0 0' {path} {path} > {os.devnull}")
    except OSError:
        print("unavailable unix command 'pdfcrop': no figure trimming")


def remove_unused_obs_categories(adata, obs: str) -> None:
    if obs in adata.obs and hasattr(adata.obs[obs], "cat"):
        adata.obs[obs] = adata.obs[obs].cat.remove_unused_categories()


def plot_labels(adata, obs: str, embedding: str, outfile: Path) -> None:
    remove_unused_obs_categories(adata, obs)
    n_components = 3 if adata.obsm[embedding].shape[1] > 2 else 2
    figure = bt.sct.pl.embedding(
        adata,
        obs=obs,
        use_rep=embedding,
        figheight=5,
        figwidth=6,
        xlabel=r"$\mathrm{dim_{1}}$",
        ylabel=r"$\mathrm{dim_{2}}$",
        zlabel=r"$\mathrm{dim_{3}}$",
        show_legend=True,
        s=2,
        alpha=1,
        lgd_params={
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": bt.sct.pl.get_color("black"),
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
    bt.sct.pl.set_default_axis(ax)
    plt.savefig(outfile, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    crop_pdf(outfile)


def plot_composition(adata, obs: str, groupby: str, outfile: Path) -> None:
    figure = bt.sct.pl.composition(
        adata,
        obs=obs,
        groupby=groupby,
        normalize=True,
        percent=True,
        dropna=False,
        orientation="vertical",
        width=0.8,
        showlegend=True,
        figwidth=6,
        figheight=3,
        labelsize=12,
        xlabel=groupby,
        legend={
            "title": obs,
            "bbox_to_anchor": (1.0, 0.5),
            "loc": "center left",
            "frameon": False,
        },
    )
    if figure is None:
        raise RuntimeError("composition plot did not return a figure and axis")
    fig, ax = figure
    bt.sct.pl.set_default_axis(ax)
    plt.savefig(outfile, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    crop_pdf(outfile)


def summarize_composition(
    adata,
    label_col: str,
    condition_col: str,
    embedding: str,
    outdir: Path,
) -> None:
    for column in [condition_col, label_col]:
        if column not in adata.obs:
            raise KeyError(f"column '{column}' not found in adata.obs")
    if embedding not in adata.obsm:
        raise KeyError(f"embedding '{embedding}' not found in adata.obsm")

    counts = pd.crosstab(adata.obs[label_col], adata.obs[condition_col])
    counts = counts.reindex(sorted(counts.columns), axis=1)

    condition_by_label = counts.div(counts.sum(axis=1), axis=0)
    label_by_condition = counts.div(counts.sum(axis=0), axis=1)

    display_condition_by_label = condition_by_label.map(lambda value: f"{value:.2%}")
    display_label_by_condition = label_by_condition.map(lambda value: f"{value:.2%}")
    display_condition_by_label["all"] = "100.00%"
    display_label_by_condition.loc["all"] = ["100.00%"] * len(
        display_label_by_condition.columns
    )
    display_condition_by_label = display_condition_by_label.rename_axis(
        index=None,
        columns=None,
    )
    display_label_by_condition = display_label_by_condition.rename_axis(
        index=None,
        columns=None,
    )
    condition_by_label_text = "     " + display_condition_by_label.to_string().replace(
        "\n",
        "\n     ",
    )
    label_by_condition_text = "     " + display_label_by_condition.to_string().replace(
        "\n",
        "\n     ",
    )

    std.print_result(
        "composition\n\n"
        "     Condition proportions by label\n"
        "     ------------------------------\n"
        f"{condition_by_label_text}\n\n"
        "     Label proportions by condition\n"
        "     ------------------------------\n"
        f"{label_by_condition_text}\n"
    )

    rows = []
    for label in condition_by_label.index:
        for condition in condition_by_label.columns:
            rows.append(
                {
                    "summary": "condition_by_label",
                    "label": label,
                    "condition": condition,
                    "proportion": round(
                        float(condition_by_label.loc[label, condition]), 4
                    ),
                }
            )
    for condition in label_by_condition.columns:
        for label in label_by_condition.index:
            rows.append(
                {
                    "summary": "label_by_condition",
                    "label": label,
                    "condition": condition,
                    "proportion": round(
                        float(label_by_condition.loc[label, condition]), 4
                    ),
                }
            )

    composition_file = outdir / "composition.csv"
    std.print_task(
        f"saving composition summary (file={std.format_path(composition_file)})"
    )
    pd.DataFrame(rows).to_csv(composition_file, sep=",", index=False)

    labels_plot = outdir / "labels.pdf"
    std.print_task(f"plotting embeddings (file={std.format_path(labels_plot)})")
    plot_labels(adata, obs=label_col, embedding=embedding, outfile=labels_plot)

    condition_by_label_plot = outdir / "condition_by_label.pdf"
    std.print_task(
        f"plotting composition (file={std.format_path(condition_by_label_plot)})"
    )
    plot_composition(
        adata,
        obs=condition_col,
        groupby=label_col,
        outfile=condition_by_label_plot,
    )

    label_by_condition_plot = outdir / "label_by_condition.pdf"
    std.print_task(
        f"plotting composition (file={std.format_path(label_by_condition_plot)})"
    )
    plot_composition(
        adata,
        obs=label_col,
        groupby=condition_col,
        outfile=label_by_condition_plot,
    )


script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="annotation",
    description=(
        "Rename labels using user-defined names.\n"
        "Values passed to --labels must follow the syntax <old_name>:<new_name>."
    ),
    usage=f"python {script_name} [-h] <FILE> <FILE> --obs <LITERAL> --labels <LITERAL:LITERAL [LITERAL:LITERAL ...]>",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing counts with renamed labels (format: h5ad)",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in adata.obs where category names are redefined",
)

parser.add_argument(
    "--new-obs",
    dest="new_obs",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="if specified, create a new adata.obs column storing renamed labels",
)

parser.add_argument(
    "--labels",
    dest="labels",
    action=cli.Store_dict,
    nargs="+",
    required=True,
    help="mapping between old and new labels",
)

parser.add_argument(
    "--condition-col",
    dest="condition_col",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="if specified, summarize and plot label composition by condition",
)

parser.add_argument(
    "--embedding",
    dest="embedding",
    type=str,
    required=False,
    default="X_umap",
    metavar="LITERAL",
    help="embedding representation used for label plotting (default: X_umap)",
)

args = parser.parse_args()

bt.sct.pl.set_default_params()


if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

dict_to_str = ", ".join(f"{k} -> {v}" for k, v in args.labels.items())

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")

adata = ad.read_h5ad(args.infile)

if args.obs not in adata.obs:
    raise KeyError(f"column '{args.obs}' not found in adata.obs")
elif not hasattr(adata.obs[args.obs], "cat"):
    raise ValueError(
        f"series 'adata.obs[{args.obs}]' does not refer to a categorical variable"
    )

std.print_task(f"renaming labels (column={args.obs}, labels={dict_to_str})")

categories = list(adata.obs[args.obs].cat.categories)
category_by_name = {str(category): category for category in categories}
missing_labels = sorted(set(args.labels) - set(category_by_name))
if missing_labels:
    raise KeyError(
        "labels not found in categorical column "
        f"'{args.obs}': {', '.join(missing_labels)}"
    )

labels = {category_by_name[key]: value for key, value in args.labels.items()}
renamed_values = adata.obs[args.obs].astype(object).replace(labels)
renamed_categories = []
for category in categories:
    renamed_category = labels.get(category, category)
    if renamed_category not in renamed_categories:
        renamed_categories.append(renamed_category)
renamed_labels = pd.Categorical(
    renamed_values,
    categories=renamed_categories,
    ordered=adata.obs[args.obs].cat.ordered,
)
if args.new_obs is None:
    adata.obs[args.obs] = renamed_labels
    label_col = args.obs
else:
    adata.obs[args.new_obs] = renamed_labels
    label_col = args.new_obs

if args.condition_col is not None:
    summarize_composition(
        adata,
        label_col=label_col,
        condition_col=args.condition_col,
        embedding=args.embedding,
        outdir=Path(os.path.dirname(args.outfile)),
    )

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
std.write_h5ad(adata, filename=args.outfile, compression="gzip")
