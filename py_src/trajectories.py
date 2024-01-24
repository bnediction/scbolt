#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import os, sys, contextlib
from pathlib import Path

import anndata as ad, stream as st

import numpy as np
from scipy.sparse import issparse

import matplotlib.pyplot as plt, color_settings as colour, plot_settings as ps

@contextlib.contextmanager
def disable_print():
    with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
        yield

class arguments:
    def __init__(
        self,
        infile=Path("data/scRNA/integration/tables/bbknn.h5ad"),
        outpath=Path("data/scRNA/stream"),
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
    adata.obsm["X_dr"] = adata.obsm["X_umap"].copy()
elif "X_scanorama" in adata.obsm.keys():
    adata.obsm["X_dr"] = adata.obsm["X_scanorama"].copy()
else:
    raise ValueError("Integrated counting (`X_umap` or `X_scanorama`) in adata.obsm not found, aborting")

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
plt.savefig(f"{fig_outpath}/pseudotime")

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
plt.savefig(f"{fig_outpath}/kmeans")

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
plt.savefig(f"{fig_outpath}/cluster")
