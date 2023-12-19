#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import random
random.seed(100)

import os, argparse
from pathlib import Path

import matplotlib.pyplot as plt, color_settings as colour, plot_settings
from matplotlib.ticker import FormatStrFormatter
from color_settings import color_cycle

import scanpy as sc

import numpy as np, math

args = {
    "infile":Path("data/scRNA/normalizing/ra/tables/corrected.h5ad").resolve(),
    "outpath":Path("data/scRNA/cluster/ra").resolve(),
    "prefix":"ra_",
    "n_dimensions":15,
    "resolution":0.6
}

data_outpath = Path(f"{args['outpath']}/tables")
fig_outpath = Path(f"{args['outpath']}/figures")

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

print(f"Loading data...")

adata = sc.read_h5ad(args["infile"])

### Clusterization ###

n_comps = 30 if args["n_dimensions"] <= 15 else args["n_dimensions"]

resolutions = [0.6,0.8,1,1.2]

colour_d = {
    "G1": colour.blue,
    "G2M": colour.red,
    "S": colour.green
}
phase = adata.obs["pypairs_cc_prediction"]

print(f"Running principal component analysis (PCA)...")

sc.tl.pca(adata, svd_solver="arpack", n_comps=n_comps)

pc1 = adata.obsm["X_pca"][:,0]
pc2 = adata.obsm["X_pca"][:,1]
fig, ax = plt.subplots(nrows=1, ncols=1)
for p in np.unique(phase):
    idx = np.where(phase == p)[0]
    ax.scatter(pc1[idx], pc2[idx], s=5, facecolors=colour_d[p], edgecolors="none", alpha=1, label=p)
ax.set_xlabel(r"$\mathrm{PC_{1}}$")
ax.set_ylabel(r"$\mathrm{PC_{2}}$")
ax.legend(markerscale=2, edgecolor=colour.black)
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
plt.savefig(f"{fig_outpath}/{args['prefix']}principal-component-analysis")

print(f"Clustering...")

sc.pp.neighbors(adata, n_neighbors=20, n_pcs=args['n_dimensions'])
for resolution in resolutions:
    sc.tl.leiden(adata, resolution=resolution, key_added=f"leiden_{resolution}")

if args["resolution"] in resolutions:
    adata.obs["cluster"] = adata.obs[f"leiden_{args['resolution']}"]
else:
    sc.tl.leiden(adata, resolution=args["resolution"], key_added=f"cluster")

print(f"Running t-SNE...")

sc.tl.tsne(adata, n_pcs=args["n_dimensions"], learning_rate=1000)

tsne1 = adata.obsm["X_tsne"][:,0]
tsne2 = adata.obsm["X_tsne"][:,1]

fig, axes = plt.subplots(nrows=2, ncols=2)
fig.set_figheight(8)
fig.set_figwidth(8)
for i, resolution in enumerate(resolutions):
    for _cluster, _color in zip(np.unique(adata.obs[f"leiden_{resolution}"]), color_cycle):
        idx = np.where(adata.obs[f"leiden_{resolution}"] == _cluster)[0]
        ax = [math.floor(i/2), i%2]
        axes[*ax].scatter(tsne1[idx], tsne2[idx], s=2, facecolors=_color, edgecolors="none", alpha=1, label=_cluster)
        axes[*ax].title.set_text(f"resolution: {resolution}")
        if ax[0] == 1:
            axes[*ax].set_xlabel(r"$t$-$\mathrm{SNE_{1}}$")
        if ax[1] == 0:
            axes[*ax].set_ylabel(r"$t$-$\mathrm{SNE_{2}}$")
plt.savefig(f"{fig_outpath}/{args['prefix']}tsne_clusters")

print(f"Running uniform manifold approximation and projection (UMAP)...")

sc.tl.umap(adata, n_components=2)

umap1 = adata.obsm["X_umap"][:,0]
umap2 = adata.obsm["X_umap"][:,1]

fig, axes = plt.subplots(nrows=2, ncols=2)
fig.set_figheight(8)
fig.set_figwidth(8)
for i, resolution in enumerate(resolutions):
    for _cluster, _color in zip(np.unique(adata.obs[f"leiden_{resolution}"]), color_cycle):
        idx = np.where(adata.obs[f"leiden_{resolution}"] == _cluster)[0]
        ax = [math.floor(i/2), i%2]
        axes[*ax].scatter(umap1[idx], umap2[idx], s=2, facecolors=_color, edgecolors="none", alpha=1, label=_cluster)
        axes[*ax].title.set_text(f"resolution: {resolution}")
        if ax[0] == 1:
            axes[*ax].set_xlabel(r"$\mathrm{UMAP_{1}}$")
        if ax[1] == 0:
            axes[*ax].set_ylabel(r"$\mathrm{UMAP_{2}}$")
plt.savefig(f"{fig_outpath}/{args['prefix']}umap_clusters")

fig, ax = plt.subplots(nrows=1, ncols=1)
for p in np.unique(phase):
    idx = np.where(phase == p)[0]
    ax.scatter(umap1[idx], umap2[idx], s=2, facecolors=colour_d[p], edgecolors="none", alpha=1, label=p)
ax.set_xlabel(r"$\mathrm{UMAP_{1}}$")
ax.set_ylabel(r"$\mathrm{UMAP_{2}}$")
ax.legend(markerscale=5, edgecolor=colour.black)
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
plt.savefig(f"{fig_outpath}/{args['prefix']}umap_phases")

for metric in ["total_counts", "pct_counts_mitochondrion"]:
    fig, ax = plt.subplots(nrows=1, ncols=1)
    if metric == "total_counts":
        cmap = "Greens"
        label = r"$\# \mathrm{read\ counts}$"
    elif metric == "pct_counts_mitochondrion":
        cmap = "Blues"
        label = r"$\frac{\# \mathrm{mitochondrion\ counts}}{\# \mathrm{read\ counts}}$"
    mapping = ax.scatter(umap1, umap2, s=2, c=adata.obs[metric], cmap=cmap, alpha=1)
    cbar = fig.colorbar(mapping)
    cbar.set_label(label, loc="center", labelpad=5)
    ax.set_xlabel(r"$\mathrm{UMAP_{1}}$")
    ax.set_ylabel(r"$\mathrm{UMAP_{2}}$")
    plt.sca(ax)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
    ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
    plt.savefig(f"{fig_outpath}/{args['prefix']}umap_{metric}")
