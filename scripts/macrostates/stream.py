#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, std, re
import argparse, cli
from pathlib import Path

import numpy as np

import anndata as ad
import stream as st
import bonesistools as bt

from networkx.classes.graph import Graph
from rpy2.rinterface import ListSexpVector

import matplotlib.pyplot as plt

bt.sct.pl.set_default_params()

parser = argparse.ArgumentParser(
    prog="stream pseudotime",
    description=
    """
    Learn elastic principal graph, estimate pseudotime and compute macrostates using STREAM framework. \
    See Chen et al. (2019) <https://www.nature.com/articles/s41467-019-09670-4>.
    """,
    usage="python stream_pseudotime.py <FILE> <FILE> --obs <LITERAL> [<args>]"
)

parser.add_argument(
    dest="infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing counts (format: h5ad)"
)

parser.add_argument(
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file storing pseudotime and stream macrostates (format: h5ad)"
)

parser.add_argument(
    "--pkl",
    dest="pkl",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output file storing elastic principal graph (format: pkl)"
)

parser.add_argument(
    "--csv",
    dest="csv",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output file storing macrostates (format: csv)"
)

parser.add_argument(
    "--embedding",
    dest="embedding",
    type=str,
    required=False,
    default="umap",
    choices=["umap","tsne"],
    metavar="[umap|tsne]",
    help="embedding projection (default: umap)"
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in adata.obs referring to clusters (default: none)"
)

parser.add_argument(
    "--cluster-number",
    dest="cluster_number",
    type=int,
    required=False,
    default=5,
    metavar="INT",
    help="number of clusters for elastic principal graph (default: 5)"
)

parser.add_argument(
    "--lambda",
    dest="lambda_epg",
    type=float,
    required=False,
    default=0.05,
    metavar="FLOAT",
    help="lambda parameter used for computing the elastic energy (default: 0.05)"
)

parser.add_argument(
    "--mu",
    dest="mu_epg",
    type=float,
    required=False,
    default=0.05,
    metavar="FLOAT",
    help="mu parameter used for computing the elastic energy (default: 0.05)"
)

parser.add_argument(
    "--alpha",
    dest="alpha_epg",
    type=float,
    required=False,
    default=0.01,
    metavar="FLOAT",
    help="alpha parameter of the penalized elastic energy (default: 0.01)"
)

parser.add_argument(
    "--extend-epg",
    dest="extend_epg",
    required=False,
    action="store_true",
    help="extend leaves of elastic principal graph by attaching them new nodes"
)

parser.add_argument(
    "--extend-mode",
    dest="extend_mode",
    type=str,
    required=False,
    choices=["QuantDists","QuantCentroid","WeigthedCentroid"],
    default="QuantDists",
    metavar="[QuantDists | QuantCentroid | WeigthedCentroid]",
    help="mode used for extending the leaves (used only if --extend, default: QuantDists)"
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
    help="stream parameter used for extending the leaves (used only if --extend, default: 0.5)"
)

parser.add_argument(
    "--prune-epg",
    dest="prune_epg",
    required=False,
    action="store_true",
    help="prune elastic principal graph by filtering out trivial branches"
)

parser.add_argument(
    "--collapse-mode",
    dest="collapse_mode",
    type=str,
    required=False,
    choices=["PointNumber", "PointNumber_Extrema", "PointNumber_Leaves", "EdgesNumber", "EdgesLength"],
    default="PointNumber",
    metavar="[PointNumber | PointNumber_Extrema | PointNumber_Leaves | EdgesNumber | EdgesLength]",
    help="mode used for prunning the graph (used only if --prune-graph, default: PointNumber)"
)

parser.add_argument(
    "--collapse-parameter",
    dest="collapse_parameter",
    type=float,
    required=False,
    default=5,
    metavar="FLOAT",
    help="stream parameter used for prunning the graph (used only if --prune-graph, default: 5)"
)

parser.add_argument(
    "--jobs",
    dest="jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of allocated processors"
)

args = parser.parse_args()

embedding_label = "UMAP" if args.embedding == "umap" else "t-SNE"

outpath = os.path.dirname(args.outfile)
if not Path(f"{outpath}/streamplot").exists():
    os.makedirs(f"{outpath}/streamplot")

std.print_task(f"loading file {str(args.infile)}")
adata = ad.read_h5ad(args.infile)
adata.uns["workdir"] = str(outpath)

if args.embedding == "umap":
    adata.uns["dr"] = "X_umap"
    adata.obsm["X_dr"] = adata.obsm["X_umap"].copy()
else:
    adata.uns["dr"] = "X_tsne"
    adata.obsm["X_dr"] = adata.obsm["X_tsne"].copy()

adata.obs[args.obs] = adata.obs[args.obs].astype(object)

std.print_task("computing elastic principal graph")

