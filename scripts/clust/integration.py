#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

from typing import Optional, Sequence
from anndata import AnnData

import random
import numpy as np

import anndata as ad
import scanpy as sc
import bonesistools as bt
import scanorama


bt.sct.pl.set_default_params()


@bt.sct.typing.anndata_checker
def clean_adata(
    adata: AnnData,
    obs: Optional[Sequence[str]] = None,
    var: Optional[Sequence[str]] = None,
    copy: bool = False,
) -> Optional[AnnData]:

    adata = adata.copy() if copy else adata

    if obs:
        for _obs in obs:
            if _obs in adata.obs.columns:
                del adata.obs[_obs]
    if var:
        for _var in var:
            if _var in adata.var.columns:
                del adata.var[_var]
    if "pca" in adata.uns.keys():
        del adata.uns["pca"]
    if "neighbors" in adata.uns.keys():
        del adata.uns["neighbors"]
    if "shared_neighbors" in adata.uns.keys():
        del adata.uns["shared_neighbors"]
    if "cluster" in adata.uns.keys():
        del adata.uns["cluster"]
    if "tsne" in adata.uns.keys():
        del adata.uns["tsne"]
    if "umap" in adata.uns.keys():
        del adata.uns["umap"]
    del adata.obsm, adata.obsp, adata.varm, adata.varp

    return adata if copy else None


def namespace_obs_names(
    adata: AnnData,
    condition: str,
    sep: str = ":",
    copy: bool = False,
) -> Optional[AnnData]:
    adata = adata.copy() if copy else adata
    barcodes = adata.obs_names.astype(str)
    adata.obs["barcode"] = barcodes
    adata.obs["condition"] = condition
    adata.obs_names = [f"{condition}{sep}{barcode}" for barcode in barcodes]
    return adata if copy else None


script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="integration",
    description=(
        "Compute principal components, compute closest and shared-nearest "
        "neighbors, cluster cells using the Leiden algorithm and integrate data "
        "in an embedding projection."
    ),
    usage=f"python {script_name} [-h] <FILE ...> --outfile <FILE> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    dest="infiles",
    action=cli.Required_length,
    type=lambda x: Path(x).resolve(),
    min=2,
    metavar="FILE",
    help="input files storing counts; the first one is used as reference (format: h5ad)",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing integrated data (format: h5ad)",
)

