#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse, cli
from pathlib import Path

import anndata as ad
import bonesistools as bt

parser = argparse.ArgumentParser(
    prog="knnbs",
    description="""
    Compute cell manifolds using k-nearest neighbors-based subclusters (knnbs) algorithm. \
    Compute the k-nearest neighbors-based graph using an embedding space, \
    compute shortest path lengths in the graph and then search for cluster related-cell manifolds \
    using knnbs algorithm. The subclusters can be computed following two strategies: \
    (1) a centrality-based strategy, minimizing distances to the cluster's own barycenter \
    and (2) a periphery-based strategy, maximizing distances to other clusters' barycenters
    """,
    usage="python knnbs_macrostates.py <FILE> <FILE> [--csv <FILE>] --obs <LITERAL> [--centrality <LITERAL...>] [--periphery <LITERAL...>] [<args>]",
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
    help="output file storing knnbs macrostates (format: h5ad)",
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
    default="umap",
    choices=["pca", "umap", "tsne"],
    metavar="[pca|umap|tsne]",
    help="embedding projection used when calculating pairwise distances (default: umap)",
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
    help="number of closest neighbors for computing k-nearest neighbors graph (default: 20)",
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
    metavar="[dijkstra|bellman-ford]",
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
    help="number of allocated processors",
)

args = parser.parse_args()

if args.embedding == "pca":
    embedding = "X_pca"
elif args.embedding == "umap":
    embedding = "X_umap"
elif args.embedding == "tsne":
    embedding = "X_tsne"

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

std.print_task(f"loading data from {str(args.infile)}")
adata = ad.read_h5ad(args.infile)

if adata.obs[args.obs].dtype.name != "category":
    adata.obs[args.obs] = adata.obs[args.obs].astype("category")

if args.dimension is None:
    args.dimension = adata.obsm[embedding].shape[1]

if args.periphery:
    for cluster in args.periphery:
        if cluster not in adata.obs[args.obs].cat.categories:
            raise argparse.ArgumentError(
                None,
                f"cluster {cluster} in argument --periphery not found in 'adata.obs[{args.obs}]'",
            )
if args.centrality:
    for cluster in args.centrality:
        if cluster not in adata.obs[args.obs].cat.categories:
            raise argparse.ArgumentError(
                None,
                f"cluster {cluster} in argument --centrality not found in 'adata.obs[{args.obs}]'",
            )

std.print_task("estimating KNNbs subclusters")
knnbs = bt.sct.tl.Knnbs(
    n_neighbors=args.neighbors,
    use_rep=embedding,
    n_components=args.dimension,
    metric=args.metric,
)

std.print_info("computing k-nearest neighbors graph")
knnbs.fit(adata, obs=args.obs, n_jobs=args.jobs)

std.print_info("computing pairwise shortest paths between cells and barycenters")
std.print_warning("this may take some time.")
knnbs.shortest_path_lengths(method=args.method, n_jobs=args.jobs)

std.print_info("estimating cluster-related cell manifolds")
adata.obs["macrostate"] = knnbs.knnbs(
    size=args.size,
    key="macrostate",
    subclusters_maximizing_distances=args.periphery,
    subclusters_minimizing_distances=args.centrality,
)

std.print_task(f"saving AnnData object in {str(args.outfile)}")
adata.write_h5ad(filename=args.outfile, compression="gzip")

if args.csv:
    std.print_task(f"saving KNNbs macrostates in {str(args.csv)}")
    adata.obs["macrostate"].to_csv(args.csv, sep=",", index=True)
