#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse, cli
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


@bt.sct.anndata_checker
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
    if "leiden" in adata.uns.keys():
        del adata.uns["leiden"]
    if "tsne" in adata.uns.keys():
        del adata.uns["tsne"]
    if "umap" in adata.uns.keys():
        del adata.uns["umap"]
    del adata.obsm, adata.obsp, adata.varm, adata.varp

    return adata if copy else None


parser = argparse.ArgumentParser(
    prog="integration",
    description=(
        "Compute principal components, compute closest and shared-nearest "
        "neighbors, cluster cells using the Leiden algorithm and integrate data "
        "in an embedding projection."
    ),
    usage="python integration.py [-h] <FILE ...> --outfile <FILE> [<args>]",
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
    "--zero-center",
    dest="zero_center",
    action="store_true",
    required=False,
    help="if true, compute PCA from covariance matrix, otherwise omit zero-centering variables",
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of highly variable genes (default: None)",
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
        f"invalid values for arguments: 'pca-dimension' > 'clustering-dimension' not satisfied (pca-dimension: {args.pca_dimension}, clustering-dimension: {args.clustering_dimension})"
    )

if args.integration == "ingest" and args.embedding == "tsne":
    raise ValueError(f"ingest does not support tsne embedding")

embedding_label = "UMAP" if args.embedding == "umap" else "t-SNE"

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

if not args.labels:
    args.labels = ["reference"]
    args.labels.extend([f"interest_{i}" for i in range(1, len(args.infiles))])

std.print_task("loading datasets")

adatas = []
for infile, label in zip(args.infiles, args.labels):
    std.print_info(f"loading dataset '{label}' from {str(infile)}")
    adatas.append(ad.read_h5ad(infile))

for adata in adatas:
    adata.X = adata.layers[args.layer].copy()
    clean_adata(adata)

std.print_debug(
    "merging datasets ({0})".format(", ".join(f"'{label}'" for label in args.labels))
)
try:
    adata = ad.concat(
        adatas=adatas,
        join="inner",
        label="condition",
        keys=args.labels,
        merge="same",
        uns_merge="same",
    )
except:
    raise RuntimeError("anndatas concatenation not working")
del adatas

if args.integration == "ingest":

    std.print_info("integrating data using ingest")

    reference = args.labels[0]
    std.print_info(f"using reference dataset: {reference}")

    std.print_info(f"splitting datasets ({' '.join(label for label in args.labels)})")
    adatas = dict()
    for label in args.labels:
        adatas[label] = adata[adata.obs["condition"] == label].to_memory()

    if args.hvg:
        std.print_task(
            f"computing top {args.hvg} highly variable genes for each dataset"
        )
        for label in args.labels:
            sc.pp.highly_variable_genes(
                adatas[label],
                layer="counts",
                flavor="seurat_v3",
                span=0.3,
                n_bins=20,
                n_top_genes=args.hvg,
                inplace=True,
            )

    std.print_task(
        f"computing top {args.pca_dimension} principal components (dataset: {reference})"
    )
    sc.tl.pca(
        adatas[reference],
        n_comps=args.pca_dimension,
        zero_center=args.zero_center,
        use_highly_variable=(args.hvg is not None),
        random_state=np.random.RandomState(args.seed),
        copy=False,
    )

    std.print_task(
        f"computing closest neighbors-related connectivities and similarities using top {args.clustering_dimension} principal components (dataset: {reference})"
    )
    sc.pp.neighbors(
        adatas[reference],
        n_neighbors=args.neighbors,
        use_rep="X_pca",
        n_pcs=args.clustering_dimension,
        metric=args.metric,
        copy=False,
    )

    std.print_task(
        f"computing shared nearest neighbors-related connectivities and similarities (dataset: {reference})"
    )
    bt.sct.tl.shared_neighbors(
        adatas[reference], snn_key="shared_neighbors", prune_snn=1 / 15, copy=False
    )

    std.print_task(
        f"embedding the neighborhood graph in {args.embedding_dimension} dimensions (dataset: {reference})"
    )
    std.print_info("computing Uniform Manifold Approximation and Projection (UMAP)")
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
        std.print_task(f"mapping embeddings using ingest (dataset: {label})")
        sc.tl.ingest(
            adata=adatas[label],
            adata_ref=adatas[reference],
            obs=None,
            embedding_method=["pca", "umap"],
            random_state=np.random.RandomState(args.seed),
            inplace=True,
            n_jobs=args.jobs,
        )

    std.print_debug(
        f"concatenating datasets ({' '.join(label for label in args.labels)})"
    )
    try:
        adata = ad.concat(
            adatas=list(adatas.values()),
            join="inner",
            label="condition",
            keys=args.labels,
            merge="same",
            uns_merge="same",
        )
    except:
        raise RuntimeError("anndatas concatenation not working")

    std.print_task(
        f"computing closest neighbors-related connectivities and similarities using top {args.clustering_dimension} principal components (dataset: integrated)"
    )
    sc.pp.neighbors(
        adata,
        n_neighbors=args.neighbors,
        use_rep="X_pca",
        n_pcs=args.clustering_dimension,
        metric=args.metric,
        copy=False,
    )

    std.print_task(
        "computing shared nearest neighbors-related connectivities and similarities (dataset: integrated)"
    )
    bt.sct.tl.shared_neighbors(
        adata, snn_key="shared_neighbors", prune_snn=1 / 15, copy=False
    )

    std.print_task("clustering cells using Leiden algorithm (dataset: integrated)")
    sc.tl.leiden(
        adata,
        neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
        resolution=args.resolution,
        key_added=f"leiden",
        random_state=args.seed,
        copy=False,
    )

