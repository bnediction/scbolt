#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

import random

import numpy as np
import anndata as ad
import scanpy as sc
import bonesistools as bt


bt.sct.pl.set_default_params()


def _format_percent_if_float(value):
    if value is None:
        return "none"
    if isinstance(value, (float, np.floating)):
        return f"{value:.2%}"
    return str(value)


script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="clustering",
    description=(
        "Compute principal components, compute closest and shared-nearest "
        "neighbors, cluster cells using the Leiden algorithm and embed the "
        "neighborhood graph in UMAP or t-SNE projection."
    ),
    usage=f"python {script_name} <FILE> <FILE> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)",
)

parser.add_argument(
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing neighbors and embedding projection (format: h5ad)",
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used (if not specified, use adata.X)",
)

parser.add_argument(
    "--adjacency",
    dest="adjacency",
    type=str,
    required=False,
    default="knn",
    choices=["knn", "snn"],
    metavar="[knn | snn]",
    help="neighbor connectivities used for Leiden clustering (default: knn)",
)

parser.add_argument(
    "--embedding",
    dest="embedding",
    type=str,
    required=False,
    default="umap",
    choices=["umap", "tsne"],
    metavar="[umap | tsne]",
    help="embedding projection (default: umap)",
)

parser.add_argument(
    "--pca-dimension",
    dest="pca_dimension",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of computed principal components (default: 50)",
)

parser.add_argument(
    "--clustering-dimension",
    dest="clustering_dimension",
    type=int,
    required=False,
    default=15,
    metavar="INT",
    help="number of principal components taken into account for clustering cells (default: 15)",
)

parser.add_argument(
    "--embedding-dimension",
    dest="embedding_dimension",
    type=int,
    required=False,
    default=2,
    metavar="INT",
    help="number of embedding dimensions (default: 2)",
)

parser.add_argument(
    "--lsa",
    dest="lsa",
    action="store_true",
    required=False,
    help="approximate reduction dimension using truncated SVD (latent semantic analysis) instead of PCA",
)

parser.add_argument(
    "--flavor",
    dest="flavor",
    type=str,
    required=False,
    default="seurat_v3",
    choices=["seurat", "cell_ranger", "seurat_v3"],
    metavar="[seurat | cell_ranger | seurat_v3]",
    help="method used for identifying highly variable genes (default: seurat_v3)",
)

parser.add_argument(
    "--top-hvg",
    dest="top_hvg",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of highly variable genes to select (default: None)",
)

parser.add_argument(
    "--span",
    dest="span",
    action=cli.Range,
    type=float,
    min=0,
    max=1,
    required=False,
    default=0.3,
    help="fraction of cells used when estimating the variance in the loess model (used only if method='seurat_v3', default: 0.3)",
)

parser.add_argument(
    "--bins",
    dest="bins",
    type=float,
    required=False,
    default=20,
    metavar="INT",
    help="number of bins for binning the mean gene expression (default: 20)",
)

parser.add_argument(
    "--only-hvg",
    dest="only_hvg",
    action="store_true",
    required=False,
    help="use only highly variable genes for PCA projection",
)

parser.add_argument(
    "--neighbors",
    dest="neighbors",
    type=int,
    required=False,
    default=20,
    metavar="INT",
    help="number of closest neighbors (default: 20)",
)

parser.add_argument(
    "--metric",
    dest="metric",
    type=str,
    required=False,
    default="euclidean",
    metavar="METRIC",
    help="metric used for computing closest neighbors and optionally t-SNE projection (default: euclidean)",
)

parser.add_argument(
    "--resolution",
    dest="resolution",
    type=float,
    required=False,
    default=0.6,
    metavar="FLOAT",
    help="coarseness of the clustering (default: 0.6)",
)

parser.add_argument(
    "--min-dist",
    dest="min_dist",
    type=float,
    required=False,
    default=0.5,
    metavar="FLOAT",
    help="effective minimum distance between embedded points in UMAP (default: 0.5)",
)

parser.add_argument(
    "--spread",
    dest="spread",
    type=float,
    required=False,
    default=1.0,
    metavar="FLOAT",
    help="effective scale of embedded points in UMAP (default: 1.0)",
)

parser.add_argument(
    "--seed",
    dest="seed",
    type=int,
    required=False,
    default=random.random(),
    metavar="INT",
    help="random seed (default: random)",
)

args = parser.parse_args()

