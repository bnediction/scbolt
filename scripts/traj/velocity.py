#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

import anndata as ad
import bonesistools as bt
import scvelo as scv

import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings(
    "ignore",
    message="is_categorical_dtype is deprecated.*",
    category=DeprecationWarning,
)

std.set_default_plot_params(bt.sct.pl)

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="velocity",
    description=(
        "Compute RNA velocities based on spliced/unspliced kinetics using the "
        "scVelo framework.\n"
        "See Bergen et al. (2020) <https://www.nature.com/articles/s41587-020-0591-3>."
    ),
    usage=f"python {script_name} <FILE> <FILE> [<args>]",
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing precomputed neighbors, principal components and embeddings (format: h5ad)",
)

parser.add_argument(
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing velocity (format: h5ad)",
)

parser.add_argument(
    "--expression",
    dest="expression",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help=("Expression layer to use.\n" "Default: adata.X."),
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in adata.obs distinguishing clusters",
)

parser.add_argument(
    "--moment-dimension",
    dest="moment_dimension",
    type=int,
    required=False,
    default=15,
    metavar="INT",
    help="number of principal components taken into account for estimating moments (default: 15)",
)

parser.add_argument(
    "--only-hvg",
    dest="only_hvg",
    action="store_true",
    required=False,
    help="use only highly variable genes for estimating RNA velocities",
)

parser.add_argument(
    "--mode",
    dest="mode",
    type=str,
    required=False,
    choices=["deterministic", "stochastic", "dynamical"],
    default="stochastic",
    metavar="[deterministic | stochastic | dynamical]",
    help="mode used for estimating the steady-state model (default: stochastic)",
)

parser.add_argument(
    "--embedding",
    dest="embedding",
    type=str,
    required=False,
    default="umap",
    choices=["umap", "tsne"],
    metavar="[umap | tsne]",
    help="embedding projection used (default: umap)",
)

parser.add_argument(
    "--jobs",
    dest="jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of allocated processors (default: 1)",
)

parser.add_argument(
    "--plot-3d",
    dest="plot_3d",
    required=False,
    action="store_true",
    help="plot 3D embeddings when available",
)

args = parser.parse_args()

outpath = os.path.dirname(args.outfile)
if not Path(outpath).exists():
    os.makedirs(outpath)

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")
adata = ad.read_h5ad(args.infile)

adata.obs["clusters"] = adata.obs[args.cluster]

if args.expression:
    adata.X = adata.layers[args.expression].copy()

plot_dir = Path(outpath)
std.print_task(f"plotting velocity outputs (directory={os.path.relpath(plot_dir)})")

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="is_categorical_dtype is deprecated.*",
        category=DeprecationWarning,
    )

    if args.cluster:
        scv.pl.proportions(
            adata,
            groupby=args.cluster,
            fontsize=plt.rcParams["font.size"],
            figsize=(11, 5),
            show=False,
        )
        plt.savefig(Path(f"{outpath}/proportions.pdf"))
        plt.close()

std.print_task("computing moments (orders=first, second)")
with std.disable_print():
    scv.pp.moments(
        adata,
        n_neighbors=None,
        n_pcs=args.moment_dimension,
        mode="connectivities",
        method="umap",
        use_rep="X_pca",
        use_highly_variable=args.only_hvg,
        copy=False,
    )

std.print_task(f"estimating RNA velocities (mode={args.mode})")
with std.disable_print():
    scv.tl.velocity(
        adata,
        vkey="velocity",
        mode=args.mode,
        use_highly_variable=args.only_hvg,
        copy=False,
    )

std.print_task("inferring velocity graph")
with std.disable_print():
    scv.tl.velocity_graph(adata, vkey="velocity", copy=False, n_jobs=args.jobs)

std.print_task("estimating velocity pseudotime")
with std.disable_print():
    scv.tl.velocity_pseudotime(adata, vkey="velocity", use_velocity_graph=True)

std.print_task("estimating PAGA graph (edges=velocity-directed)")
with std.disable_print():
    scv.tl.paga(adata, vkey="velocity", groups=args.cluster, copy=False)
    adata.uns["transitions_confidence"] = adata.uns["paga"]["transitions_confidence"]

embedding_label = "UMAP" if args.embedding == "umap" else "t-SNE"
adata.uns["colors"] = bt.sct.pl.generate_colormap(
    color_number=len(adata.obs[args.cluster].cat.categories)
).colors
color_map = {
    cluster: adata.uns["colors"][idx]
    for idx, cluster in enumerate(adata.obs[args.cluster].cat.categories)
}

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="is_categorical_dtype is deprecated.*",
        category=DeprecationWarning,
    )

    with std.disable_print():
        ax = scv.pl.velocity_embedding_stream(
            adata,
            basis=args.embedding,
            title="",
            linewidth=1,
            size=5,
            color_map=color_map,
            alpha=0.5,
            legend_loc="best",
            legend_fontweight="bold",
            figsize=(7, 4),
            show=False,
        )
        for txt in ax.texts:
            txt.set_visible(False)
        try:
            plt.savefig(Path(f"{outpath}/stream_plot.pdf"))
        except Exception:
            if os.path.isfile(Path(f"{outpath}/stream_plot.pdf")):
                os.remove(Path(f"{outpath}/stream_plot.pdf"))
            plt.savefig(Path(f"{outpath}/stream_plot.png"))
        plt.close()

    bt.sct.pl.embedding(
        adata,
        obs="velocity_pseudotime",
        representation="X_umap" if args.embedding == "umap" else "X_tsne",
        xlabel=std.axis_label(embedding_label, 1),
        ylabel=std.axis_label(embedding_label, 2),
        zlabel=std.axis_label(embedding_label, 3),
        figwidth=6,
        s=4,
        legend={
            "title": "pseudotime",
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": bt.sct.pl.get_color("black"),
            "shadow": False,
        },
        n_components=3 if adata.obsm["velocity_umap"].shape[1] > 2 else 2,
        background_visible=False,
        colorbar_scale=0.3,
        colors="gnuplot",
        outfile=Path(f"{outpath}/velocity_pseudotime.pdf"),
    )

    fig, ax = bt.sct.pl.embedding(
        adata,
        obs=args.cluster,
        representation="X_umap" if args.embedding == "umap" else "X_tsne",
        xlabel=std.axis_label(embedding_label, 1),
        ylabel=std.axis_label(embedding_label, 2),
        zlabel=std.axis_label(embedding_label, 3),
        figwidth=6,
        s=4,
        legend={
            "title": "clusters",
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": bt.sct.pl.get_color("black"),
            "shadow": False,
        },
        colors=adata.uns["colors"],
        n_components=(
            3
            if adata.obsm["velocity_umap"].shape[1] > 2 and args.plot_3d is True
            else 2
        ),
        background_visible=False,
    )
    plt.axis("off")
    ax = bt.sct.pl.draw_paga(
        adata=adata,
        obs=args.cluster,
        representation="X_umap" if args.embedding == "umap" else "X_tsne",
        edges="transitions_confidence",
        threshold=0.01,
        ax=ax,
        with_labels=False,
        width=2,
        node_size=100,
        node_color=color_map,
    )
    plt.savefig(Path(f"{outpath}/paga.pdf"))
    plt.close()

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
if args.cluster != "clusters":
    del adata.obs["clusters"]
std.write_h5ad(adata, filename=args.outfile, compression="gzip")
