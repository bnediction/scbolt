import argparse
import os
import random
from pathlib import Path

import anndata as ad
import bonesistools as bt
import numpy as np
from scbolt import cli, console, omics
from scbolt.runtime import single_thread

omics.set_default_plot_params(bt.omics.pl)


def _format_percent_if_float(value):
    if value is None:
        return "none"
    if isinstance(value, (float, np.floating)):
        return f"{value:.2%}"
    return str(value)


EMBEDDINGS = (
    ("umap", "X_umap", "umap.pdf"),
    ("tsne", "X_tsne", "tsne.pdf"),
    ("spectral", "X_se", "spectral.pdf"),
)


def compute_embedding(adata, method: str, args) -> None:
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
            representation="X_pca",
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
            copy=False,
        )


def plot_embedding(
    adata, method: str, representation: str, outfile: Path, args
) -> None:
    embedding_label = console.format_embedding(method)
    bt.omics.pl.embedding(
        adata,
        obs="cluster",
        representation=representation,
        xlabel=omics.axis_label(embedding_label, 1),
        ylabel=omics.axis_label(embedding_label, 2),
        zlabel=omics.axis_label(embedding_label, 3),
        figwidth=6,
        legend={
            "title": "clusters",
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
        prog="clustering",
        description=(
            "Compute principal components, compute closest and shared-nearest "
            "neighbors, cluster cells using the Leiden algorithm and compute UMAP, "
            "t-SNE, and spectral embeddings."
        ),
        usage=f"python {script_name} <FILE> <FILE> [<args>]",
        formatter_class=cli.HelpFormatter,
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
        "--expression",
        dest="expression",
        type=str,
        required=True,
        metavar="LITERAL",
        help="Expression layer used to compute principal components. Required.",
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
        "--centered-pca",
        dest="centered_pca",
        action="store_true",
        default=False,
        required=False,
        help="center variables before PCA",
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
        default=random.random(),
        metavar="INT",
        help="random seed (default: random)",
    )

    args = parser.parse_args()

    if args.pca_dimension < args.clustering_dimension:
        raise ValueError(
            f"invalid values for arguments: 'pca-dimension' > 'clustering-dimension' not satisfied (pca-dimension: {args.pca_dimension}, clustering-dimension: {args.clustering_dimension})"
        )

    if not Path(os.path.dirname(args.outfile)).exists():
        os.makedirs(Path(os.path.dirname(args.outfile)))

    console.print_task(f"loading AnnData (file={console.format_path(args.infile)})")

    adata = ad.read_h5ad(args.infile)

    if args.only_hvg:
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
        )

    console.print_task(f"computing principal components (dimensions={args.pca_dimension})")
    if args.only_hvg:
        console.print_info("filtering PCA features (scope=highly variable genes)")
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
        "computing nearest-neighbor graph "
        f"(principal components={args.clustering_dimension}, "
        f"neighbors={args.neighbors}, metric={args.metric})"
    )
    bt.omics.tl.neighbors(
        adata,
        n_neighbors=args.neighbors,
        representation="X_pca",
        n_pcs=args.clustering_dimension,
        metric=args.metric,
        copy=False,
    )

    if args.adjacency == "snn":
        prune_snn = 1 / 15
        prune_snn_msg = _format_percent_if_float(prune_snn)
        console.print_task(
            f"computing shared nearest-neighbor graph (pruning_threshold={prune_snn_msg})"
        )
        bt.omics.tl.shared_neighbors(
            adata,
            key_added="shared_neighbors",
            prune=prune_snn,
            copy=False,
        )

    console.print_task(f"clustering cells (algorithm=leiden, resolution={args.resolution})")
    bt.omics.tl.leiden(
        adata,
        neighbors_key="neighbors" if args.adjacency == "knn" else "shared_neighbors",
        resolution=args.resolution,
        key_added="cluster",
        seed=args.seed,
        copy=False,
    )
    console.print_result(f"identified {adata.obs['cluster'].nunique()} clusters")

    for method, _, _ in EMBEDDINGS:
        compute_embedding(adata, method, args)

    console.print_info(
        f"plotting embeddings (directory={os.path.relpath(os.path.dirname(args.outfile))})"
    )
    for method, representation, filename in EMBEDDINGS:
        plot_embedding(
            adata,
            method,
            representation,
            Path(f"{os.path.dirname(args.outfile)}/{filename}"),
            args,
        )

    console.print_task(f"saving AnnData (file={console.format_path(args.outfile)})")
    omics.drop_expression_matrices(
        adata,
        layers=("norm", "scale", "correct"),
    )
    omics.write_h5ad(adata, filename=args.outfile, compression="gzip")


if __name__ == "__main__":
    main()