elif args.integration == "bbknn":

    std.print_info("integrating data using BBKNN")

    if args.hvg:
        std.print_task(f"computing top {args.hvg} highly variable genes")
        sc.pp.highly_variable_genes(
            adata,
            layer="counts",
            flavor="seurat_v3",
            span=0.3,
            n_bins=20,
            n_top_genes=args.hvg,
            inplace=True,
        )

    std.print_task(f"computing top {args.pca_dimension} principal components")
    sc.tl.pca(
        adata,
        n_comps=args.pca_dimension,
        zero_center=args.zero_center,
        use_highly_variable=(args.hvg is not None),
        random_state=np.random.RandomState(args.seed),
        copy=False,
    )

    std.print_task("mapping embeddings using batch balanced nearest neighbors")
    with std.disable_print():
        sc.external.pp.bbknn(
            adata,
            batch_key="condition",
            neighbors_within_batch=args.neighbors,
            use_rep="X_pca",
            n_pcs=args.clustering_dimension,
            metric=args.metric,
            approx=False,
            use_annoy=False,
            pynndescent_random_state=args.seed,
            copy=False,
        )

    std.print_task("clustering cells using Leiden algorithm")
    sc.tl.leiden(
        adata,
        neighbors_key="neighbors",
        resolution=args.resolution,
        key_added=f"leiden",
        random_state=args.seed,
        copy=False,
    )

    std.print_task(
        f"embedding the neighborhood graph in {args.embedding_dimension} dimensions"
    )
    if args.embedding == "umap":
        std.print_info("computing Uniform Manifold Approximation and Projection (UMAP)")
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
        std.print_info(
            "computing t-distributed Stochastic Neighborhood Embedding (t-SNE)"
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

    std.print_info("integrating data using scanorama")

    std.print_info(f"splitting datasets ({' '.join(label for label in args.labels)})")
    adatas = dict()
    for label in args.labels:
        adatas[label] = adata[adata.obs["condition"] == label].to_memory()

    std.print_task("computing integrated embedding using scanorama")
    with std.disable_print():
        adatas = scanorama.correct_scanpy(
            list(adatas.values()),
            dimred=args.pca_dimension,
            return_dimred=True,
            hvg=args.hvg,
        )

    std.print_debug(
        f"concatenating datasets ({' '.join(label for label in args.labels)})"
    )
    try:
        adata = ad.concat(
            adatas=adatas,
            join="inner",
            label="condition",
            keys=args.labels,
            merge="same",
            uns_merge="same",
        )
    except:
        raise RuntimeError("anndatas concatenation not working")

    std.print_task(
        f"computing closest neighbors-related connectivities and similarities using top {args.clustering_dimension} principal components"
    )
    sc.pp.neighbors(
        adata,
        n_neighbors=args.neighbors,
        use_rep="X_scanorama",
        n_pcs=args.clustering_dimension,
        metric=args.metric,
        copy=False,
    )

    std.print_task(
        "computing shared nearest neighbors-related connectivities and similarities"
    )
    bt.sct.tl.shared_neighbors(
        adata, snn_key="shared_neighbors", prune_snn=1 / 15, copy=False
    )

    std.print_task("clustering cells using Leiden algorithm")
    sc.tl.leiden(
        adata,
        neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
        resolution=args.resolution,
        key_added=f"leiden",
        random_state=args.seed,
        copy=False,
    )

    std.print_task(
        f"embedding the neighborhood graph in {args.embedding_dimension} dimensions"
    )
    if args.embedding == "umap":
        std.print_info("computing Uniform Manifold Approximation and Projection (UMAP)")
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
        std.print_info(
            "computing t-distributed Stochastic Neighborhood Embedding (t-SNE)"
        )
        sc.tl.tsne(
            adata,
            n_pcs=args.embedding_dimension,
            use_rep="X_pca",
            metric=args.metric,
            random_state=np.random.RandomState(args.seed),
            copy=False,
        )

pc_plot = Path(f"{os.path.dirname(args.outfile)}/pc_condition.pdf")
std.print_info(
    f"plotting embeddings in {os.path.relpath(os.path.dirname(args.outfile))}"
)
bt.sct.pl.embedding_plot(
    adata,
    obs="condition",
    use_rep="X_pca" if args.integration != "scanorama" else "X_scanorama",
    xlabel=r"$\mathrm{PC_{1}}$",
    ylabel=r"$\mathrm{PC_{2}}$",
    figwidth=6,
    s=2,
    alpha=1,
    add_legend=True,
    lgd_params={
        "title": "conditions",
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

for obs in ["condition", "leiden"]:
    embedding_plot = Path(f"{os.path.dirname(args.outfile)}/{args.embedding}_{obs}.pdf")
    bt.sct.pl.embedding_plot(
        adata,
        obs=obs,
        use_rep="X_umap" if args.embedding == "umap" else "X_tsne",
        xlabel=r"$\mathrm{{{}_{{1}}}}$".format(embedding_label),
        ylabel=r"$\mathrm{{{}_{{2}}}}$".format(embedding_label),
        zlabel=r"$\mathrm{{{}_{{3}}}}$".format(embedding_label),
        figwidth=6,
        s=2,
        alpha=1,
        add_legend=True,
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

std.print_task(f"saving data in {str(args.outfile)}")
adata.write_h5ad(filename=args.outfile, compression="gzip")
