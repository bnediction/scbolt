#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std
import argparse, cli
import re
import pickle
from pathlib import Path

import anndata as ad
import stream as st
import bonesistools as bt

from numpy import nan
from scipy.sparse import issparse
from pandas.api.types import is_float_dtype
from networkx.classes.graph import Graph
from rpy2.rinterface import ListSexpVector

import matplotlib.pyplot as plt

bt.adt.pl.set_default_params()

parser = argparse.ArgumentParser(
    prog="pseudotime computation",
    description="""compute pseudotime using STREAM method \
    (see Chen et al. (2019): <https://www.nature.com/articles/s41467-019-09670-4>).""",
    usage=""""python stream_pseudotime.py [-h] <FILE> <PATH> [<args>]"""
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="counting file (h5ad format)"
)

parser.add_argument(
    "outpath",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "--st", "--save-tables",
    dest="save_tables",
    action=cli.Store_boolean,
    required=False,
    default=True,
    help="save the anndata object (default: yes)"
)

parser.add_argument(
    "-e", "--extension",
    dest="extension",
    type=str,
    required=False,
    choices=["h5ad", "pkl", "both"],
    default="h5ad",
    metavar="[h5ad | pkl | both]",
    help="""file extension of saved anndata object (default: h5ad).
    if `both` is specified, save both anndata object in h5ad and pkl format."""
)

parser.add_argument(
    "-s", "--use-stream-embedding",
    dest="use_stream_embedding",
    required=False,
    action="store_true",
    help="""compute embedding components using classic stream data preprocessing.
    Trajectories are then inferred using the output array given by stream embedding.
    Cannot be used with --use-stream-embedding argument.
    If neither --use-stream-embedding argument nor --obsm argument is used,
    searches pre-computed embedding components for inferring trajectories:
    .obsm[`X_umap`] and .obsm[`X_scanorama`]."""
)

parser.add_argument(
    "-m", "--method",
    dest="method",
    type=str,
    required=False,
    choices=["se", "mlle", "umap", "pca"],
    metavar="[se | mlle | umap | pca]",
    help="method used for dimension reduction (used only if --use-stream-embedding)"
)

parser.add_argument(
    "--obsm",
    dest="obsm",
    required=False,
    default=None,
    metavar="LITERAL",
    help="""ndarray name stored in .obsm[`obsm`] used for trajectory inference.
    Cannot be used with --use-stream-embedding argument.
    If neither --obsm argument nor --use-stream-embedding argument is used,
    searches pre-computed embedding components for inferring trajectories:
    .obsm[`X_umap`] and .obsm[`X_scanorama`]."""
)

parser.add_argument(
    "-l", "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used for dimension reduction (used only if --use-stream-embedding)"
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    required=False,
    action="store_true",
    help="select the most variable genes for dimension reduction (used only if --use-stream-embedding)"
)

parser.add_argument(
    "-d", "--dimensions",
    dest="n_dimensions",
    type=int,
    required=False,
    default=3,
    metavar="INT",
    help="number of components to keep (used only if --use-stream-embedding, default: 3)"
)

parser.add_argument(
    "-n", "--cluster-number",
    dest="n_clusters",
    type=int,
    required=False,
    default=5,
    metavar="INT",
    help="number of clusters to compute for elastic principal graph (default: 5)"
)

parser.add_argument(
    "-g", "--groups",
    dest="groups",
    type=str,
    required=False,
    nargs="+",
    metavar="LITERAL",
    help="clusters retrieving from adata.obs[`cluster`] used for cluster-related trajectory plotting"
)

parser.add_argument(
    "--lambda", "--epg-lambda",
    dest="epg_lambda",
    type=float,
    required=False,
    default=0.05,
    metavar="FLOAT",
    help="lambda parameter used to compute the elastic energy (default: 0.05)"
)

parser.add_argument(
    "--mu", "--epg-mu",
    dest="epg_mu",
    type=float,
    required=False,
    default=0.05,
    metavar="FLOAT",
    help="mu parameter used to compute the elastic energy (default: 0.05)"
)

parser.add_argument(
    "--alpha", "--epg-alpha",
    dest="epg_alpha",
    type=float,
    required=False,
    default=0.01,
    metavar="FLOAT",
    help="alpha parameter of the penalized elastic energy (default: 0.01)"
)

