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

import matplotlib.pyplot as plt

from networkx.classes.graph import Graph
from rpy2.rinterface import ListSexpVector

bt.sct.pl.set_default_params()

parser = argparse.ArgumentParser(
    prog="stream",
    description=(
        "Learn elastic principal graph, estimate pseudotime and compute macrostates "
        "using the STREAM framework.\n"
        "See Chen et al. (2019) <https://www.nature.com/articles/s41467-019-09670-4>."
    ),
    usage="python stream_macrostates.py <FILE> <FILE> --obs <LITERAL> [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
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
    help="output file storing pseudotime and stream macrostates (format: h5ad)",
)

parser.add_argument(
    "--pkl",
    dest="pkl",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="output file storing elastic principal graph (format: pkl)",
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
    "--use-rep",
    dest="use_rep",
    type=str,
    required=False,
    default="X_umap",
    metavar="LITERAL",
    help="embedding projection in adata.obsm used for computing elastic principal graph (default: X_umap)",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name in adata.obs referring to clusters (default: none)",
)

parser.add_argument(
    "--clustering",
    dest="clustering",
    type=str,
    required=False,
    choices=["kmeans", "ap", "sc"],
    default="kmeans",
    metavar="[kmeans | ap | sc]",
    help="clustering method used (K-means clustering, affinity propagation, spectral clustering) for seeding the initial elastic principal graph (default: kmeans)",
)

parser.add_argument(
    "--cluster-number",
    dest="cluster_number",
    type=int,
    required=False,
    default=5,
    metavar="INT",
    help="number of clusters for elastic principal graph (default: 5)",
)

parser.add_argument(
    "--alpha",
    dest="alpha_epg",
    type=float,
    required=False,
    default=0.01,
    metavar="FLOAT",
    help="alpha parameter used for computing elastic energy, penalizing spurious branching events (default: 0.01)",
)

parser.add_argument(
    "--mu",
    dest="mu_epg",
    type=float,
    required=False,
    default=0.05,
    metavar="FLOAT",
    help="mu parameter used for computing elastic energy, penalizing the deviation from harmonic embedding (default: 0.05)",
)

parser.add_argument(
    "--lambda",
    dest="lambda_epg",
    type=float,
    required=False,
    default=0.05,
    metavar="FLOAT",
    help="lambda parameter used for computing elastic energy, penalizing the total length of edges (default: 0.05)",
)

parser.add_argument(
    "--extend-epg",
    dest="extend_epg",
    required=False,
    action="store_true",
    help="extend leaves of the elastic principal graph by attaching new nodes",
)

parser.add_argument(
    "--extend-mode",
    dest="extend_mode",
    type=str,
    required=False,
    choices=["QuantDists", "QuantCentroid", "WeigthedCentroid"],
    default="QuantDists",
    metavar="[QuantDists | QuantCentroid | WeigthedCentroid]",
    help="mode used to extend leaves (used only if --extend-epg, default: QuantDists)",
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
    help="STREAM parameter used to extend leaves (used only if --extend-epg, default: 0.5)",
)

parser.add_argument(
    "--prune-epg",
    dest="prune_epg",
    required=False,
    action="store_true",
    help="prune elastic principal graph by filtering out trivial branches",
)

parser.add_argument(
    "--collapse-mode",
    dest="collapse_mode",
    type=str,
    required=False,
    choices=[
        "PointNumber",
        "PointNumber_Extrema",
        "PointNumber_Leaves",
        "EdgesNumber",
        "EdgesLength",
    ],
    default="PointNumber",
    metavar="[PointNumber | PointNumber_Extrema | PointNumber_Leaves | EdgesNumber | EdgesLength]",
    help="mode used to prune the graph (used only if --prune-epg, default: PointNumber)",
)

parser.add_argument(
    "--collapse-parameter",
    dest="collapse_parameter",
    type=float,
    required=False,
    default=5,
    metavar="FLOAT",
    help="STREAM parameter used to prune the graph (used only if --prune-epg, default: 5)",
)

