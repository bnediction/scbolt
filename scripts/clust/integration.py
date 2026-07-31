#!/usr/bin/env python

import argparse
import os
import random
from pathlib import Path
from typing import Optional, Sequence

import anndata as ad
import bonesistools as bt
import numpy as np
import pandas as pd
import scanorama
import scanpy as sc
from anndata import AnnData
from bonesistools.omics import _typing as omics_typing

from scbolt import cli, console, omics
from scbolt.omics import (
    check_exported_composition,
    composition_rows,
    compute_condition_composition,
)
from scbolt.runtime import single_thread

omics.set_default_plot_params(bt.omics.pl)


@omics_typing.anndata_checker
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


def compute_shared_neighbors_if_needed(
    adata: AnnData,
    args: argparse.Namespace,
    *,
    context: Optional[str] = None,
) -> None:
    if args.adjacency != "snn":
        return

    message = "computing shared nearest-neighbor graph"
    if context:
        message = f"{message} ({context})"
    console.print_task(message)
    bt.omics.tl.shared_neighbors(
        adata,
        key_added="shared_neighbors",
        prune=1 / 15,
        copy=False,
    )


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


def summarize_cluster_composition(
    adata: AnnData,
    cluster_key: str = "cluster",
    condition_key: str = "condition",
) -> pd.DataFrame:
    (
        condition_by_cluster,
        cluster_by_condition,
        condition_enrichment_by_cluster,
    ) = compute_condition_composition(
        adata.obs,
        group_col=cluster_key,
        condition_col=condition_key,
    )
    composition = pd.DataFrame(
        composition_rows(
            condition_by_group=condition_by_cluster,
            group_by_condition=cluster_by_condition,
            condition_enrichment_by_group=condition_enrichment_by_cluster,
            group_key="cluster",
        )
    )
    check_exported_composition(composition, group_key="cluster")
    return composition


EMBEDDINGS = (
    ("umap", "X_umap", "umap_clust.pdf", "umap_cond.pdf"),
    ("tsne", "X_tsne", "tsne_clust.pdf", "tsne_cond.pdf"),
    ("spectral", "X_se", "spectral_clust.pdf", "spectral_cond.pdf"),
)


def compute_embedding(adata, method: str, args, representation: str = "X_pca") -> None:
    embedding_label = (
        "spectral" if method == "spectral" else console.format_embedding(method)
    )
    if method == "umap":
        console.print_task(
            f"computing embedding (method={embedding_label}, "
            f"dimensions={args.embedding_dimension}, "
            f"min_dist={args.min_dist}, "
            f"spread={args.spread}, "
            f"n_iter={args.embedding_n_iter})"
        )
        bt.omics.tl.umap(
            adata,
            neighbors_key="neighbors",
            n_components=args.embedding_dimension,
            min_dist=args.min_dist,
            spread=args.spread,
            n_iter=args.embedding_n_iter,
            seed=args.seed,
            copy=False,
        )
    elif method == "tsne":
        console.print_task(
            f"computing embedding (method={embedding_label}, "
            f"dimensions={args.embedding_dimension}, "
            f"metric={args.metric}, "
            f"n_iter={args.embedding_n_iter})"
        )
        bt.omics.tl.tsne(
            adata,
            representation=representation,
            n_pcs=args.clustering_dimension,
            n_components=args.embedding_dimension,
            n_iter=args.embedding_n_iter,
            metric=args.metric,
            seed=args.seed,
            copy=False,
        )
    elif method == "spectral":
        console.print_task(
            f"computing embedding (method={embedding_label}, "
            f"dimensions={args.embedding_dimension})"
        )
        bt.omics.tl.spectral(
            adata,
            neighbors_key="neighbors",
            n_components=args.embedding_dimension,
            seed=args.seed,
            n_jobs=args.jobs,
            copy=False,
        )


def compute_embeddings(adata, args, representation: str = "X_pca") -> None:
    for method, _, _, _ in EMBEDDINGS:
        compute_embedding(adata, method, args, representation=representation)


def plot_embedding(
    adata,
    obs: str,
    method: str,
    representation: str,
    outfile: Path,
    args,
) -> None:
    embedding_label = console.format_embedding(method)
    bt.omics.pl.embedding(
        adata,
        obs=obs,
        representation=representation,
        xlabel=omics.axis_label(embedding_label, 1),
        ylabel=omics.axis_label(embedding_label, 2),
        zlabel=omics.axis_label(embedding_label, 3),
        figwidth=6,
        legend={
            "title": obs,
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": bt.omics.pl.get_color("black"),
            "shadow": False,
        },
        n_components=3 if args.embedding_dimension > 2 else 2,
        background_visible=False,
        outfile=outfile,
    )


