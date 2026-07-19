#!/usr/bin/env python

import argparse
import os
from pathlib import Path

import anndata as ad
import bonesistools as bt

from scbolt import cli, console, omics

omics.set_default_plot_params(bt.omics.pl)

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="knnsc",
    description=(
        "Compute cell manifolds using the k-nearest neighbors-based subclusters "
        "(KNNSC) algorithm.\n"
        "Compute the k-nearest neighbors graph using an embedding space, compute "
        "shortest path lengths in the graph and then search for cluster-related "
        "cell manifolds.\n"
        "Subclusters can be computed with two strategies: centrality, minimizing "
        "distances to the cluster's own barycenter; and periphery, maximizing "
        "distances to other clusters' barycenters."
    ),
    usage=(
        f"python {script_name} <FILE> <FILE> [--csv <FILE>] --obs <LITERAL> "
        "[--centrality <LITERAL ...>] [--periphery <LITERAL ...>] [<args>]"
    ),
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts and clusters (format: h5ad)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing KNNSC macrostates (format: h5ad)",
)

parser.add_argument(
    "--csv",
    dest="csv",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output file storing macrostates (format: csv)",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in adata.obs distinguishing clusters (required)",
)

parser.add_argument(
    "--embedding",
    dest="embedding",
    type=str,
    required=False,
    default="X_umap",
    metavar="KEY",
    help=(
        "embedding key in adata.obsm used when calculating pairwise distances "
        "(default: X_umap)"
    ),
)

parser.add_argument(
    "--plot-representation",
    dest="plot_representation",
    type=str,
    required=False,
    default=None,
    metavar="KEY",
    help=(
        "Embedding key in adata.obsm used for plotting KNNSC macrostates.\n"
        "Default: None."
    ),
)

parser.add_argument(
    "--dimension",
    dest="dimension",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help=(
        "number of embedding dimensions used when calculating pairwise distances "
        "(default: None)"
    ),
)

parser.add_argument(
    "--neighbors",
    dest="neighbors",
    type=int,
    required=False,
    default=20,
    metavar="INT",
    help=(
        "number of closest neighbors used to compute the k-nearest neighbors graph "
        "(default: 20)"
    ),
)

parser.add_argument(
    "--metric",
    dest="metric",
    action=cli.Store_metric,
    required=False,
    default="euclidean",
    help="metric used when calculating pairwise distances (default: euclidean)",
)

parser.add_argument(
    "--min-cluster-size",
    dest="min_cluster_size",
    type=int,
    required=False,
    default=100,
    metavar="INT",
    help=(
        "minimum cluster size required to use a label as a KNNSC candidate (default: "
        "100)"
    ),
)

parser.add_argument(
    "--size",
    dest="size",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of cells in each macrostate (default: 50)",
)

parser.add_argument(
    "--method",
    dest="method",
    type=str,
    required=False,
    choices=["dijkstra", "bellman-ford"],
    default="dijkstra",
    metavar="[dijkstra | bellman-ford]",
    help=(
        "method used for computing pairwise shortest path lengths between cells and "
        "barycenters (default: dijkstra)"
    ),
)

parser.add_argument(
    "--centrality",
    dest="centrality",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help=(
        "cluster labels refined using the centrality-based strategy, minimizing "
        "distances to their own barycenter (default: None)"
    ),
)