parser.add_argument(
    "--extend-leaf-nodes",
    dest="extend_leaf_nodes",
    required=False,
    action="store_true",
    help="attach new node to each leaf node in order to connect the border of data point cloud to nodes"
)

parser.add_argument(
    "--extend-mode",
    dest="extend_mode",
    type=str,
    required=False,
    choices=["QuantDists","QuantCentroid","WeigthedCentroid"],
    default="QuantDists",
    metavar="[QuantDists | QuantCentroid | WeigthedCentroid]",
    help="mode used to extend the leaves (used only if --extend-leaf-nodes, default: QuantDists)"
)

parser.add_argument(
    "--extend-parameter",
    dest="extend_parameter",
    type=float,
    action=cli.Range,
    min=0,
    max=1,
    required=False,
    default=0.5,
    help="parameter value used to extend the leaves (used only if --extend-leaf-nodes, default: 0.5)"
)

parser.add_argument(
    "--prune-graph",
    dest="prune_graph",
    required=False,
    action="store_true",
    help="Prune the learnt elastic principal graph by filtering out trivial branches"
)

parser.add_argument(
    "--collapse-mode",
    dest="collapse_mode",
    type=str,
    required=False,
    choices=["PointNumber", "PointNumber_Extrema", "PointNumber_Leaves", "EdgesNumber", "EdgesLength"],
    default="PointNumber",
    metavar="[PointNumber | PointNumber_Extrema | PointNumber_Leaves | EdgesNumber | EdgesLength]",
    help="mode used to prune the graph (used only if --prune-graph, default: PointNumber)"
)

parser.add_argument(
    "--collapse-parameter",
    dest="collapse_parameter",
    type=float,
    required=False,
    default=5,
    metavar="FLOAT",
    help="parameter value used to prune the graph (used only if --prune-graph, default: 5)"
)

parser.add_argument(
    "--add-legend",
    dest="legend",
    required=False,
    action="store_true",
    help="add legend to figures"
)

parser.add_argument(
    "--add-graph",
    dest="graph",
    required=False,
    action="store_true",
    help="add elastic principal graph to figures"
)

parser.add_argument(
    "--plot-3d",
    dest="plot_3d",
    required=False,
    action="store_true",
    help="plot figures in three dimensions"
)

parser.add_argument(
    "-j", "--jobs",
    dest="n_jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of parallel jobs to run"
)

args = parser.parse_args()

if not args.outpath.exists():
    os.makedirs(args.outpath)

groups = set(args.groups)

std.print_task("data loading")

adata = ad.read_h5ad(args.infile)
adata.obs_names_make_unique()
adata.uns["workdir"] = str(args.outpath)

if args.use_stream_embedding is True and args.obsm is not None:
    raise argparse.ArgumentError("--use-stream-embedding and --obsm arguments cannot be used simultaneously.")
elif args.use_stream_embedding is True:
    std.print_task("preprocessing for stream")
    with std.disable_print():
        adata.X = adata.layers[args.layer].toarray() if issparse(adata.layers[args.layer]) else adata.layers[args.layer]
        if args.hvg:
            st.select_variable_genes(
                adata,
                loess_frac=0.02
            )
        st.select_top_principal_components(
            adata,
            first_pc=True,
            n_pc=15,
            feature="var_genes" if args.hvg else None
        )
        st.dimension_reduction(
            adata,
            method=args.method,
            feature="top_pcs",
            n_components=args.n_dimensions,
            n_neighbors=50,
            n_jobs=args.jobs
        )
        adata.uns["dr"] = f"{args.method}"
else:
    std.print_info("no preprocessing for stream (use previous results)")
    if args.obsm:
        adata.uns["dr"] = args.obsm
    if "X_umap" in adata.obsm.keys():
        adata.uns["dr"] = "X_umap"
    elif "X_scanorama" in adata.obsm.keys():
        adata.uns["dr"] = "X_scanorama"
    else:
        raise ValueError("Integrated components (`X_umap` or `X_scanorama`) in adata.obsm not found.")
    adata.obsm["X_dr"] = adata.obsm[adata.uns["dr"]].copy()

for group in groups:
    try:
        adata.obs[group] = adata.obs[group].astype(object)
    except:
        pass

std.print_task("elastic principal graph computation")