script_name = Path(__file__).name

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="integration",
        description=(
            "Compute principal components, compute closest and shared-nearest "
            "neighbors, cluster cells using the Leiden algorithm and integrate data "
            "before computing UMAP, t-SNE, and spectral embeddings."
        ),
        usage=f"python {script_name} [-h] <FILE ...> --outfile <FILE> [<args>]",
        formatter_class=cli.HelpFormatter,
    )

    parser.add_argument(
        dest="infiles",
        action=cli.Required_length,
        type=lambda x: Path(x).resolve(),
        min=2,
        metavar="FILE",
        help=(
            "input files storing counts; the first one is used as reference (format: "
            "h5ad)"
        ),
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
        "--expression",
        dest="expression",
        type=str,
        required=True,
        metavar="LITERAL",
        help="Expression layer used for integration and PCA. Required.",
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
        help=(
            "number of principal components taken into account for clustering cells "
            "(default: 15)"
        ),
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
        "--method",
        dest="method",
        type=str,
        required=False,
        default="loess",
        choices=["loess", "binning"],
        metavar="[loess | binning]",
        help="method used for identifying highly variable genes (default: loess)",
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
        help=(
            "fraction of cells used when estimating the variance in the loess model (used "
            "only if method='loess', default: 0.3)"
        ),
    )

    parser.add_argument(
        "--bins",
        dest="bins",
        type=int,
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
        "--centered-pca",
        "--zero-center",
        dest="centered_pca",
        action="store_true",
        default=False,
        required=False,
        help="center variables before PCA",
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
        help=(
            "metric used for computing closest neighbors and optionally t-SNE projection "
            "(default: euclidean)"
        ),
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
        "--embedding-n-iter",
        dest="embedding_n_iter",
        type=int,
        required=False,
        default=500,
        metavar="INT",
        help="number of optimization iterations used by UMAP and t-SNE (default: 500)",
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

    if not Path(os.path.dirname(args.outfile)).exists():
        os.makedirs(Path(os.path.dirname(args.outfile)))

    if not args.labels:
        args.labels = ["reference"]
        args.labels.extend([f"interest_{i}" for i in range(1, len(args.infiles))])

    console.print_task("loading datasets")

    adatas = []
    for infile, label in zip(args.infiles, args.labels):
        console.print_task(
            f"loading AnnData (condition={label}, file={console.format_path(infile)})"
        )
        adata = ad.read_h5ad(infile)
        namespace_obs_names(adata, condition=label)
        adatas.append(adata)

    for adata in adatas:
        clean_adata(adata)
        if args.integration in {"ingest", "scanorama"}:
            adata.X = adata.layers[args.expression].copy()

    console.print_debug(f"merging datasets (conditions={', '.join(args.labels)})")
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

    console.print_task(
        "estimating highly variable genes "
        f"({console.format_hvg_parameters(method=args.method, number=args.top_hvg)})"
    )
    bt.omics.pp.hvg(
        adata,
        expression="counts" if args.method == "loess" else "log-norm",
        method=args.method,
        span=args.span,
        n_bins=args.bins,
        n_features=args.top_hvg,
        batch_key="condition",
        batch_selection="rank",
    )

    if args.integration == "ingest":

        console.print_info("integrating data (method=ingest)")

        reference = args.labels[0]
        console.print_info(f"selecting reference condition (condition={reference})")

        console.print_info(f"splitting datasets (conditions={', '.join(args.labels)})")
        adatas = dict()
        for label in args.labels:
            adatas[label] = adata[adata.obs["condition"] == label].to_memory()

        console.print_task(
            f"computing principal components (dimensions={args.pca_dimension}, condition={reference})"
        )
        with single_thread():
            bt.omics.tl.pca(
                adatas[reference],
                n_components=args.pca_dimension,
                layer=args.expression,
                zero_center=args.centered_pca,
                var_subset="highly_variable" if args.only_hvg else None,
                seed=args.seed,
                copy=False,
            )

        console.print_task(
            "computing nearest-neighbor graph "
            f"(principal components={args.clustering_dimension}, "
            f"neighbors={args.neighbors}, metric={args.metric}, condition={reference})"
        )
        bt.omics.tl.neighbors(
            adatas[reference],
            n_neighbors=args.neighbors,
            representation="X_pca",
            n_pcs=args.clustering_dimension,
            metric=args.metric,
            copy=False,
        )

        for label in args.labels[1:]:
            console.print_task(f"mapping PCA embedding (condition={label})")
            sc.tl.ingest(
                adata=adatas[label],
                adata_ref=adatas[reference],
                obs=None,
                embedding_method=["pca"],
                random_state=np.random.RandomState(args.seed),
                inplace=True,
                n_jobs=args.jobs,
            )

        console.print_debug(f"concatenating datasets (conditions={'+'.join(args.labels)})")
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

        console.print_task(
            "computing nearest-neighbor graph "
            f"(principal components={args.clustering_dimension}, "
            f"neighbors={args.neighbors}, metric={args.metric}, dataset=integrated)"
        )
        bt.omics.tl.neighbors(
            adata,
            n_neighbors=args.neighbors,
            representation="X_pca",
            n_pcs=args.clustering_dimension,
            metric=args.metric,
            copy=False,
        )

        compute_shared_neighbors_if_needed(adata, args, context="dataset=integrated")

        console.print_task(
            f"clustering cells (algorithm=leiden, resolution={args.resolution}, dataset=integrated)"
        )
        bt.omics.tl.leiden(
            adata,
            neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
            resolution=args.resolution,
            key_added="cluster",
            seed=args.seed,
            copy=False,
        )
        compute_embeddings(adata, args, representation="X_pca")

    elif args.integration == "bbknn":

        console.print_info("integrating data (method=BBKNN)")

        console.print_task(f"computing principal components (dimensions={args.pca_dimension})")
        with single_thread():
            bt.omics.tl.pca(
                adata,
                n_components=args.pca_dimension,
                layer=args.expression,
                zero_center=args.centered_pca,
                var_subset="highly_variable" if args.only_hvg else None,
                seed=args.seed,
                copy=False,
            )

        console.print_task(
            "mapping embeddings "
            f"(neighbors within batch={args.neighbors}, metric={args.metric})"
        )
        with console.suppress_output():
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

        compute_shared_neighbors_if_needed(adata, args)

        console.print_task(f"clustering cells (algorithm=leiden, resolution={args.resolution})")
        bt.omics.tl.leiden(
            adata,
            neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
            resolution=args.resolution,
            key_added="cluster",
            seed=args.seed,
            copy=False,
        )

        compute_embeddings(adata, args, representation="X_pca")

    elif args.integration == "scanorama":

        console.print_info("integrating data (method=scanorama)")

        console.print_info(f"splitting datasets (conditions={'+'.join(args.labels)})")
        adatas = dict()
        for label in args.labels:
            adatas[label] = adata[adata.obs["condition"] == label].to_memory()

        console.print_task(f"computing integrated embedding (dimensions={args.pca_dimension})")
        with console.suppress_output():
            adatas = scanorama.correct_scanpy(
                list(adatas.values()),
                dimred=args.pca_dimension,
                return_dimred=True,
                hvg=args.top_hvg,
            )

        console.print_debug(f"concatenating datasets (conditions={'+'.join(args.labels)})")
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

        console.print_task(
            "computing nearest-neighbor graph "
            f"(principal components={args.clustering_dimension}, "
            f"neighbors={args.neighbors}, metric={args.metric})"
        )
        bt.omics.tl.neighbors(
            adata,
            n_neighbors=args.neighbors,
            representation="X_scanorama",
            n_pcs=args.clustering_dimension,
            metric=args.metric,
            copy=False,
        )

        compute_shared_neighbors_if_needed(adata, args)

        console.print_task(f"clustering cells (algorithm=leiden, resolution={args.resolution})")
        bt.omics.tl.leiden(
            adata,
            neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
            resolution=args.resolution,
            key_added="cluster",
            seed=args.seed,
            copy=False,
        )

        compute_embeddings(adata, args, representation="X_scanorama")

    composition = summarize_cluster_composition(adata)
    composition_file = Path(f"{os.path.dirname(args.outfile)}/composition.csv")
    console.print_task(f"saving cluster composition (file={console.format_path(composition_file)})")
    composition.to_csv(composition_file, sep=",", index=False)

    console.print_info(
        f"plotting embeddings (directory={os.path.relpath(os.path.dirname(args.outfile))})"
    )
    pc_plot = Path(f"{os.path.dirname(args.outfile)}/pca.pdf")
    bt.omics.pl.embedding(
        adata,
        obs="condition",
        representation="X_pca" if args.integration != "scanorama" else "X_scanorama",
        xlabel=omics.axis_label("PC", 1),
        ylabel=omics.axis_label("PC", 2),
        figwidth=6,
        legend={
            "title": "condition",
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": bt.omics.pl.get_color("black"),
            "shadow": False,
        },
        background_visible=False,
        outfile=pc_plot,
    )

    for method, representation, cluster_filename, condition_filename in EMBEDDINGS:
        plot_embedding(
            adata,
            "cluster",
            method,
            representation,
            Path(f"{os.path.dirname(args.outfile)}/{cluster_filename}"),
            args,
        )
        plot_embedding(
            adata,
            "condition",
            method,
            representation,
            Path(f"{os.path.dirname(args.outfile)}/{condition_filename}"),
            args,
        )

    composition_plots = {
        "condition": ("cluster", "condition_by_cluster.pdf"),
        "cluster": ("condition", "cluster_by_condition.pdf"),
    }

    for obs, (groupby, filename) in composition_plots.items():
        composition_plot = Path(f"{os.path.dirname(args.outfile)}/{filename}")
        bt.omics.pl.composition(
            adata,
            obs=obs,
            groupby=groupby,
            dropna=False,
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

    console.print_task(f"saving AnnData (file={console.format_path(args.outfile)})")
    omics.drop_expression_matrices(
        adata,
        layers=("norm", "scale", "correct"),
    )
    omics.write_h5ad(adata, filename=args.outfile, compression="gzip")


if __name__ == "__main__":
    main()
