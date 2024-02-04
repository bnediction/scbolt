#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import os, contextlib, argparse
from pathlib import Path

import pandas as pd
import anndata as ad, anndatatools as adt, stream as st

import numpy as np
from scipy.sparse import issparse

import networkx
import rpy2

import matplotlib.pyplot as plt, color_settings as colour, plot_settings as ps

@contextlib.contextmanager
def disable_print():
    with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
        yield

def str2prefix(v: str):
    if v:
        v = v if v[-1] in ["-","_"] else v + "_"
    return v

def str2bool(v: str):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")

parser = argparse.ArgumentParser(
    prog="trajectory inference of sc-RNAseq data",
    description="""From concatenated (sometimes integrated) sc-rnaSeq data recorded in the \
        hdf5 format (<filename>.h5ad), compute cell phenotype trajectory based on the STREAM \
        method (see Chen et al. (2019): <https://www.nature.com/articles/s41467-019-09670-4>).""",
    usage=""""python trajectories.py [-h] -i <path> [<args>]"""
)

parser.add_argument(
    "-i", "--infile",
    dest="infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="path to .h5ad file (including file)"
)

parser.add_argument(
    "-o", "--outpath",
    dest="outpath",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=Path("./").resolve(),
    help="output path"
)

parser.add_argument(
    "-p", "--prefix",
    dest="prefix",
    type=str2prefix,
    required=False,
    default="",
    help="prefix for each saving file"
)

parser.add_argument(
    "--st", "--save-tables",
    dest="save_tables",
    type=str2bool,
    required=False,
    default=True,
    help="save the anndata in the h5ad format"
)

parser.add_argument(
    "-s", "--use-stream-embedding",
    dest="use_stream_embedding",
    type=str2prefix,
    required=False,
    help="""compute embedding component using classic stream data preprocessing.
    If not, use existing pre-computed embedding components"""
)

parser.add_argument(
    "-m", "--method",
    dest="method",
    type=str,
    required=False,
    choices=["se", "mlle", "umap", "pca"],
    help="method used for dimension reduction (only if --use-stream-embedding True is specified)."
)

parser.add_argument(
    "-l", "--layer",
    dest="layer",
    type=str,
    required=False,
    help="layer used for dimension reduction (only if --use-stream-embedding True is specified)."
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    type=str2bool,
    required=False,
    default=None,
    help="select the most variable genes for dimension reduction (only if --use-stream-embedding True is specified)."
)

parser.add_argument(
    "-d", "--dimensions",
    dest="n_dimensions",
    type=int,
    required=False,
    default=3,
    help="number of components to keep (only if --use-stream-embedding True is specified)."
)

parser.add_argument(
    "-j", "--jobs",
    dest="n_jobs",
    type=int,
    required=False,
    default=1,
    help="number of parallel jobs to run when dimension reduction is performed (only if --use-stream-embedding True is specified)."
)

parser.add_argument(
    "-r", "--root",
    dest="root",
    type=int,
    required=False,
    default=0,
    help="root of the elastic principal graph."
)

parser.add_argument(
    "-c", "--clusters",
    dest="n_clusters",
    type=int,
    required=False,
    default=5,
    help="number of clusters to compute for elastic principal graph."
)

parser.add_argument(
    "--lambda", "--epg-lambda",
    dest="epg_lambda",
    type=float,
    required=False,
    default=0.05,
    help="lambda parameter used to compute the elastic energy."
)

parser.add_argument(
    "--mu", "--epg-mu",
    dest="epg_mu",
    type=float,
    required=False,
    default=0.05,
    help="mu parameter used to compute the elastic energy."
)

parser.add_argument(
    "--alpha", "--epg-alpha",
    dest="epg_alpha",
    type=float,
    required=False,
    default=0.01,
    help="alpha parameter of the penalized elastic energy."
)

parser.add_argument(
    "--legend",
    dest="legend",
    type=str2bool,
    required=False,
    default=False,
    help="add legend to plot."
)

args = parser.parse_args()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")
root=f"S{args.root}"

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

print(f"Loading data...")

adata = ad.read_h5ad(args.infile)
adata.obs_names_make_unique()
adata.uns["workdir"] = args.outpath

if args.use_stream_embedding is True:
    with disable_print():
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
        dr = f"{args.method}"
