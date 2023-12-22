#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import random
random.seed(100)

import os, argparse
from pathlib import Path

import numpy as np, math
from scipy.stats import hypergeom

import pandas as pd, scanpy as sc, json

import matplotlib.pyplot as plt, color_settings as colour, plot_settings
from matplotlib.ticker import FormatStrFormatter
from color_settings import color_cycle

args = {
    "infile":Path("data/scRNA/normalizing/ra/tables/corrected.h5ad").resolve(),
    "outpath":Path("data/scRNA/cluster/ra").resolve(),
    "signatures":Path("data/public/signatures/signatures.json").resolve(),
    "condition":"ra",
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

n_comps = 30 if args["n_dimensions"] <= 15 else args["n_dimensions"]

resolutions = [0.6,0.8,1,1.2]

colour_d = {
    "G1": colour.blue,
    "G2M": colour.red,
    "S": colour.green
}
phase = adata.obs["pypairs_cc_prediction"]

print(f"Running principal component analysis (PCA)...")

adata.obsm["X_pca"], PCs, _, _ = sc.tl.pca(adata.layers["correct"], svd_solver="arpack", n_comps=n_comps, return_info=True)
adata.varm["PCs"] = PCs.transpose()
del PCs

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

print(f"Marker analysis...")

sc.tl.rank_genes_groups(adata,
    layer="normalize",
    groupby="cluster",
    method="wilcoxon",
    corr_method='benjamini-hochberg'
)

markers = adata.uns["rank_genes_groups"]
markers_d = {
    "gene":list(),
    "cluster":list(),
    "p_value":list(),
    "adj_p_value":list(),
    "log2foldchange":list(),
    "score":list()
}

for cluster in sorted(adata.obs["cluster"].unique()):
    markers_d["gene"].extend(markers["names"][cluster])
    markers_d["cluster"].extend([cluster] * adata.n_vars)
    markers_d["p_value"].extend(markers["pvals"][cluster])
    markers_d["adj_p_value"].extend(markers["pvals_adj"][cluster])
    markers_d["log2foldchange"].extend(markers["logfoldchanges"][cluster])
    markers_d["score"].extend(markers["scores"][cluster])

markers_df = pd.DataFrame(data=markers_d)
markers_df = markers_df[markers_df["adj_p_value"] < 0.05]
del markers, markers_d

markers_df.to_csv(f"{data_outpath}/markers.csv", sep=",", index=False)

print(f"Signature analysis...")

with open(args["signatures"], "r") as signatures_f:
    signatures_d = json.load(signatures_f)

valid_gene_names = list(adata.var.index)
for name, genes in signatures_d.items():
    signatures_d[name] = [gene for gene in genes if gene in valid_gene_names]
signatures_d = {f"{name}_{args['condition']}": genes for name, genes in signatures_d.items() if genes}
del valid_gene_names

adata.X = adata.layers["scale"]
for name, genes in signatures_d.items():
    sc.tl.score_genes(adata,
        gene_list=genes,
        ctrl_size=100,
        gene_pool=None,
        n_bins=25,
        score_name=name,
        random_state=1,
        copy=False,
        use_raw=False
    )

print("Summarizing clusters...")

def hypergeometric_test(adata, signatures, markers):
    
    background = list(adata.var.index)
    marked_genes = list(set(markers).intersection(signatures))
    pvalue = 1 - hypergeom.sf(
        len(marked_genes)-1,
        len(background),
        len(signatures),
        len(markers),
        loc=0
    )
    
    return pvalue

def multiple_hypergeometric_test(adata, signatures_d, markers_df, cluster):

    cell_type_pvalue_d = dict()
    markers = markers_df[markers_df["cluster"] == cluster]["gene"]

    for cell_type, signatures in signatures_d.items():
        pvalue = hypergeometric_test(adata, signatures, markers)
        cell_type_pvalue_d[cell_type] = pvalue
    
    return cell_type_pvalue_d

def get_cluster_info(adata, signatures_d, markers_df, cluster):
    
    info_d = dict()
    info_d = {"n_cells":sum(adata.obs["cluster"] == cluster)}
    info_d["proportion_cells"] = info_d["n_cells"]/adata.n_vars
    proportion_phases = adata.obs[adata.obs["cluster"] == cluster]["pypairs_max_class"].value_counts() / sum(adata.obs["cluster"] == cluster)
    info_d.update({phase: proportion_phases[phase] for phase in proportion_phases.index})
    info_d["median_n_genes_by_UMI"] = int(adata.obs[adata.obs["cluster"] == cluster]["n_genes_by_counts"].median())
    info_d["median_total_counts_by_UMI"] = int(adata.obs[adata.obs["cluster"] == cluster]["total_counts"].median())
    info_d["median_proportion_mito_by_UMI"] = f"{adata.obs[adata.obs['cluster'] == cluster]['pct_counts_mitochondrion'].median()}%"
    info_d.update(multiple_hypergeometric_test(adata, signatures_d, markers_df, cluster))
    
    return info_d

cluster_info_d = {cluster: get_cluster_info(adata, signatures_d, markers_df, cluster) for cluster in sorted(adata.obs["cluster"].unique())}
cluster_info_df = pd.DataFrame.from_dict(cluster_info_d, orient='index')

cluster_info_df.to_csv(f"{data_outpath}/cluster_info.csv", sep=",", index=True)
adata.write_h5ad(filename=f"{data_outpath}/counts.h5ad", compression="gzip")

### le cluster 1 sur Python correspond au cluster 5 sur R.
