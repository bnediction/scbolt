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
from sklearn.linear_model import LinearRegression

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

parser = argparse.ArgumentParser(
    prog="Normalization of sc-RNAseq data and clusterization",
    description="""From one-condition sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    filter low-quality genes (gene poorly expressed and no HVG),
    normalize data with respect to the depth library, scale data
    and correct batch effects. Then, reduct the dimension by using PCA,
    cluster cells and compute t-SNE and UMAP.""",
    usage="python normalization.py [<args>]"
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
    "-c", "--correction",
    dest="correction",
    type=lambda x: x.split("+"),
    required=False,
    default=["G2M_score", "S_score", "G1_score"],
    help="batch effect to correct (ex: 'G2M_score+S_score+G1_score')"
)

parser.add_argument(
    "-m", "--min-cell-expression-proportion",
    dest="min_cell_expression_proportion",
    type=float,
    required=False,
    default=0.001,
    help="remove gene for which the proportion of expressed cells is inferior to the given value (between 0 and 1, default=0.001)"
)

parser.add_argument(
    "-d", "--dimensions",
    dest="n_dimensions",
    type=int,
    required=False,
    default=15,
    help="number of principal components taken into account"
)

parser.add_argument(
    "-r", "--resolution",
    dest="resolution",
    type=float,
    required=False,
    default=0.6,
    help="clustering resolution"
)

parser.add_argument(
    "-j", "--jobs",
    dest="n_jobs",
    type=int,
    required=False,
    default=1,
    help="number of process to use"
)

args = parser.parse_args()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

print(f"Loading data...")

adata = sc.read_h5ad(args.infile)
_k = list()

print(f"Filtering genes...")

if args.min_cell_expression_proportion:

    _k.append(adata.n_vars)

    threshold = args.min_cell_expression_proportion*adata.n_obs
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

print(f"Selecting higly variable genes (HVG)...")

sc.pp.highly_variable_genes(adata, flavor="seurat_v3", span=0.3, n_bins=20, n_top_genes=2000, inplace=True)

print(f"Normalizing data...")

sc.pp.normalize_total(adata, target_sum=1e4, inplace=True)
sc.pp.log1p(adata)
adata = adata[:, adata.var.highly_variable]

normalized_ad = adata.copy(); corrected_ad = adata.copy()
del adata

print(f"Scaling data...")

sc.pp.scale(normalized_ad)
normalized_ad.write_h5ad(filename=f"{data_outpath}/{args.prefix}uncorrected.h5ad", compression="gzip")

print(f"Correcting batch (unwanted) effects and scaling data...")

corrected_ad = regress_out(corrected_ad, args.correction, intercept=False, n_jobs=args.n_jobs)
sc.pp.scale(corrected_ad)
corrected_ad.write_h5ad(filename=f"{data_outpath}/{args.prefix}corrected.h5ad", compression="gzip")

### Clustering and computing some metrics ###

adata = corrected_ad
del corrected_ad
n_comps = 30 if args.n_dimensions <= 15 else args.n_dimensions

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
plt.savefig(f"{fig_outpath}/{args.prefix}principal-component-analysis")

print(f"Clustering...")

sc.pp.neighbors(adata, n_neighbors=20, n_pcs=args.n_dimensions)
for resolution in resolutions:
    sc.tl.leiden(adata, resolution=resolution, key_added=f"leiden_{resolution}")

if args.resolution in resolutions:
    adata.obs["cluster"] = adata.obs[f"leiden_{args.resolution}"]
else:
    sc.tl.leiden(adata, resolution=args.resolution, key_added=f"cluster")

print(f"Running t-SNE...")

sc.tl.tsne(adata, n_pcs=args.n_dimensions, learning_rate=1000)

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
plt.savefig(f"{fig_outpath}/{args.prefix}tsne_clusters")

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
plt.savefig(f"{fig_outpath}/{args.prefix}umap_clusters")

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
plt.savefig(f"{fig_outpath}/{args.prefix}umap_phases")

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
    plt.savefig(f"{fig_outpath}/{args.prefix}umap_{metric}")