with std.disable_print():
    st.seed_elastic_principal_graph(
        adata,
        clustering="kmeans",
        n_clusters=args.n_clusters
    )
    st.elastic_principal_graph(
        adata,
        epg_alpha=args.epg_alpha,
        epg_mu=args.epg_mu,
        epg_lambda=args.epg_lambda
    )
    if args.extend_leaf_nodes is True:
        st.extend_elastic_principal_graph(
            adata,
            epg_ext_mode=args.extend_mode,
            epg_ext_par=args.extend_parameter
        )
    if args.prune_graph is True:
        st.prune_elastic_principal_graph(
            adata,
            epg_collapse_mode = args.collapse_mode,
            epg_collapse_par = args.collapse_parameter,
            epg_n_processes=args.n_jobs
        )

adata.obs["kmeans"] = adata.obs["kmeans"].transform(lambda x: re.search(r"\d+", x).group())

adata.obs["macrostates"] = nan
adata.obs["macrostates"] = adata.obs["macrostates"].astype(str)

nodes_mapping = dict()
for node, attributes in adata.uns["flat_tree"]._node.items():
    _label = re.search(r"\d+", attributes["label"]).group()
    adata.uns["flat_tree"].nodes[node]["label"] = _label
    nodes_mapping[node] = _label

for node in nodes_mapping.keys():
    _true = adata.obs["node"] == node
    adata.obs["macrostates"][_true] = str(nodes_mapping[node])

groups = groups.union({"kmeans", "macrostates"})

std.print_task("trajectory plotting")

for _group in groups:
    fig, ax = bt.adt.pl.embedding_plot(
        adata,
        obs=_group,
        obsm=adata.uns["dr"],
        colors=[bt.adt.pl.get_color("blue")]*(len(nodes_mapping)) + [bt.adt.pl.get_color("lightgray")] if _group == "macrostates" else None,
        xlabel=r"$\mathrm{UMAP_{1}}$" if adata.uns["dr"] == "X_umap" else r"$\mathrm{x_{1}^{\mathrm{scanorama}}}$",
        ylabel=r"$\mathrm{UMAP_{2}}$" if adata.uns["dr"] == "X_umap" else r"$\mathrm{x_{2}^{\mathrm{scanorama}}}$",
        zlabel=r"$\mathrm{UMAP_{3}}$" if adata.uns["dr"] == "X_umap" else r"$\mathrm{x_{3}^{\mathrm{scanorama}}}$",
        add_graph=args.graph,
        add_labels_to_graph=True if not is_float_dtype(adata.obs[_group]) else False,
        add_legend=args.legend if _group != "macrostates" else False,
        figwidth=6 if args.legend else 5,
        s=2,
        alpha=0.4 if (args.plot_3d and not is_float_dtype(adata.obs[_group])) else 0.7,
        lgd_params={
            "title":"macrostates" if _group != "condition" else "conditions",
            "ncol":1,
            "markerscale":5,
            "frameon":True,
            "shadow":False
        } if not is_float_dtype(adata.obs[_group]) else None,
        text={
            "fontsize":14,
            "fontweight":"extra bold"
        },
        n_components = 3 if args.plot_3d is True else 2,
        background_visible=False
    )
    bt.adt.pl.set_default_axis(ax)
    plt.savefig(f"{args.outpath}/{_group}_{adata.uns['dr'].split('_')[-1].lower()}_trajectory_plot")
    if args.plot_3d is True:
        pickle.dump(fig, open(Path(f"{args.outpath}/{_group}_{adata.uns['dr'].split('_')[-1].lower()}_trajectory_plot.pkl"), "wb"))
    else:
        pass

if args.save_tables:
    std.print_task("data saving")
    with std.disable_print():
        if args.extension == "pkl" or args.extension == "both":
            st.write(adata, file_name=f"{args.outpath}/stream.h5ad.pkl")
        if args.extension == "h5ad" or args.extension == "both":
            del adata.uns["workdir"]
            for key in list(adata.obs.keys()):
                if isinstance (adata.obs[key][0], tuple):
                    del adata.obs[key]
            for key in list(adata.uns.keys()):
                if isinstance(adata.uns[key], (tuple, Path, Graph, ListSexpVector)):
                    del adata.uns[key]
                if key.startswith("stream_S"):
                    del adata.uns[key]
            adata.write_h5ad(filename=f"{args.outpath}/stream.h5ad", compression="gzip")
else:
    std.print_info("no data saving")