if args.pca_dimension < args.clustering_dimension:
    raise ValueError(
        f"invalid values for arguments: 'pca-dimension' > 'clustering-dimension' not satisfied (pca-dimension: {args.pca_dimension}, clustering-dimension: {args.clustering_dimension})"
    )

embedding_label = std.format_embedding(args.embedding)

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")

adata = ad.read_h5ad(args.infile)

if args.layer:
    adata.X = adata.layers[args.layer].copy()

if args.only_hvg:
    std.print_task(
        "estimating highly variable genes "
        f"({std.format_hvg_parameters(flavor=args.flavor, number=args.top_hvg)})"
    )
    with std.filter_scanpy_hvg_warnings():
        sc.pp.highly_variable_genes(
            adata,
            layer="counts" if args.flavor == "seurat_v3" else "log-norm",
            flavor=args.flavor,
            span=args.span,
            n_bins=args.bins,
            n_top_genes=args.top_hvg,
            inplace=True,
        )

std.print_task(f"computing principal components (dimensions={args.pca_dimension})")
if args.only_hvg:
    std.print_info("filtering PCA features (scope=highly variable genes)")
sc.tl.pca(
    adata,
    n_comps=args.pca_dimension,
    zero_center=not args.lsa,
    use_highly_variable=args.only_hvg,
    random_state=np.random.RandomState(args.seed),
    copy=False,
)

std.print_task(
    f"computing nearest-neighbor graph (principal components={args.clustering_dimension})"
)
sc.pp.neighbors(
    adata,
    n_neighbors=args.neighbors,
    use_rep="X_pca",
    n_pcs=args.clustering_dimension,
    metric=args.metric,
    copy=False,
)

prune_snn = 1 / 15
prune_snn_msg = _format_percent_if_float(prune_snn)
std.print_task(
    f"computing shared nearest-neighbor graph (pruning_threshold={prune_snn_msg})"
)
bt.sct.tl.shared_neighbors(
    adata, snn_key="shared_neighbors", prune_snn=prune_snn, copy=False
)

std.print_task(f"clustering cells (algorithm=leiden, resolution={args.resolution})")
sc.tl.leiden(
    adata,
    neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
    resolution=args.resolution,
    key_added="cluster",
    random_state=args.seed,
    copy=False,
)
std.print_result(f"identified {adata.obs['cluster'].nunique()} clusters")

std.print_task(f"embedding neighborhood graph (dimensions={args.embedding_dimension})")
if args.embedding == "umap":
    std.print_task(
        f"computing embedding (method={embedding_label}, "
        f"dimensions={args.embedding_dimension}, "
        f"min_dist={args.min_dist}, "
        f"spread={args.spread})"
    )
    sc.tl.umap(
        adata,
        neighbors_key="neighbors",
        n_components=args.embedding_dimension,
        min_dist=args.min_dist,
        spread=args.spread,
        random_state=np.random.RandomState(args.seed),
        copy=False,
    )
    del adata.uns["umap"]["params"]["random_state"]
elif args.embedding == "tsne":
    std.print_task(
        f"computing embedding (method={embedding_label}, "
        f"dimensions={args.embedding_dimension}, "
        f"metric={args.metric})"
    )
    sc.tl.tsne(
        adata,
        n_pcs=args.embedding_dimension,
        use_rep="X_pca",
        metric=args.metric,
        random_state=np.random.RandomState(args.seed),
        copy=False,
    )

embedding_plot = Path(f"{os.path.dirname(args.outfile)}/clusters.pdf")
std.print_info(
    f"plotting embeddings (directory={os.path.relpath(os.path.dirname(args.outfile))})"
)
bt.sct.pl.embedding(
    adata,
    obs="cluster",
    use_rep="X_umap" if args.embedding == "umap" else "X_tsne",
    xlabel=r"$\mathrm{{{}_{{1}}}}$".format(embedding_label),
    ylabel=r"$\mathrm{{{}_{{2}}}}$".format(embedding_label),
    zlabel=r"$\mathrm{{{}_{{3}}}}$".format(embedding_label),
    figwidth=6,
    s=2,
    alpha=1,
    show_legend=True,
    lgd_params={
        "title": "clusters",
        "ncol": 1,
        "markerscale": 5,
        "frameon": True,
        "edgecolor": bt.sct.pl.get_color("black"),
        "shadow": False,
    },
    n_components=3 if args.embedding_dimension > 2 else 2,
    background_visible=False,
    outfile=embedding_plot,
)

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
std.write_h5ad(adata, filename=args.outfile, compression="gzip")