parser.add_argument(
    "--size",
    dest="size",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="minimum number of cells per macrostate; smaller macrostates are extended to neighboring elastic principal graph nodes (default: None)",
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

embedding_label = (
    args.use_rep[2:].lower() if args.use_rep.startswith("X_") else args.use_rep.lower()
)

outpath = os.path.dirname(args.outfile)
os.makedirs(f"{outpath}/streamplot", exist_ok=True)

std.print_task(f"loading data from {str(args.infile)}")
adata = ad.read_h5ad(args.infile)
adata.uns["workdir"] = str(outpath)

adata.uns["dr"] = args.use_rep
adata.obsm["X_dr"] = bt.sct.tl.choose_representation(adata, use_rep=args.use_rep).copy()

adata.obs[args.obs] = adata.obs[args.obs].astype(object)

std.print_task("computing elastic principal graph")

std.print_info("initializing elastic principal graph")
with std.disable_print():
    st.seed_elastic_principal_graph(
        adata, clustering=args.clustering, n_clusters=args.cluster_number
    )

std.print_info("learning elastic principal graph")
with std.disable_print():
    st.elastic_principal_graph(
        adata,
        epg_alpha=args.alpha_epg,
        epg_mu=args.mu_epg,
        epg_lambda=args.lambda_epg,
        epg_n_processes=args.jobs,
    )

if args.extend_epg:
    std.print_info("extending leaves of elastic principal graph")
    with std.disable_print():
        st.extend_elastic_principal_graph(
            adata, epg_ext_mode=args.extend_mode, epg_ext_par=args.extend_parameter
        )
else:
    std.print_info("not extending leaves of elastic principal graph")

if args.prune_epg:
    std.print_info("pruning elastic principal graph by filtering out trivial branches")
    with std.disable_print():
        st.prune_elastic_principal_graph(
            adata,
            epg_collapse_mode=args.collapse_mode,
            epg_collapse_par=args.collapse_parameter,
            epg_n_processes=args.jobs,
        )
else:
    std.print_info(
        "not prunning elastic principal graph by filtering out trivial branches"
    )

std.print_task("retrieving stream-based clusters")

def get_stream_cluster(value):
    match = re.search(r"\d+", str(value))
    if match is None:
        raise ValueError(f"STREAM cluster label has no numeric id: {value}")
    return match.group()

adata.obs["kmeans"] = (
    adata.obs["kmeans"]
    .transform(get_stream_cluster)
    .astype("category")
)

epg_to_flat = dict()
for node, attributes in adata.uns["flat_tree"]._node.items():
    epg_to_flat[node] = attributes["label"]

adata.obs["macrostate"] = np.nan
adata.obs["macrostate"] = (
    adata.obs["macrostate"]
    .astype("category")
    .cat.add_categories(sorted(epg_to_flat.values()))
)
for node in epg_to_flat.keys():
    _true = adata.obs["node"] == node
    adata.obs["macrostate"][_true] = str(epg_to_flat[node])

if args.size is not None:
    flat_to_epg = dict((v, k) for k, v in epg_to_flat.items())
    extension = dict()
    size = adata.obs["macrostate"].value_counts()
    for i, v in size.items():
        if v < args.size:
            std.print_debug(
                f"macrostate {i} too small ({v}): extend to neighborhood nodes"
            )
            _true = adata.obs["node"].isin(list(adata.uns["epg"][flat_to_epg[i]]))
            adata.obs["macrostate"][_true] = str(i)

info_str = "macrostate size:"
for i, v in adata.obs["macrostate"].value_counts().sort_index().items():
    info_str += f" {i}: {v}; "
info_str = info_str[:-2]
std.print_info(info_str)

groups = set([args.obs]).union({"kmeans", "macrostate"})

std.print_task(f"plotting STREAM outputs in {os.path.relpath(outpath)}")
for group in groups:
    epg_plot = Path(f"{outpath}/epg_{group}.pdf")
    bt.sct.pl.embedding_plot(
        adata,
        obs=group,
        use_rep=args.use_rep,
        xlabel=r"$\mathrm{{{}_{{1}}}}$".format(embedding_label),
        ylabel=r"$\mathrm{{{}_{{2}}}}$".format(embedding_label),
        zlabel=r"$\mathrm{{{}_{{3}}}}$".format(embedding_label),
        figwidth=6,
        s=2,
        alpha=0.7,
        add_legend=True,
        lgd_params={
            "title": group,
            "ncol": 1,
            "markerscale": 5,
            "frameon": True,
            "edgecolor": bt.sct.pl.get_color("black"),
            "shadow": False,
        },
        text={"fontsize": 14, "fontweight": "extra bold"},
        add_graph=True,
        add_labels_to_graph=True,
        n_components=3 if adata.obsm["X_dr"].shape[1] > 2 else 2,
        background_visible=False,
        outfile=epg_plot,
    )

branches_plot = Path(f"{outpath}/branches.pdf")
st.plot_branches(adata, show_text=True, save_fig=branches_plot)

for root in adata.obs["macrostate"].cat.categories:
    st.plot_stream(
        adata,
        root=root,
        color=[args.obs],
        log_scale=False,
        factor_zoomin=100,
        save_fig=False,
    )
    plt.title("")
    os.makedirs(Path(f"{outpath}/streamplot/{root}"), exist_ok=True)
    plt.savefig(
        Path(f"{outpath}/streamplot/{root}/density_streamplot.pdf"), bbox_inches="tight"
    )
    plt.close()
    st.plot_stream_sc(
        adata,
        root=root,
        color=[args.obs],
        dist_scale=0.3,
        show_graph=True,
        show_text=True,
        save_fig=False,
    )

    plt.savefig(
        Path(f"{outpath}/streamplot/{root}/sc_streamplot.pdf"), bbox_inches="tight"
    )
    plt.close()

if args.pkl:
    std.print_task(f"saving STREAM object in {str(args.pkl)}")
    with std.disable_print():
        st.write(adata, file_name=args.pkl)

std.print_task(f"saving AnnData object in {str(args.outfile)}")
del adata.uns["workdir"]
for key in list(adata.obs.keys()):
    if isinstance(adata.obs[key][0], tuple):
        del adata.obs[key]
for key in list(adata.uns.keys()):
    if isinstance(adata.uns[key], (tuple, Path, Graph, ListSexpVector)):
        del adata.uns[key]
    if key.startswith("stream_S"):
        del adata.uns[key]
adata.write_h5ad(filename=args.outfile, compression="gzip")

if args.csv:
    std.print_task(f"saving stream macrostates in {str(args.csv)}")
    adata.obs["macrostate"].to_csv(args.csv, sep=",", index=True)