else:
    if "X_umap" in adata.obsm.keys():
        dr = "X_umap"
    elif "X_scanorama" in adata.obsm.keys():
        dr = "X_scanorama"
    else:
        raise ValueError("Integrated components (`X_umap` or `X_scanorama`) in adata.obsm not found, aborting")
    adata.obsm["X_dr"] = adata.obsm[dr].copy()

adata.obs["condition"] = adata.obs["condition"].astype(object)
adata.obs["leiden"] = adata.obs["leiden"].astype(object)

print("Computing elastic principal graph...")

with disable_print():
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
    st.extend_elastic_principal_graph(
        adata,
        epg_ext_mode='WeigthedCentroid',
        epg_ext_par=0.8
    )

adata.obs["node_clusters"] = np.nan
adata.obs["node_clusters"] = adata.obs["node_clusters"].astype(str)

nodes_mapping = dict()
for key, value in adata.uns["flat_tree"]._node.items():
    nodes_mapping[key] = value["label"]

node_clusters = dict()
for node in nodes_mapping.keys():
    _true = adata.obs["node"] == node
    adata.obs["node_clusters"][_true] = str(nodes_mapping[node])

print("Plotting trajectories...")

for cluster in ["node_clusters", "condition", "kmeans", "leiden", f"{root}_pseudotime"]:
    adt.scatterplot(
        adata,
        obs=cluster,
        obsm=dr,
        colors=colour.COLORS[0:len(nodes_mapping)] + [colour.lightgray] if cluster == "node_clusters" else None,
        xlabel=r"$\mathrm{UMAP_{1}}$" if dr == "X_umap" else r"$\mathrm{x_{1}^{\mathrm{scanorama}}}$",
        ylabel=r"$\mathrm{UMAP_{2}}$" if dr == "X_umap" else r"$\mathrm{x_{2}^{\mathrm{scanorama}}}$",
        add_graph=True,
        s=2,
        add_legend=True,
        lgd_params={
            "title":"clusters" if cluster != "condition" else "conditions",
            "labels":[string.replace("cluster ","") for string in np.sort(adata.obs[cluster].unique())],
            "ncol":1,
            "markerscale":2.5,
            "frameon":True,
            "shadow":False
        } if not pd.api.types.is_float_dtype(adata.obs[cluster]) else None,
    )
    ps.set_default(plt.gca())
    if "pseudotime" not in cluster:
        plt.savefig(f"{fig_outpath}/{args.prefix}{cluster}_{dr.split('_')[-1].lower()}")
    else:
        plt.savefig(f"{fig_outpath}/{args.prefix}pseudotime_{dr.split('_')[-1].lower()}")

st.plot_stream(
    adata,
    root=root,
    color=[f"{root}_pseudotime"],
    log_scale=False,
    factor_zoomin=100,
    save_fig=False,
)
fig, ax = (plt.gcf(), plt.gca())
ps.set_default(ax)
ax.tick_params(axis="x", which="major", pad=2)
ax.images[-1].colorbar.remove()
plt.savefig(f"{fig_outpath}/{args.prefix}pseudotime_stream_plot")

for cluster in ["condition", "kmeans", "leiden"]:
    st.plot_stream(
        adata,
        root=root,
        color=[cluster],
        log_scale=False,
        factor_zoomin=100,
        save_fig=False,
    )
    fig, ax = (plt.gcf(), plt.gca())
    ax.tick_params(axis="x", which="major", pad=2)
    ps.set_default(ax)
    for idx, patch in enumerate(ax.patches):
        patch.set_color(colour.COLORS[idx])
        patch.set_alpha(1)
    ax.legend(
        [string.replace("cluster ","") for string in np.sort(adata.obs[cluster].unique())],
        bbox_to_anchor=(1.03, 0.5),
        loc='center left',
        title="clusters" if cluster != "condition" else "conditions",
        ncol=1,
        frameon=False,
        columnspacing=0.4,
        borderaxespad=0.2,
        handletextpad=0.3
    )
    plt.savefig(f"{fig_outpath}/{args.prefix}{cluster}_stream_plot")

if args.save_tables:

    print("Saving data...")

    for key in list(adata.obs.keys()):
        if isinstance (adata.obs[key][0], tuple):
            del adata.obs[key]

    for key in list(adata.uns.keys()):
        if isinstance(adata.uns[key], (tuple, Path, networkx.classes.graph.Graph, rpy2.rinterface.ListSexpVector)):
            del adata.uns[key]
        if key.startswith("stream_S"):
            del adata.uns[key]

    adata.write_h5ad(filename=f"{data_outpath}/{args.prefix}stream.h5ad", compression="gzip")