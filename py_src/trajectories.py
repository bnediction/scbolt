#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import os, sys, contextlib
from pathlib import Path

import anndata as ad, anndatatools as adt, stream as st

import numpy as np
from scipy.sparse import issparse

import networkx
import rpy2

import matplotlib.pyplot as plt, color_settings as colour, plot_settings as ps
from matplotlib.ticker import FormatStrFormatter

@contextlib.contextmanager
def disable_print():
    with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
        yield

def str2prefix(v: str):
    if v:
        v = v if v[-1] in ["-","_"] else v + "_"
    return v

def edges_plot(ax, edgelines):
    for edgeline in edgelines:
        line = plt.Line2D(edgeline[:,0], edgeline[:, 1], color=colour.black)
        ax.add_line(line)

class arguments:
    def __init__(
        self,
        infile=Path("data/scRNA/integration/tables/bbknn.h5ad"),
        outpath=Path("data/scRNA/stream"),
        prefix=None,
        use_stream_embedding=False,
        layer="correct",
        hvg=True,
        root=1,
        n_embedding_dimensions=15,
        n_reduction_dimensions=4,
        n_clusters=6,
        epg_alpha=0.01,
        epg_mu=0.05,
        epg_lambda=0.05,
        jobs=6,
        verbose=True
    ):
        self.infile = infile
        self.outpath = outpath
        self.prefix = prefix
        self.use_stream_embedding = use_stream_embedding
        self.hvg = hvg
        self.root = f"S{root}"
        self.layer = layer
        self.n_embedding_dimensions = n_embedding_dimensions
        self.n_reduction_dimensions = n_reduction_dimensions
        self.n_clusters=n_clusters
        self.epg_alpha = epg_alpha
        self.epg_mu = epg_mu
        self.epg_lambda = epg_lambda
        self.jobs = jobs
        self.verbose = verbose

args = arguments()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")
args.prefix = "" if args.prefix is None else args.prefix

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

print(f"Loading data...")

adata = ad.read_h5ad(args.infile)
adata.obs_names_make_unique()
adata.uns["workdir"] = args.outpath

if args.use_stream_embedding:
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
            method="mlle",
            feature="top_pcs",
            n_components=args.n_reduction_dimensions,
            n_neighbors=50,
            n_jobs=args.jobs
        )
else:
    if "X_umap" in adata.obsm.keys():
        dr = "X_umap"
    elif "X_scanorama" in adata.obsm.keys():
        dr = "X_scanorama"
    else:
        raise ValueError("Integrated components (`X_umap` or `X_scanorama`) in adata.obsm not found, aborting")
    adata.obsm["X_dr"] = adata.obsm[dr].copy()

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

adata.obs["subclusters"] = np.nan
adata.obs["subclusters"] = adata.obs["subclusters"].astype(str)

nodes_mapping = dict()
for key, value in adata.uns["flat_tree"]._node.items():
    nodes_mapping[key] = value["label"]

subclusters = dict()
for node in nodes_mapping.keys():
    _true = adata.obs["node"] == node
    adata.obs["subclusters"][_true] = str(nodes_mapping[node])

#edgelines = list()
#_nodes = adata.uns["flat_tree"]._node
#for edges in list(adata.uns["flat_tree"].edges):
#    _first = np.array(([_nodes[edges[0]]["pos"]]))
#    _second = np.array(([_nodes[edges[1]]["pos"]]))
#    edgelines.append(np.concatenate((_first, _second)))

print("Plotting trajectories...")