parser.add_argument(
    "--labels",
    dest="labels",
    action=cli.Required_length,
    type=str,
    min=2,
    required=False,
    default=None,
    metavar="LITERAL",
    help="sample labels ordered with input files",
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
    "--integration",
    dest="integration",
    type=str,
    required=False,
    default="bbknn",
    choices=["bbknn", "ingest", "scanorama"],
    metavar="[bbknn | ingest | scanorama]",
    help="integration method used (default: bbknn)",
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
    "--zero-center",
    dest="zero_center",
    action="store_true",
    required=False,
    help="if true, compute PCA from covariance matrix, otherwise omit zero-centering variables",
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
    default=random.randint(0, 1_000_000_000),
    metavar="INT",
    help="random seed (default: random)",
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

args = parser.parse_args()

if args.pca_dimension < args.clustering_dimension:
    raise ValueError(
        "invalid dimensionality: "
        f"clustering dimension ({args.clustering_dimension}) "
        f"cannot exceed pca dimension ({args.pca_dimension})"
    )

if args.integration == "ingest" and args.embedding == "tsne":
    raise ValueError("ingest does not support tsne embedding")

embedding_label = "UMAP" if args.embedding == "umap" else "t-SNE"

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

if not args.labels:
    args.labels = ["reference"]
    args.labels.extend([f"interest_{i}" for i in range(1, len(args.infiles))])

std.print_task("loading datasets")

adatas = []
for infile, label in zip(args.infiles, args.labels):
    std.print_task(
        f"loading AnnData (condition={label}, file={std.format_path(infile)})"
    )
    adata = ad.read_h5ad(infile)
    namespace_obs_names(adata, condition=label)
    adatas.append(adata)

for adata in adatas:
    adata.X = adata.layers[args.layer].copy()
    clean_adata(adata)

std.print_debug(f"merging datasets (conditions={', '.join(args.labels)})")
try:
    adata = ad.concat(
        adatas=adatas,
        join="inner",
        label="condition",
        keys=args.labels,
        merge="same",
        uns_merge="same",
    )
except Exception as error:
    raise RuntimeError("anndatas concatenation not working") from error
del adatas

std.print_task(
    "estimating highly variable genes "
    f"(flavor={args.flavor}, number={args.top_hvg if args.top_hvg else 'none'})"
)
with std.filter_scanpy_hvg_warnings():
    sc.pp.highly_variable_genes(
        adata,
        layer="counts" if args.flavor == "seurat_v3" else "log-norm",
        flavor=args.flavor,
        span=args.span,
        n_bins=args.bins,
        n_top_genes=args.top_hvg,
        batch_key="condition",
        inplace=True,
    )

if args.integration == "ingest":

    std.print_info("integrating data (method=ingest)")

    reference = args.labels[0]
    std.print_info(f"selecting reference condition (condition={reference})")

    std.print_info(f"splitting datasets (conditions={', '.join(args.labels)})")
    adatas = dict()
    for label in args.labels:
        adatas[label] = adata[adata.obs["condition"] == label].to_memory()

    std.print_task(
        f"computing principal components (dimensions={args.pca_dimension}, condition={reference})"
    )
    sc.tl.pca(
        adatas[reference],
        n_comps=args.pca_dimension,
        zero_center=args.zero_center,
        use_highly_variable=args.only_hvg,
        random_state=np.random.RandomState(args.seed),
        copy=False,
    )

    std.print_task(
        f"computing nearest-neighbor graph (principal components={args.clustering_dimension}, condition={reference})"
    )
    sc.pp.neighbors(
        adatas[reference],
        n_neighbors=args.neighbors,
        use_rep="X_pca",
        n_pcs=args.clustering_dimension,
        metric=args.metric,
        copy=False,
    )

    std.print_task(f"computing shared nearest-neighbor graph (condition={reference})")
    bt.sct.tl.shared_neighbors(
        adatas[reference], snn_key="shared_neighbors", prune_snn=1 / 15, copy=False
    )

    std.print_task(
        f"embedding neighborhood graph (dimensions={args.embedding_dimension}, condition={reference})"
    )
    std.print_task(
        f"computing embedding (method=UMAP, "
        f"dimensions={args.embedding_dimension}, "
        f"min_dist={args.min_dist}, "
        f"spread={args.spread})"
    )
    sc.tl.umap(
        adatas[reference],
        neighbors_key="neighbors",
        n_components=args.embedding_dimension,
        min_dist=args.min_dist,
        spread=args.spread,
        random_state=np.random.RandomState(args.seed),
        copy=False,
    )
    del adatas[reference].uns["umap"]["params"]["random_state"]

    for label in args.labels[1:]:
        std.print_task(f"mapping embeddings (condition={label})")
        sc.tl.ingest(
            adata=adatas[label],
            adata_ref=adatas[reference],
            obs=None,
            embedding_method=["pca", "umap"],
            random_state=np.random.RandomState(args.seed),
            inplace=True,
            n_jobs=args.jobs,
        )

    std.print_debug(f"concatenating datasets (conditions={'+'.join(args.labels)})")
    try:
        adata = ad.concat(
            adatas=list(adatas.values()),
            join="inner",
            label="condition",
            keys=args.labels,
            merge="same",
            uns_merge="same",
        )
    except Exception as error:
        raise RuntimeError("anndatas concatenation not working") from error

    std.print_task(
        f"computing nearest-neighbor graph (principal components={args.clustering_dimension}, dataset=integrated)"
    )
    sc.pp.neighbors(
        adata,
        n_neighbors=args.neighbors,
        use_rep="X_pca",
        n_pcs=args.clustering_dimension,
        metric=args.metric,
        copy=False,
    )

    std.print_task("computing shared nearest-neighbor graph (dataset=integrated)")
    bt.sct.tl.shared_neighbors(
        adata, snn_key="shared_neighbors", prune_snn=1 / 15, copy=False
    )

    std.print_task("clustering cells (algorithm=leiden, dataset=integrated)")
    sc.tl.leiden(
        adata,
        neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
        resolution=args.resolution,
        key_added="cluster",
        random_state=args.seed,
        copy=False,
    )

elif args.integration == "bbknn":

    std.print_info("integrating data (method=BBKNN)")

    std.print_task(f"computing principal components (dimensions={args.pca_dimension})")
    sc.tl.pca(
        adata,
        n_comps=args.pca_dimension,
        zero_center=args.zero_center,
        use_highly_variable=args.only_hvg,
        random_state=np.random.RandomState(args.seed),
        copy=False,
    )

    std.print_task("mapping embeddings")
    with std.disable_print():
        sc.external.pp.bbknn(
            adata,
            batch_key="condition",
            neighbors_within_batch=args.neighbors,
            use_rep="X_pca",
            n_pcs=args.clustering_dimension,
            metric=args.metric,
            approx=None,
            use_annoy=None,
            use_faiss=None,
            computation="cKDTree",
            pynndescent_random_state=args.seed,
            copy=False,
        )

    std.print_task("clustering cells (algorithm=leiden)")
    sc.tl.leiden(
        adata,
        neighbors_key="neighbors",
        resolution=args.resolution,
        key_added="cluster",
        random_state=args.seed,
        copy=False,
    )

    std.print_task(
        f"embedding neighborhood graph (dimensions={args.embedding_dimension})"
    )
    if args.embedding == "umap":
        std.print_task(
            f"computing embedding (method=UMAP, "
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
            f"computing embedding (method=t-SNE, "
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

elif args.integration == "scanorama":

    std.print_info("integrating data (method=scanorama)")

    std.print_info(f"splitting datasets (conditions={'+'.join(args.labels)})")
    adatas = dict()
    for label in args.labels:
        adatas[label] = adata[adata.obs["condition"] == label].to_memory()

    std.print_task(f"computing integrated embedding (dimensions={args.pca_dimension})")
    with std.disable_print():
        adatas = scanorama.correct_scanpy(
            list(adatas.values()),
            dimred=args.pca_dimension,
            return_dimred=True,
            hvg=args.top_hvg,
        )

    std.print_debug(f"concatenating datasets (conditions={'+'.join(args.labels)})")
    try:
        adata = ad.concat(
            adatas=adatas,
            join="inner",
            label="condition",
            keys=args.labels,
            merge="same",
            uns_merge="same",
        )
    except Exception as error:
        raise RuntimeError("anndatas concatenation not working") from error

    std.print_task(
        f"computing nearest-neighbor graph (principal components={args.clustering_dimension})"
    )
    sc.pp.neighbors(
        adata,
        n_neighbors=args.neighbors,
        use_rep="X_scanorama",
        n_pcs=args.clustering_dimension,
        metric=args.metric,
        copy=False,
    )

    std.print_task("computing shared nearest-neighbor graph")
    bt.sct.tl.shared_neighbors(
        adata, snn_key="shared_neighbors", prune_snn=1 / 15, copy=False
    )

    std.print_task("clustering cells (algorithm=leiden)")
    sc.tl.leiden(
        adata,
        neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
        resolution=args.resolution,
        key_added="cluster",
        random_state=args.seed,
        copy=False,
    )

    std.print_task(
        f"embedding neighborhood graph (dimensions={args.embedding_dimension})"
    )
    if args.embedding == "umap":
        std.print_task(
            f"computing embedding (method=UMAP, "
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
            f"computing embedding (method=t-SNE, "
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

std.print_info(
    f"plotting embeddings (directory={os.path.relpath(os.path.dirname(args.outfile))})"
)
pc_plot = Path(f"{os.path.dirname(args.outfile)}/conditions_pc.pdf")
bt.sct.pl.embedding(
    adata,
    obs="condition",
    use_rep="X_pca" if args.integration != "scanorama" else "X_scanorama",
    xlabel=r"$\mathrm{PC_{1}}$",
    ylabel=r"$\mathrm{PC_{2}}$",
    figwidth=6,
    s=2,
    alpha=1,
    show_legend=True,
    lgd_params={
        "title": "condition",
        "ncol": 1,
        "markerscale": 5,
        "frameon": True,
        "edgecolor": bt.sct.pl.get_color("black"),
        "shadow": False,
    },
    n_components=2,
    background_visible=False,
    outfile=pc_plot,
)

embedding_plots = {
    "condition": "conditions.pdf",
    "cluster": "clusters.pdf",
}
for obs, filename in embedding_plots.items():
    embedding_plot = Path(f"{os.path.dirname(args.outfile)}/{filename}")
    bt.sct.pl.embedding(
        adata,
        obs=obs,
        use_rep="X_umap" if args.embedding == "umap" else "X_tsne",
        xlabel=r"$\mathrm{{{}_{{1}}}}$".format(embedding_label),
        ylabel=r"$\mathrm{{{}_{{2}}}}$".format(embedding_label),
        zlabel=r"$\mathrm{{{}_{{3}}}}$".format(embedding_label),
        figwidth=6,
        s=2,
        alpha=1,
        show_legend=True,
        lgd_params={
            "title": obs,
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

composition_plots = {
    "condition": ("cluster", "condition_by_cluster.pdf"),
    "cluster": ("condition", "cluster_by_condition.pdf"),
}

for obs, (groupby, filename) in composition_plots.items():
    composition_plot = Path(f"{os.path.dirname(args.outfile)}/{filename}")
    bt.sct.pl.composition(
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
        xlabel=groupby,
        labelsize=12,
        legend={
            "title": obs,
            "bbox_to_anchor": (1.0, 0.5),
            "loc": "center left",
            "frameon": False,
        },
        outfile=composition_plot,
    )

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
std.write_h5ad(adata, filename=args.outfile, compression="gzip")
