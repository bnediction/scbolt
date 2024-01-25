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

class arguments:
    def __init__(
        self,
        infile=Path("data/scRNA/integration/tables/bbknn.h5ad"),
        outpath=Path("data/scRNA/stream"),
        prefix=None,
        hvg=False,
        layer="correct",
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
        self.hvg = hvg
        self.layer = layer
        self.n_clusters=n_clusters
        self.epg_alpha = epg_alpha
        self.epg_mu = epg_mu
        self.epg_lambda = epg_lambda
        self.jobs = jobs
        self.verbose = verbose

args = arguments()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")
prefix = "" if args.prefix is None else args.prefix

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

print(f"Loading data...")

adata = ad.read_h5ad(args.infile)
adata.obs_names_make_unique()
adata.uns["workdir"] = args.outpath

#adata.X = adata.layers[args.layer] if not issparse(adata.layers[args.layer]) else adata.layers[args.layer].toarray()
#adata.X = adata.X.astype(np.float64)

if "X_umap" in adata.obsm.keys():
    dr = "X_umap"
elif "X_scanorama" in adata.obsm.keys():
    dr = "X_scanorama"
else:
    raise ValueError("Integrated counting (`X_umap` or `X_scanorama`) in adata.obsm not found, aborting")

adata.obsm["X_dr"] = adata.obsm[dr].copy()

print("Computing elastic principal graph...")

with disable_print():
    st.seed_elastic_principal_graph(
        adata,
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

print("Plotting trajectories...")

st.plot_stream(
    adata,
    root="S1",
    color=["S1_pseudotime"],
    log_scale=False,
    factor_zoomin=100,
    save_fig=False,
)
fig, ax = (plt.gcf(), plt.gca())
ps.set_default(ax)
ax.tick_params(axis='x', which='major', pad=2)
ax.images[-1].colorbar.remove()
plt.savefig(f"{fig_outpath}/{args.prefix}pseudotime_trajectories")

st.plot_stream_sc(
    adata,
    root="S1",
    color=["S1_pseudotime"],
    dist_scale=0.1,
    show_text=False,
    save_fig=False,
)
fig, ax = (plt.gcf(), plt.gca())
ps.set_default(ax)
ax.tick_params(axis='x', which='major', pad=2)
plt.savefig(f"{fig_outpath}/{args.prefix}sc_pseudotime_trajectories")

st.plot_stream(
    adata,
    root="S1",
    color=["kmeans"],
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
    [string.replace("cluster ","") for string in np.sort(adata.obs["kmeans"].unique())],
    bbox_to_anchor=(1.03, 0.5),
    loc='center left',
    title="cluster",
    ncol=1,
    frameon=False,
    columnspacing=0.4,
    borderaxespad=0.2,
    handletextpad=0.3
)
plt.savefig(f"{fig_outpath}/{args.prefix}kmeans_trajectories")

adata.obs["cluster"] = adata.obs["cluster"].astype(object)
st.plot_stream(
    adata,
    root="S1",
    color=["cluster"],
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
    [string.replace("cluster ","") for string in np.sort(adata.obs["cluster"].unique())],
    bbox_to_anchor=(1.03, 0.5),
    loc='center left',
    title="cluster",
    ncol=1,
    frameon=False,
    columnspacing=0.4,
    borderaxespad=0.2,
    handletextpad=0.3
)
plt.savefig(f"{fig_outpath}/{args.prefix}cluster_trajectories")

adt.scatterplot(
    adata,
    obs="kmeans",
    obsm=dr,
    colors=colour.COLORS,
    xlabel=r"$\mathrm{UMAP_{1}}$" if dr == "UMAP" else r"$\mathrm{x_{1}^{\mathrm{scanorama}}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$" if dr == "UMAP" else r"$\mathrm{x_{2}^{\mathrm{scanorama}}}$",
    outfile=Path(f"{fig_outpath}/kmeans_{dr.split('_')[-1].lower()}")
)

adt.scatterplot(
    adata,
    obs="cluster",
    obsm=dr,
    colors=colour.COLORS,
    xlabel=r"$\mathrm{UMAP_{1}}$" if dr == "UMAP" else r"$\mathrm{x_{1}^{\mathrm{scanorama}}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$" if dr == "UMAP" else r"$\mathrm{x_{2}^{\mathrm{scanorama}}}$",
    outfile=Path(f"{fig_outpath}/cluster_{dr.split('_')[-1].lower()}")
)

fig, ax = plt.subplots(nrows=1, ncols=1)
fig.set_figheight(5)
fig.set_figwidth(6.5)
sc = ax.scatter(
    adata.obsm[dr][:,0],
    adata.obsm[dr][:,1],
    s=3,
    c=adata.obs["S1_pseudotime"],
    cmap="autumn",
    edgecolors="none",
    alpha=1
)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
fig.colorbar(sc)
plt.savefig(Path(f"{fig_outpath}/{args.prefix}pseudotime_{dr.split('_')[-1].lower()}"))

print("Saving data...")

for key in list(adata.obs.keys()):
    if isinstance (adata.obs[key][0], tuple):
        del adata.obs[key]

for key in list(adata.uns.keys()):
    if isinstance(adata.uns[key], (networkx.classes.graph.Graph, rpy2.rinterface.ListSexpVector, Path)):
        del adata.uns[key]
    if key.startswith("stream_S"):
        del adata.uns[key]

adata.write_h5ad(filename=f"{data_outpath}/{args.prefix}stream.h5ad", compression="gzip")