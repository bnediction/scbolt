#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import anndata as ad
import bonesistools as bt

import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(
    prog="knnbs",
    description=
    """
    Compute k-nearest neighbors-based subclusters.
    """,
    usage="python scbridge_macrostates.py <FILE> <PATH> [-- center <LITERAL...>] [-- extremity <LITERAL...>] [<args>]"
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="preprocessed input file (h5ad format)"
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="preprocessed output file storing 'macrostates' in adata.obs (h5ad format)"
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=False,
    default="cluster",
    metavar="LITERAL",
    help="column name in adata.obs distinguishing clusters (default: cluster)"
)

parser.add_argument(
    "--obsm",
    dest="obsm",
    type=str,
    required=False,
    default="X_umap",
    metavar="LITERAL",
    help="embedding space used in adata.obsm (default: X_umap)"
)

parser.add_argument(
    "--dimension",
    dest="dimension",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="number of components taken into account in adata.obsm[`obsm`] (default: maximum)"
)

parser.add_argument(
    "--size",
    dest="size",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of cells in each macrostate (default: 50)"
)

s = "data/rna/ctrl/clustering/clusters/annotation.h5ad /tmp/results --obs leiden --obsm X_umap"

args = parser.parse_args(s.split())

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

adata = ad.read_h5ad(args.infile)

if args.dimension is None:
    args.dimension = adata.obsm[args.obsm].shape[1]

n_components = None
metric = "euclidean"
n_jobs = 10
metric_kwds = None
n_neighbors = 10

### Two methods:

# distances = compute_distances(adata, n_pcs, use_rep, metric, n_jobs)
# sample_range = np.arange(distances.shape[0])[:, None]
# sorted_indices = np.argpartition(distances, axis=1)
# knn_indices = sorted_indices[:, :n_neighbors]
# weights = distances[sample_range, knn_indices]
# weighted_adjacency_matrix = np.zeros_like(distances)
# weighted_adjacency_matrix[knn_indices]
# for i, _ in enumerate(distances):
#     row_index = knn_indices[i,:]
#     weighted_adjacency_matrix[i, row_index] = weights[i,:]
# neighbors_graph = nx.from_numpy_array(weighted_adjacency_matrix)
# neighbors_graph[0]

knnbs = bt.sct.tl.Knnbs(
    n_neighbors=10,
    use_rep=args.obsm,
    n_components=n_components,
    metric=metric 
)

knnbs.fit(
    adata,
    obs=args.obs,
    n_jobs=n_jobs
)

knnbs.shortest_path_lengths(
    method="dijkstra",
    n_jobs=n_jobs
)

adata.obs["macrostates"] = knnbs.knnbs(
    size=args.size,
    key="knnbs",
    subclusters_maximizing_distances=["gran2", "prom2", "prom3", "rep"],
    subclusters_minimizing_distances=["prom1"]
)

# find_cells_maximizing_distances_to_other_barycenters
# find_farther_cell_manifolds_to_other_barycenters
# subclusters_maximizing_distances
# find_closest_cells_to_self_barycenter

fig, _ = bt.sct.pl.embedding_plot(
    adata,
    obs="macrostates",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=True,
    figwidth=6,
    s=4,
    alpha=1,
    lgd_params={
        "title":"macrostates",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":bt.sct.pl.get_color("black"),
        "shadow":False
    },
    n_components = 3 if adata.obsm["X_umap"].shape[1] > 2 else 2,
    background_visible=False
)
plt.show()
plt.savefig(Path(f"{os.path.dirname(args.outfile)}/macrostates.pdf"))