adt.scatterplot(
    adata,
    obs="subclusters",
    obsm=dr,
    colors= colour.COLORS[0:len(nodes_mapping)] + [colour.lightgray],
    xlabel=r"$\mathrm{UMAP_{1}}$" if dr == "X_umap" else r"$\mathrm{x_{1}^{\mathrm{scanorama}}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$" if dr == "X_umap" else r"$\mathrm{x_{2}^{\mathrm{scanorama}}}$",
    add_graph=True,
    s=2
)
ax = plt.gca()
ps.set_default(ax)
ax.legend(
    [string.replace("cluster ","") for string in np.sort(adata.obs["kmeans"].unique())],
    bbox_to_anchor=(0, 0),
    loc="lower left",
    title="clusters",
    ncol=1,
    frameon=False,
    markerscale=2.5,
    columnspacing=0.4,
    borderaxespad=0.2,
    handletextpad=0.3,
    shadow=True
)
plt.savefig(f"{fig_outpath}/{args.prefix}subclusters_dimension_reduction_plot")

st.plot_dimension_reduction(
    adata,
    color=["kmeans"],
    n_components=2,
    show_graph=True,
    show_text=True
)
fig, ax = (plt.gcf(), plt.gca())
ax.tick_params(axis="x", which="major", pad=2)
ax.tick_params(axis="y", which="major", pad=2)
ps.set_default(ax)
ax.legend(
    [string.replace("cluster ","") for string in np.sort(adata.obs["kmeans"].unique())],
    bbox_to_anchor=(1.03, 0.5),
    loc='center left',
    title="clusters",
    ncol=1,
    frameon=False,
    columnspacing=0.4,
    borderaxespad=0.2,
    handletextpad=0.3
)
ax.set_xlabel("")
ax.set_ylabel("")
plt.tick_params(left = False, bottom = False)
plt.savefig(f"{fig_outpath}/{args.prefix}dimension_reduction_plot")

st.plot_stream(
    adata,
    root=args.root,
    color=[f"{args.root}_pseudotime"],
    log_scale=False,
    factor_zoomin=100,
    save_fig=False,
)
fig, ax = (plt.gcf(), plt.gca())
ps.set_default(ax)
ax.tick_params(axis='x', which='major', pad=2)
ax.images[-1].colorbar.remove()
plt.savefig(f"{fig_outpath}/{args.prefix}pseudotime_stream_plot")

st.plot_stream_sc(
    adata,
    root=args.root,
    color=[f"{args.root}_pseudotime"],
    dist_scale=0.1,
    show_text=False,
    save_fig=False,
)
fig, ax = (plt.gcf(), plt.gca())
ps.set_default(ax)
ax.tick_params(axis='x', which='major', pad=2)
plt.savefig(f"{fig_outpath}/{args.prefix}sc_pseudotime_stream_plot")

adata.obs["leiden"] = adata.obs["leiden"].astype(object)
for cluster in ["kmeans", "leiden"]:
    st.plot_stream(
        adata,
        root=args.root,
        color=[cluster],
        log_scale=False,
        factor_zoomin=100,
        save_fig=False,
    )
    fig, ax = (plt.gcf(), plt.gca())
    ax.tick_params(axis='x', which='major', pad=2)
    ps.set_default(ax)
    for idx, patch in enumerate(ax.patches):
        patch.set_color(colour.COLORS[idx])
        patch.set_alpha(1)
    ax.legend(
        [string.replace("cluster ","") for string in np.sort(adata.obs[cluster].unique())],
        bbox_to_anchor=(1.03, 0.5),
        loc='center left',
        title="cluster",
        ncol=1,
        frameon=False,
        columnspacing=0.4,
        borderaxespad=0.2,
        handletextpad=0.3
    )
    plt.savefig(f"{fig_outpath}/{args.prefix}{cluster}_trajectories")

for obs in ["kmeans", "leiden", f"{args.root}_pseudotime"]:
    adt.scatterplot(
        adata,
        obs=obs,
        obsm=dr,
        colors=None,
        xlabel=r"$\mathrm{UMAP_{1}}$" if dr == "X_umap" else r"$\mathrm{x_{1}^{\mathrm{scanorama}}}$",
        ylabel=r"$\mathrm{UMAP_{2}}$" if dr == "X_umap" else r"$\mathrm{x_{2}^{\mathrm{scanorama}}}$",
        outfile=Path(f"{fig_outpath}/{args.prefix}{obs}_{dr.split('_')[-1].lower()}")
    )

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