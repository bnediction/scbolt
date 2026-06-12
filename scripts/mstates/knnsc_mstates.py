#!/usr/bin/env python

import os
import std
import argparse
import cli
from pathlib import Path

import anndata as ad
import bonesistools as bt

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
    formatter_class=argparse.RawDescriptionHelpFormatter,
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
    help="embedding key in adata.obsm used when calculating pairwise distances (default: X_umap)",
)

parser.add_argument(
    "--dimension",
    dest="dimension",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of embedding dimensions used when calculating pairwise distances (default: None)",
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
    "--neighbors",
    dest="neighbors",
    type=int,
    required=False,
    default=20,
    metavar="INT",
    help="number of closest neighbors used to compute the k-nearest neighbors graph (default: 20)",
)

parser.add_argument(
    "--min-cluster-size",
    dest="min_cluster_size",
    type=int,
    required=False,
    default=100,
    metavar="INT",
    help="minimum cluster size required to use a label as a KNNSC candidate (default: 100)",
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
    help="method used for computing pairwise shortest path lengths between cells and barycenters (default: dijkstra)",
)

parser.add_argument(
    "--centrality",
    dest="centrality",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="cluster labels refined using the centrality-based strategy, minimizing distances to their own barycenter (default: None)",
)

parser.add_argument(
    "--periphery",
    dest="periphery",
    type=str,
    required=False,
    nargs="+",
    default=None,
    metavar="LITERAL",
    help="cluster labels refined using the periphery-based strategy, maximizing distances to other clusters' barycenters (default: None)",
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

std.print_task(f"loading AnnData (file={std.format_path(args.infile)})")
adata = ad.read_h5ad(args.infile)

if adata.obs[args.obs].dtype.name != "category":
    adata.obs[args.obs] = adata.obs[args.obs].astype("category")

if args.dimension is None:
    args.dimension = adata.obsm[args.embedding].shape[1]

if args.min_cluster_size <= 0:
    parser.error("--min-cluster-size must be a positive integer")

cluster_counts = adata.obs[args.obs].value_counts()
clusters = list(adata.obs[args.obs].cat.categories)
eligible_clusters = {
    cluster
    for cluster in clusters
    if int(cluster_counts.get(cluster, 0)) >= args.min_cluster_size
}
if not eligible_clusters:
    parser.error(
        "no cluster has at least "
        f"--min-cluster-size={args.min_cluster_size} cells"
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
    if cluster in selected_clusters and cluster not in eligible_clusters
]
if small_selected_clusters:
    parser.error(
        "cluster(s) smaller than "
        f"--min-cluster-size={args.min_cluster_size}: "
        + ", ".join(small_selected_clusters)
    )

unassigned_eligible_clusters = sorted(eligible_clusters - selected_clusters)
if unassigned_eligible_clusters:
    parser.error(
        "eligible cluster(s) not assigned to --centrality or --periphery: "
        + ", ".join(unassigned_eligible_clusters)
    )

std.print_task("estimating subclusters (method=KNNSC)")
knnsc = bt.sct.tl.KNNSC(
    n_neighbors=args.neighbors,
    use_rep=args.embedding,
    n_components=args.dimension,
    metric=args.metric,
)

std.print_info("computing k-nearest neighbors graph")
knnsc.fit(
    adata,
    obs=args.obs,
    min_cluster_size=args.min_cluster_size,
    n_jobs=args.jobs,
)

std.print_info("computing pairwise shortest paths between cells and barycenters")
std.print_warning("this may take some time.")
knnsc.compute_shortest_path_lengths(method=args.method, n_jobs=args.jobs)

std.print_info("estimating cluster-related cell manifolds")
macrostates = knnsc.predict(
    subcluster_size=args.size,
    key="macrostate",
    peripheral_clusters=args.periphery,
    central_clusters=args.centrality,
)
adata.obs["macrostate"] = macrostates

std.print_task(f"saving AnnData (file={std.format_path(args.outfile)})")
std.write_h5ad(adata, filename=args.outfile, compression="gzip")

if args.csv:
    std.print_task(f"saving KNNSC macrostates (file={std.format_path(args.csv)})")
    adata.obs["macrostate"].to_csv(args.csv, sep=",", index=True)