parser.add_argument(
    "--periphery",
    dest="periphery",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help=(
        "cluster labels refined using the periphery-based strategy, maximizing "
        "distances to other clusters' barycenters (default: None)"
    ),
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

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

console.print_task(f"loading AnnData (file={console.format_path(args.infile)})")
adata = ad.read_h5ad(args.infile)

if adata.obs[args.obs].dtype.name != "category":
    adata.obs[args.obs] = adata.obs[args.obs].astype("category")

if args.dimension is None:
    args.dimension = adata.obsm[args.embedding].shape[1]

if args.min_cluster_size < 0:
    parser.error("--min-cluster-size must be a non-negative integer")

cluster_counts = adata.obs[args.obs].value_counts()
clusters = list(adata.obs[args.obs].cat.categories)
eligible_clusters = {
    cluster
    for cluster in clusters
    if int(cluster_counts.get(cluster, 0)) > 0
    and int(cluster_counts.get(cluster, 0)) >= args.min_cluster_size
}
if not eligible_clusters:
    parser.error(
        "no cluster has at least " f"--min-cluster-size={args.min_cluster_size} cells"
    )

selected_clusters = set(args.centrality or []) | set(args.periphery or [])
missing_clusters = sorted(selected_clusters - set(clusters))
if missing_clusters:
    parser.error(
        "cluster(s) not found in "
        f"adata.obs[{args.obs!r}]: {', '.join(missing_clusters)}"
    )

small_selected_clusters = [
    f"{cluster} (size={int(cluster_counts.get(cluster, 0))})"
    for cluster in clusters
    if cluster in selected_clusters
    and int(cluster_counts.get(cluster, 0)) > 0
    and cluster not in eligible_clusters
]
if small_selected_clusters:
    parser.error(
        "cluster(s) smaller than "
        f"--min-cluster-size={args.min_cluster_size}: "
        + ", ".join(small_selected_clusters)
    )

empty_selected_clusters = [
    cluster
    for cluster in clusters
    if cluster in selected_clusters and int(cluster_counts.get(cluster, 0)) == 0
]
if empty_selected_clusters:
    parser.error(
        "empty cluster(s) cannot be used as KNNSC candidates: "
        + ", ".join(empty_selected_clusters)
    )

console.print_task("estimating macrostates (method=KNNSC)")
knnsc = bt.omics.tl.KNNSC()

console.print_info(
    f"initializing graph parameters "
    f"(embedding={console.format_embedding(args.embedding)}, dimension={args.dimension}, "
    f"neighbors={args.neighbors}, metric={args.metric}, jobs={args.jobs})"
)
console.print_info(
    f"initializing distance parameters "
    f"(min_cluster_size={args.min_cluster_size}, "
    f"method={args.method}, jobs={args.jobs})"
)
console.print_info("fitting neighbors graph and shortest-path distances")
knnsc.fit(
    adata,
    cluster_key=args.obs,
    representation=args.embedding,
    n_components=args.dimension,
    n_neighbors=args.neighbors,
    metric=args.metric,
    min_cluster_size=args.min_cluster_size,
    method=args.method,
    n_jobs=args.jobs,
)

if args.centrality is None and args.periphery is None:
    centrality_log = "{}"
    periphery_log = "{all eligible clusters}"
else:
    centrality_log = (
        "{}" if args.centrality is None else "{" + ", ".join(args.centrality) + "}"
    )
    periphery_log = (
        "{}" if args.periphery is None else "{" + ", ".join(args.periphery) + "}"
    )

console.print_info(
    f"predicting subclusters "
    f"(centrality={centrality_log}, periphery={periphery_log})"
)
macrostates = knnsc.predict(
    subcluster_size=args.size,
    key="macrostate",
    peripheral_clusters=args.periphery,
    central_clusters=args.centrality,
)
adata.obs["macrostate"] = macrostates

if args.plot_representation:
    plot = Path(f"{os.path.dirname(args.outfile)}/knnsc.pdf")
    console.print_task(f"plotting embeddings (file={console.format_path(plot)})")
    omics.plot_categorical_embedding(
        adata,
        obs="macrostate",
        embedding=args.plot_representation,
        label=console.format_embedding(args.plot_representation),
        outfile=plot,
    )

console.print_task(f"saving AnnData (file={console.format_path(args.outfile)})")
omics.write_h5ad(adata, filename=args.outfile, compression="gzip")

if args.csv:
    console.print_task(f"saving KNNSC macrostates (file={console.format_path(args.csv)})")
    adata.obs["macrostate"].to_csv(args.csv, sep=",", index=True)
