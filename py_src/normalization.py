#!/usr/bin/python3

import os
from pathlib import Path

import matplotlib.pyplot as plt, color_settings as colour, plot_settings
from matplotlib.ticker import FormatStrFormatter
from color_settings import color_cycle

import scanpy as sc

import numpy as np, scipy, math
from sklearn.linear_model import LinearRegression

from itertools import cycle

def regress_out_feature(interest, regressors, intercept=False, n_jobs=1):

    regression_model = LinearRegression(fit_intercept=False, n_jobs=n_jobs)
    regression_model.fit(regressors, interest)
    _prediction = regression_model.predict(regressors)

    if intercept:
        _intercept = regression_model.coef_[0][0]
        _result = interest - _prediction + _intercept
    else:
        _result = interest - _prediction
    
    return _result[:,0]

def regress_out(adata, correction, intercept=False, n_jobs=1):

    if sc.preprocessing._simple.issparse(adata.X):
        adata.X = adata.X.toarray()
    regressors = adata.obs[correction]
    regressors.insert(0, 'ones', 1.0)
    regressors = regressors.to_numpy()

    for i in range(adata.n_vars):
        interest = adata.X[:,i].reshape(-1, 1)
        corrected_interest = regress_out_feature(interest, regressors, intercept=intercept, n_jobs=n_jobs)
        adata.X[:,i] = corrected_interest
    
    return adata

args = {
    "infile": Path(f"data/scRNA/cell_filtering/ct/tables/counts.h5ad").resolve(),
    "outpath": Path(f"data/scRNA/normalizing/ct").resolve(),
    "suffix": "ct",
    "correction": "G2M_score+S_score+G1_score",
    "gene_filtering": True,
    "min_cell_expression_proportion": 0.001,
    "dim": 15,
    "intercept":False,
    "n_jobs":6,
    "n_dimensions":15
}

data_outpath = Path(f"{args['outpath']}/tables")
fig_outpath = Path(f"{args['outpath']}/figures")

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

correction = args["correction"].split("+")

print(f"Loading data...")

adata = sc.read_h5ad(args["infile"])
_k = list()

print(f"Filtering genes...")

if args["gene_filtering"]:

    _k.append(adata.n_vars)

    threshold = args["min_cell_expression_proportion"]*adata.n_obs
    sc.pp.filter_genes(data=adata, min_cells=threshold)

    _k.append(adata.n_vars)

    fig, ax = plt.subplots(nrows=1, ncols=1)
    plt.bar(
        ["before filtering", "after filtering"], _k,
        width=0.8,
        linewidth=2,
        color=colour.pink,
        edgecolor=colour.red
    )
    ax.update({"xmargin": 0.1})
    plt.savefig(f"{fig_outpath}/gene-number.png")

print(f"Selecting Higly variable genes...")

sc.pp.highly_variable_genes(adata, flavor="seurat_v3", span=0.3, n_bins=20, n_top_genes=2000, inplace=True)
adata = adata[:, adata.var.highly_variable]

print(f"Normalizing data...")

sc.pp.normalize_total(adata, target_sum=1e4, inplace=True)
sc.pp.log1p(adata)

normalized_ad = adata.copy(); corrected_ad = adata.copy()
del adata

print(f"Scaling data...")

sc.pp.scale(normalized_ad)
normalized_ad.write_h5ad(filename=f"{data_outpath}/uncorrected_{args['suffix']}.h5ad", compression="gzip")

print(f"Correcting batch (unwanted) effects and scaling data...")

corrected_ad = regress_out(corrected_ad, correction, intercept=False, n_jobs=args["n_jobs"])
sc.pp.scale(corrected_ad)
corrected_ad.write_h5ad(filename=f"{data_outpath}/corrected_{args['suffix']}.h5ad", compression="gzip")

# corrected_ad = sc.read_h5ad(Path("data/scRNA/normalizing/ct/tables/corrected_ct.h5ad"))

ndims = 30
resolutions = [0.6,0.8,1,1.2]

colour_d = {
    "G1": colour.blue,
    "G2M": colour.red,
    "S": colour.green
}
phase = adata.obs["pypairs_cc_prediction"]

print(f"Running principal component analysis (PCA)...")

sc.tl.pca(adata, svd_solver='arpack', n_comps=ndims)

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
plt.savefig(f"{fig_outpath}/{args['suffix']}_principal-component-analysis")

print(f"Clustering...")

sc.pp.neighbors(adata, n_neighbors=20, n_pcs=args["n_dimensions"])
for resolution in resolutions:
    sc.tl.leiden(adata, resolution=resolution, key_added=f"leiden_{resolution}")

print(f"Running t-SNE...")

sc.tl.tsne(adata, n_pcs=args["n_dimensions"])

fig, axes = plt.subplots(nrows=2, ncols=2)
tsne1 = adata.obsm["X_tsne"][:,0]
tsne2 = adata.obsm["X_tsne"][:,1]
for i, resolution in enumerate(resolutions):
    for _cluster, _color in zip(np.unique(adata.obs[f"leiden_{resolution}"]), color_cycle):
        idx = np.where(adata.obs[f"leiden_{resolution}"] == _cluster)[0]
        ax = [math.floor(i/2), i%2]
        axes[*ax].scatter(tsne1[idx], tsne2[idx], s=2, facecolors=_color, edgecolors="none", alpha=1, label=_cluster)
        if ax[0] == 1:
            axes[*ax].set_xlabel(r"$\mathrm{t-SNE_{1}}$")
        if ax[1] == 0:
            axes[*ax].set_ylabel(r"$\mathrm{t-SNE_{2}}$")
plt.savefig(f"{fig_outpath}/{args['suffix']}_tsne_clusters")

print(f"Running uniform manifold approximation and projection (UMAP)...\n")

sc.tl.umap(adata, n_components=args["n_dimensions"])

fig, axes = plt.subplots(nrows=2, ncols=2)
umap1 = adata.obsm["X_umap"][:,0]
umap2 = adata.obsm["X_umap"][:,1]
for i, resolution in enumerate(resolutions):
    for _cluster, _color in zip(np.unique(adata.obs[f"leiden_{resolution}"]), color_cycle):
        idx = np.where(adata.obs[f"leiden_{resolution}"] == _cluster)[0]
        ax = [math.floor(i/2), i%2]
        axes[*ax].scatter(umap1[idx], umap2[idx], s=2, facecolors=_color, edgecolors="none", alpha=1, label=_cluster)
        if ax[0] == 1:
            axes[*ax].set_xlabel(r"$\mathrm{UMAP_{1}}$")
        if ax[1] == 0:
            axes[*ax].set_ylabel(r"$\mathrm{UMAP_{2}}$")
plt.savefig(f"{fig_outpath}/{args['suffix']}_umap_clusters")

sc.pl.umap(adata, show=True, save=False)
