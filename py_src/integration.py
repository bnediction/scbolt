#!/usr/bin/python3

import os
from pathlib import Path

from typing import Sequence

from itertools import cycle
from collections import OrderedDict as odict

import numpy as np

import anndata as ad
import scanpy as sc
import scanorama

import matplotlib.pyplot as plt, color_settings as colour, plot_settings
from matplotlib.ticker import FormatStrFormatter
from color_settings import color_cycle

def clean_adata(
    adata: ad.AnnData,
    obs: Sequence[str] = None,
    var: Sequence[str] = None,
    copy: bool = False
    ) -> None:
        
        adata = adata.copy() if copy else adata

        if obs:
            for _obs in obs:
                if _obs in adata.obs.columns:
                    del adata.obs[_obs]
        if var:
            for _var in var:
                if _var in adata.var.columns:
                    del adata.var[_var]
        if "pca" in adata.uns.keys():
            del adata.uns["pca"]
        if "neighbors" in adata.uns.keys():
            del adata.uns["neighbors"]
        if "leiden" in adata.uns.keys():
            del adata.uns["leiden"]
        if "tsne" in adata.uns.keys():
            del adata.uns["tsne"]
        if "umap" in adata.uns.keys():
            del adata.uns["umap"]
        if "hvg" in adata.uns.keys():
            try:
                del adata.uns["hvg"]
                del adata.var["highly_variable"]
                del adata.var["highly_variable_rank"]
            except:
                pass
        del adata.obsm, adata.obsp, adata.varm, adata.varp

        if copy:
            return adata


class arguments:

    def __init__(
        self,
        infile_ref="data/scRNA/normalizing/ct/tables/corrected.h5ad",
        infile_interest="data/scRNA/normalizing/ra/tables/corrected.h5ad",
        outpath="data/scRNA/integration",
        label="condition",
        metadata="age+condition+date",
        metric="euclidean",
        k_neighbors=20,
        correction="G2M_score+S_score+G1_score",
        n_dimensions=15,
        dim_clustering=15,
        dim_integration=50,
        dim_CCA=15,
        resolution=0.5,
        logfc_threshold=0.25,
        n_jobs=5
    ):
        self.infile_ref = Path(infile_ref)
        self.infile_interest = Path(infile_interest)
        self.outpath = Path(outpath)
        self.label = label
        self.metadata = metadata.split("+")
        self.metric = metric
        self.k_neighbors = k_neighbors
        self.correction = correction.split("+")
        self.n_dimensions = n_dimensions
        self.dim_clustering = dim_clustering
        self.dim_integration = dim_integration
        self.dim_CCA = dim_CCA
        self.resolution = resolution
        self.logfc_threshold = logfc_threshold
        self.n_jobs = n_jobs

args = arguments()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

print(f"Loading data...")

adata_d = odict()
adata_d["reference"] = sc.read_h5ad(args.infile_ref)
adata_d["interest"] = sc.read_h5ad(args.infile_interest)
if args.label:
    label = [adata.uns[args.label] for adata in adata_d.values()]
else:
    label = ["reference", "interest"]
valid_genes = list(set(adata_d["reference"].var.index).intersection(set(adata_d["interest"].var.index)))

for key in adata_d.keys():
    clean_adata(adata_d[key])
    adata_d[key].X = adata_d[key].layers["correct"]
    adata_d[key] = adata_d[key][:,valid_genes]
    sc.pp.highly_variable_genes(adata_d[key], layer="raw", flavor="seurat_v3", span=0.3, n_bins=20, n_top_genes=2000, inplace=True)

del valid_genes

print("Integration using mnn...")

sc.tl.pca(
    adata_d["reference"],
    zero_center=False,
    n_comps=max(args.dim_clustering, args.dim_integration),
    use_highly_variable=True,
    copy=False
)
sc.pp.neighbors(
    adata_d["reference"],
    n_neighbors=args.k_neighbors,
    n_pcs=args.dim_clustering,
    copy=False
)
sc.tl.umap(
    adata_d["reference"],
    n_components=2,
    random_state=0
)

sc.tl.ingest(
    adata=adata_d["interest"],
    adata_ref=adata_d["reference"],
    obs=None,
    embedding_method=["pca", "umap"],
    n_jobs=args.n_jobs
)

fig, ax = plt.subplots(nrows=1, ncols=1)
fig.set_figheight(5)
fig.set_figwidth(5)
ax.scatter(adata_d["reference"].obsm["X_pca"][:,0], adata_d["reference"].obsm["X_pca"][:,1], s=2, facecolors=colour.green, edgecolors="none", alpha=1, label=label[0])
ax.scatter(adata_d["interest"].obsm["X_pca"][:,0], adata_d["interest"].obsm["X_pca"][:,1], s=2, facecolors=colour.red, edgecolors="none", alpha=1, label=label[1])
ax.set_xlabel(r"$\mathrm{PC_{1}}$")
ax.set_ylabel(r"$\mathrm{PC_{2}}$")
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.legend(markerscale=5, edgecolor=colour.black)
plt.savefig(f"{fig_outpath}/ingest_pca")