std.print_debug("initializing elastic principal graph")
with std.disable_print():
    st.seed_elastic_principal_graph(
        adata,
        clustering="kmeans",
        n_clusters=args.cluster_number
    )

std.print_info("learning elastic principal graph")
with std.disable_print():
    st.elastic_principal_graph(
        adata,
        epg_alpha=args.alpha_epg,
        epg_mu=args.mu_epg,
        epg_lambda=args.lambda_epg,
        epg_n_processes=args.jobs
    )

if args.extend_epg:
    std.print_info("extending leaves of elastic principal graph")
    with std.disable_print():
        st.extend_elastic_principal_graph(
            adata,
            epg_ext_mode=args.extend_mode,
            epg_ext_par=args.extend_parameter
        )
else:
    std.print_info("not extending leaves of elastic principal graph")

if args.prune_epg:
    std.print_info("prunning elastic principal graph by filtering out trivial branches")
    with std.disable_print():
        st.prune_elastic_principal_graph(
            adata,
            epg_collapse_mode = args.collapse_mode,
            epg_collapse_par = args.collapse_parameter,
            epg_n_processes=args.n_jobs
        )
else:
    std.print_info("not prunning elastic principal graph by filtering out trivial branches")

std.print_debug("retrieving stream-based clusters")

adata.obs["kmeans"] = adata.obs["kmeans"].transform(lambda x: re.search(r"\d+", x).group()).astype("category")

nodes_mapping = dict()
for node, attributes in adata.uns["flat_tree"]._node.items():
    label = re.search(r"\d+", attributes["label"]).group()
    adata.uns["flat_tree"].nodes[node]["label"] = label
    nodes_mapping[node] = label

adata.obs["macrostates"] = np.nan
adata.obs["macrostates"] = adata.obs["macrostates"].astype("category").cat.add_categories(sorted(nodes_mapping.values()))
for node in nodes_mapping.keys():
    _true = adata.obs["node"] == node
    adata.obs["macrostates"][_true] = str(nodes_mapping[node])
adata.obs["macrostates"] = adata.obs["macrostates"].astype("category")

for node in adata.obs["macrostates"].cat.categories:
    adata.obs[f"{node}_pseudotime"] = adata.obs[f"S{node}_pseudotime"]
    del adata.obs[f"S{node}_pseudotime"]

groups = set([args.obs]).union({"kmeans", "macrostates"})

for group in groups:
    std.print_task(f"plotting elastic principal graph in {embedding_label.lower()} space for cluster '{group}'")
    bt.sct.pl.embedding_plot(
        adata,
        obs=group,
        use_rep="X_dr",
        xlabel=r"$\mathrm{{{}_{{1}}}}$".format(embedding_label),
        ylabel=r"$\mathrm{{{}_{{2}}}}$".format(embedding_label),
        zlabel=r"$\mathrm{{{}_{{3}}}}$".format(embedding_label),
        figwidth=6,
        s=2,
        alpha=0.7,
        add_legend=True,
        lgd_params={
            "title":group,
            "ncol":1,
            "markerscale":5,
            "frameon":True,
            "edgecolor":bt.sct.pl.get_color("black"),
            "shadow":False
        },
        text={
            "fontsize":14,
            "fontweight":"extra bold"
        },
        add_graph=True,
        add_labels_to_graph=True,
        n_components=3 if adata.obsm["X_dr"].shape[1] > 2 else 2,
        background_visible=False,
        outfile=Path(f"{outpath}/{embedding_label}_epg_{group}.pdf")
    )

std.print_task("plotting trajectories with respect to pseudotime at density level")
for root in adata.obs["macrostates"].cat.categories:
    st.plot_stream(
        adata,
        root=root,
        color=[args.obs],
        log_scale=False,
        factor_zoomin=100,
        save_fig=False
    )
    plt.gca().get_legend().set_title(args.obs)
    plt.savefig(Path(f"{outpath}/streamplot/streamplot_{group}_root{root}.pdf"))

if args.pkl:
    std.print_task(f"saving pkl-formatted data in {str(args.pkl)}")
    with std.disable_print():
        st.write(
            adata,
            file_name=args.pkl
        )

std.print_task(f"saving h5ad-formatted data in {str(args.outfile)}")
del adata.uns["workdir"]
for key in list(adata.obs.keys()):
    if isinstance (adata.obs[key][0], tuple):
        del adata.obs[key]
for key in list(adata.uns.keys()):
    if isinstance(adata.uns[key], (tuple, Path, Graph, ListSexpVector)):
        del adata.uns[key]
    if key.startswith("stream_S"):
        del adata.uns[key]
adata.write_h5ad(
    filename=args.outfile,
    compression="gzip"
)

if args.csv:
    std.print_task(f"saving stream macrostates in {str(args.csv)}")
    adata.obs["macrostates"].to_csv(
        args.csv,
        sep=",",
        index=True
    )
