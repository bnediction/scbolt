#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
import pickle
from pathlib import Path
from utils.argtype import Store_prefix
from utils.stdout import disable_print, Section

import pandas as pd
import anndata as ad, anndatatools as adt, stream as st

import networkx as nx

import matplotlib.pyplot as plt
from anndatatools.plotting import color

parser = argparse.ArgumentParser(
    prog="trajectory inference of sc-RNAseq data",
    description="""From sc-RNAseq data recorded in hdf5 pickle format with pre-computed stream pseudotime,
    compute cell phenotype trajectories based on STREAM method \
    (see Chen et al. (2019): <https://www.nature.com/articles/s41467-019-09670-4>).""",
    usage=""""python trajectories.py [-h] -i <path> -r <int> [<args>]"""
)

parser.add_argument(
    "-i", "--infile",
    dest="infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="path to .h5ad file (including file)"
)

parser.add_argument(
    "-o", "--outpath",
    dest="outpath",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=Path("./trajectories").resolve(),
    metavar="PATH",
    help="output path (default: ./trajectories)"
)

parser.add_argument(
    "-p", "--prefix",
    dest="prefix",
    action=Store_prefix,
    required=False,
    default="",
    metavar="LITERAL",
    help="prefix for each saving file"
)

parser.add_argument(
    "-r", "--root",
    dest="root",
    type=int,
    required=True,
    metavar="INT",
    help="root of the elastic principal graph"
)

parser.add_argument(
    "--obsm",
    dest="obsm",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="embedding component used"
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
    "--add-text",
    dest="text",
    required=False,
    action="store_true",
    help="add node labels to figures"
)

parser.add_argument(
    "--plot-3d",
    dest="plot_3d",
    required=False,
    action="store_true",
    help="plot figures in three dimensions"
)


s = """--infile data/rna/stream/pseudotime/tables/pseudotime.h5ad.pkl --outpath data/rna/stream/trajectories --root 4
--group condition leiden kmeans node_clusters --add-legend --add-graph --plot-3d"""
args = parser.parse_args(s.split())

# args = parser.parse_args()

section = Section()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")
args.root=f"S{args.root}"

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

groups = set(args.groups).union([f"{args.root}_pseudotime"])

print("Loading data...")

with disable_print():
    adata = st.read(str(args.infile), file_format="pkl", workdir=args.outpath)

if args.obsm is None and "dr" not in adata.uns:
    raise ValueError("neither `obsm` argument is specified nor adata.uns[`dr`] exists.")
else:
    dr = args.obsm if args.obsm is not None else adata.uns["dr"]

if dr not in adata.obsm:
    raise ValueError("Integrated components {dr} in adata.obsm not found.")

print("Plotting trajectories...")

section("trajectory plot")

for _group in groups:
    fig, ax = adt.pl.embedding_plot(
        adata,
        obs=_group,
        obsm=adata.uns["dr"],
        colors=[color.blue] * (len(adata.obs["node_clusters"].unique()) - 1) + [color.lightgray] if _group == "node_clusters" else None,
        xlabel=r"$\mathrm{UMAP_{1}}$" if adata.uns["dr"] == "X_umap" else r"$\mathrm{x_{1}^{\mathrm{scanorama}}}$",
        ylabel=r"$\mathrm{UMAP_{2}}$" if adata.uns["dr"] == "X_umap" else r"$\mathrm{x_{2}^{\mathrm{scanorama}}}$",
        zlabel=r"$\mathrm{UMAP_{3}}$" if adata.uns["dr"] == "X_umap" else r"$\mathrm{x_{3}^{\mathrm{scanorama}}}$",
        add_graph=args.graph,
        add_text=args.text,
        add_legend=args.legend if _group != "node_clusters" else False,
        figwidth=6 if args.legend else 5,
        s=2,
        alpha=0.7,
        lgd_params={
            "title":"clusters" if _group != "condition" else "conditions",
            "labels":[string.replace("cluster ","") for string in sorted(adata.obs[_group].unique())],
            "ncol":1,
            "markerscale":5,
            "frameon":True,
            "shadow":False
        } if not pd.api.types.is_float_dtype(adata.obs[_group]) else None,
        text={
            "fontsize":14,
            "fontweight":"extra bold"
        },
        n_components = 3 if args.plot_3d is True else 2,
        background_visible=False
    )
    adt.pl.set_default(ax)
    if "pseudotime" not in _group:
        plt.savefig(f"{fig_outpath}/{args.prefix}{_group}_{dr.split('_')[-1].lower()}_trajectory_plot")
    else:
        plt.savefig(f"{fig_outpath}/{args.prefix}pseudotime_{dr.split('_')[-1].lower()}_trajectory_plot")
    if args.plot_3d is True and "pseudotime" not in _group:
        pickle.dump(fig, open(Path(f"{fig_outpath}/{args.prefix}{_group}_{dr.split('_')[-1].lower()}_trajectory_plot.pkl"), "wb"))
    elif args.plot_3d is True:
        pickle.dump(fig, open(Path(f"{fig_outpath}/{args.prefix}pseudotime_{dr.split('_')[-1].lower()}_trajectory_plot.pkl"), "wb"))
    else:
        pass

section("stream plot")

st.plot_stream(
    adata,
    root=args.root,
    color=[f"{args.root}_pseudotime"],
    log_scale=False,
    factor_zoomin=100,
    save_fig=False,
)
fig, ax = (plt.gcf(), plt.gca())
adt.pl.set_default(ax)
ax.tick_params(axis="x", which="major", pad=2)
ax.images[-1].colorbar.remove()
plt.savefig(f"{fig_outpath}/{args.prefix}pseudotime_stream_plot")

for _group in groups.difference([f"{args.root}_pseudotime"]):
    colors=color.COLORS[0:len(adata.obs["node_clusters"].unique())-1] + [color.lightgray] if _group == "node_clusters" else color.COLORS
    st.plot_stream(
        adata,
        root=args.root,
        color=[_group],
        log_scale=False,
        factor_zoomin=100,
        save_fig=False,
    )
    fig, ax = (plt.gcf(), plt.gca())
    ax.tick_params(axis="x", which="major", pad=2)
    adt.pl.set_default(ax)
    for idx, patch in enumerate(ax.patches):
        if idx == len(ax.patches)-1:
            continue
        else:
            patch.set_color(colors[idx])
            patch.set_alpha(1)
    ax.legend(
        [string.replace("cluster ","") for string in sorted(adata.obs[_group].unique())],
        bbox_to_anchor=(1.03, 0.5),
        loc='center left',
        title="clusters" if _group != "condition" else "conditions",
        ncol=1,
        frameon=False,
        columnspacing=0.4,
        borderaxespad=0.2,
        handletextpad=0.3
    )
    plt.savefig(f"{fig_outpath}/{args.prefix}{_group}_stream_plot")

print("Trajectories inference...")

epg = adata.uns["epg"]
flat_tree = adata.uns["flat_tree"]

edges = flat_tree.edges
labels = nx.get_node_attributes(flat_tree,"label")

edges = list()
for _edge in flat_tree.edges:
    _out = labels[_edge[0]]
    _in = labels[_edge[1]]
    edges.append((_out, _in))

### Be careful, we do not have the right order between out and in