fig, ax = plt.subplots(nrows=1, ncols=1)
fig.set_figheight(5)
fig.set_figwidth(5)
ax.scatter(adata_d["reference"].obsm["X_umap"][:,0], adata_d["reference"].obsm["X_umap"][:,1], s=2, facecolors=colour.green, edgecolors="none", alpha=1, label=label[0])
ax.scatter(adata_d["interest"].obsm["X_umap"][:,0], adata_d["interest"].obsm["X_umap"][:,1], s=2, facecolors=colour.red, edgecolors="none", alpha=1, label=label[1])
ax.set_xlabel(r"$\mathrm{UMAP_{1}}$")
ax.set_ylabel(r"$\mathrm{UMAP_{2}}$")
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.legend(markerscale=5, edgecolor=colour.black)
plt.savefig(f"{fig_outpath}/ingest_umap")

try:
    concat_adata = ad.concat(
        list(adata_d.values()),
        join="inner",
        label=args.label,
        keys=label,
        merge="same",
        uns_merge="same"
    )
except:
    raise RuntimeError("Anndatas concatenation did not work, aborting")

sc.pp.neighbors(
    concat_adata,
    n_neighbors=args.k_neighbors,
    n_pcs=args.dim_clustering,
    copy=False
)
sc.tl.leiden(
    concat_adata,
    resolution=args.resolution,
    key_added=f"cluster"
)

fig, ax = plt.subplots(nrows=1, ncols=1)
fig.set_figheight(5)
fig.set_figwidth(5)
for _cluster, _color in zip(sorted(np.unique(concat_adata.obs["cluster"])), color_cycle):
    idx = np.where(concat_adata.obs["cluster"] == _cluster)[0]
    ax.scatter(concat_adata.obsm["X_umap"][idx,0], concat_adata.obsm["X_umap"][idx,1], s=2, facecolors=_color, edgecolors="none", alpha=1)
ax.set_xlabel(r"$\mathrm{UMAP_{1}}$")
ax.set_ylabel(r"$\mathrm{UMAP_{2}}$")
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
plt.savefig(f"{fig_outpath}/ingest_umap_clusters")

concat_adata.write_h5ad(filename=f"{data_outpath}/ingest.h5ad", compression="gzip")

print("Integration using bbknn...")

clean_adata(
    concat_adata,
    obs="cluster"
)

sc.pp.highly_variable_genes(
    concat_adata,
    layer="raw",
    flavor="seurat_v3",
    span=0.3,
    n_bins=20,
    n_top_genes=2000,
    inplace=True
)
sc.tl.pca(
    concat_adata,
    zero_center=False,
    n_comps=max(args.dim_clustering, args.dim_integration),
    use_highly_variable=True,
    copy=False
)
sc.external.pp.bbknn(
    concat_adata,
    batch_key=args.label,
    use_rep="X_pca",
    metric=args.metric,
    copy=False,
    neighbors_within_batch=args.k_neighbors,
    n_pcs=args.dim_clustering,
)
sc.tl.umap(
    concat_adata,
    n_components=2,
    random_state=0
)

fig, ax = plt.subplots(nrows=1, ncols=1)
fig.set_figheight(5)
fig.set_figwidth(5)
ref_idx = concat_adata.obs["condition"] == label[0]
idx = concat_adata.obs["condition"] == label[1]
ax.scatter(concat_adata.obsm["X_umap"][ref_idx,0], concat_adata.obsm["X_umap"][ref_idx,1], s=2, facecolors=colour.green, edgecolors="none", alpha=1, label=label[0])
ax.scatter(concat_adata.obsm["X_umap"][idx,0], concat_adata.obsm["X_umap"][idx,1], s=2, facecolors=colour.red, edgecolors="none", alpha=1, label=label[1])
ax.set_xlabel(r"$\mathrm{UMAP_{1}}$")
ax.set_ylabel(r"$\mathrm{UMAP_{2}}$")
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.legend(markerscale=5, edgecolor=colour.black)
plt.savefig(f"{fig_outpath}/bbknn_umap")

sc.pp.neighbors(
    concat_adata,
    n_neighbors=args.k_neighbors,
    n_pcs=args.dim_clustering,
    copy=False
)
sc.tl.leiden(
    concat_adata,
    resolution=args.resolution,
    key_added=f"cluster"
)

