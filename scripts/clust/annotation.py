import argparse
import os
from pathlib import Path

import anndata as ad
import bonesistools as bt
import matplotlib.pyplot as plt
import pandas as pd
from scbolt import cli, console, omics
from scbolt.omics import (
    check_exported_composition,
    composition_rows,
    compute_condition_composition,
)


def plot_labels(adata, obs: str, embedding: str, outfile: Path) -> None:
    omics.plot_categorical_embedding(
        adata,
        obs=obs,
        embedding=embedding,
        outfile=outfile,
    )


def plot_composition(adata, obs: str, groupby: str, outfile: Path) -> None:
    figure = bt.omics.pl.composition(
        adata,
        obs=obs,
        groupby=groupby,
        dropna=False,
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
    bt.omics.pl.set_default_axis(ax)
    plt.savefig(outfile, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    omics.crop_pdf(outfile)


def compute_composition_tables(
    adata,
    label_col: str,
    condition_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return compute_condition_composition(
        adata.obs,
        group_col=label_col,
        condition_col=condition_col,
    )


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

    (
        condition_by_label,
        label_by_condition,
        condition_enrichment_by_label,
    ) = compute_composition_tables(
        adata,
        label_col=label_col,
        condition_col=condition_col,
    )

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

    console.print_result(
        "composition\n\n"
        "     Condition proportions by label\n"
        "     ------------------------------\n"
        f"{condition_by_label_text}\n\n"
        "     Label proportions by condition\n"
        "     ------------------------------\n"
        f"{label_by_condition_text}\n"
    )

    rows = composition_rows(
        condition_by_group=condition_by_label,
        group_by_condition=label_by_condition,
        condition_enrichment_by_group=condition_enrichment_by_label,
        group_key="label",
    )

    composition_file = outdir / "composition.csv"
    console.print_task(
        f"saving composition summary (file={console.format_path(composition_file)})"
    )
    composition = pd.DataFrame(rows)
    check_exported_composition(composition, group_key="label")
    composition.to_csv(composition_file, sep=",", index=False)

    labels_plot = outdir / "labels.pdf"
    console.print_task(f"plotting embeddings (file={console.format_path(labels_plot)})")
    plot_labels(adata, obs=label_col, embedding=embedding, outfile=labels_plot)

    condition_by_label_plot = outdir / "condition_by_label.pdf"
    console.print_task(
        f"plotting composition (file={console.format_path(condition_by_label_plot)})"
    )
    plot_composition(
        adata,
        obs=condition_col,
        groupby=label_col,
        outfile=condition_by_label_plot,
    )

    label_by_condition_plot = outdir / "label_by_condition.pdf"
    console.print_task(
        f"plotting composition (file={console.format_path(label_by_condition_plot)})"
    )
    plot_composition(
        adata,
        obs=label_col,
        groupby=condition_col,
        outfile=label_by_condition_plot,
    )


script_name = Path(__file__).name

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="annotation",
        description=(
            "Rename labels using user-defined names.\n"
            "Values passed to --labels must follow the syntax <old_name>:<new_name>."
        ),
        usage=f"python {script_name} [-h] <FILE> <FILE> --obs <LITERAL> --labels <LITERAL:LITERAL [LITERAL:LITERAL ...]>",
        formatter_class=cli.HelpFormatter,
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

    omics.set_default_plot_params(bt.omics.pl)

    if not Path(os.path.dirname(args.outfile)).exists():
        os.makedirs(Path(os.path.dirname(args.outfile)))

    dict_to_str = ", ".join(f"{k} -> {v}" for k, v in args.labels.items())

    console.print_task(f"loading AnnData (file={console.format_path(args.infile)})")

    adata = ad.read_h5ad(args.infile)

    if args.obs not in adata.obs:
        raise KeyError(f"column '{args.obs}' not found in adata.obs")
    elif not hasattr(adata.obs[args.obs], "cat"):
        raise ValueError(
            f"series 'adata.obs[{args.obs}]' does not refer to a categorical variable"
        )

    console.print_task(f"renaming labels (column={args.obs}, labels={dict_to_str})")

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
    else:
        labels_plot = Path(os.path.dirname(args.outfile)) / "labels.pdf"
        console.print_task(f"plotting embeddings (file={console.format_path(labels_plot)})")
        plot_labels(adata, obs=label_col, embedding=args.embedding, outfile=labels_plot)

    console.print_task(f"saving AnnData (file={console.format_path(args.outfile)})")
    omics.write_h5ad(adata, filename=args.outfile, compression="gzip")


if __name__ == "__main__":
    main()