fig, ax = plt.subplots(nrows=1, ncols=1)
fig.set_figheight(5)
fig.set_figwidth(5)
for _cluster, _color in zip(sorted(np.unique(concat_adata.obs["cluster"])), color_cycle):
    idx = np.where(concat_adata.obs["cluster"] == _cluster)[0]
    ax.scatter(concat_adata.obsm["X_umap"][idx,0], concat_adata.obsm["X_umap"][idx,1], s=2, facecolors=_color, edgecolors="none", alpha=1)
ax.set_xlabel(r"$\mathrm{UMAP_{1}}$")
ax.set_ylabel(r"$\mathrm{UMAP_{2}}$")
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
plt.savefig(f"{fig_outpath}/bbknn_umap_clusters")

concat_adata.write_h5ad(filename=f"{data_outpath}/bbknn.h5ad", compression="gzip")

del concat_adata

print("Integration using scanorama...")

for key in adata_d.keys():
    clean_adata(adata_d[key])

adata_l = list(adata_d.values())
del adata_d

adata_l = scanorama.correct_scanpy(
    adata_l,
    dimred=max(args.dim_clustering, args.dim_integration),
    return_dimred=True
)

try:
    concat_adata = ad.concat(
        adata_l,
        join="inner",
        label=args.label,
        keys=label,
        merge="same",
        uns_merge="same"
    )
    del adata_l
except:
    raise RuntimeError("Anndatas concatenation did not work, aborting")

fig, ax = plt.subplots(nrows=1, ncols=1)
fig.set_figheight(5)
fig.set_figwidth(5)
ref_idx = concat_adata.obs["condition"] == label[0]
idx = concat_adata.obs["condition"] == label[1]
ax.scatter(concat_adata.obsm["X_scanorama"][ref_idx,0], concat_adata.obsm["X_umap"][ref_idx,1], s=2, facecolors=colour.green, edgecolors="none", alpha=1, label=label[0])
ax.scatter(concat_adata.obsm["X_scanorama"][idx,0], concat_adata.obsm["X_umap"][idx,1], s=2, facecolors=colour.red, edgecolors="none", alpha=1, label=label[1])
ax.set_xlabel(r"$\mathrm{x_{1}^{\mathrm{scanorama}}}$")
ax.set_ylabel(r"$\mathrm{x_{2}^{\mathrm{scanorama}}}$")
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.legend(markerscale=5, edgecolor=colour.black)
plt.savefig(f"{fig_outpath}/scanorama_components")

sc.pp.neighbors(
    concat_adata,
    n_neighbors=args.k_neighbors,
    use_rep="X_scanorama",
    n_pcs=args.dim_clustering,
    copy=False
)
sc.tl.leiden(
    concat_adata,
    resolution=args.resolution,
    key_added=f"cluster"
)
sc.tl.umap(
    concat_adata,
    n_components=2,
    random_state=0
)

fig, ax = plt.subplots(nrows=1, ncols=1)
fig.set_figheight(5)
fig.set_figwidth(5)
ref_idx = concat_adata.obs["condition"] == label[0]
idx = concat_adata.obs["condition"] == label[1]
ax.scatter(concat_adata.obsm["X_umap"][ref_idx,0], concat_adata.obsm["X_umap"][ref_idx,1], s=2, facecolors=colour.green, edgecolors="none", alpha=1, label=label[0])
ax.scatter(concat_adata.obsm["X_umap"][idx,0], concat_adata.obsm["X_umap"][idx,1], s=2, facecolors=colour.red, edgecolors="none", alpha=1, label=label[1])
ax.set_xlabel(r"$\mathrm{UMAP_{1}}$")
ax.set_ylabel(r"$\mathrm{UMAP_{2}}$")
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.legend(markerscale=5, edgecolor=colour.black)
plt.savefig(f"{fig_outpath}/scanorama_umap")

fig, ax = plt.subplots(nrows=1, ncols=1)
fig.set_figheight(5)
fig.set_figwidth(5)
for _cluster, _color in zip(sorted(np.unique(concat_adata.obs["cluster"])), color_cycle):
    idx = np.where(concat_adata.obs["cluster"] == _cluster)[0]
    ax.scatter(concat_adata.obsm["X_umap"][idx,0], concat_adata.obsm["X_umap"][idx,1], s=2, facecolors=_color, edgecolors="none", alpha=1)
ax.set_xlabel(r"$\mathrm{UMAP_{1}}$")
ax.set_ylabel(r"$\mathrm{UMAP_{2}}$")
plt.sca(ax)
ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
plt.savefig(f"{fig_outpath}/scanorama_umap_clusters")

concat_adata.write_h5ad(filename=f"{data_outpath}/scanorama.h5ad", compression="gzip")
