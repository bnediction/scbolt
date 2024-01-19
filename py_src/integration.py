#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import os, argparse
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

def str2bool(v: str):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")

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

def scatterplot(
    adata: ad.AnnData,
    obs: str,
    obsm: str,
    xlabel: str = r"$x_{1}",
    ylabel: str = r"$x_{2}",
    outfile: Path = Path("./figure"),
):

    if obs not in adata.obs:
        raise ValueError(f"adata.obs[{obs}] does not exist, aborting")
    if obsm not in adata.obsm:
        raise ValueError(f"adata.obsm[{obsm}] does not exist, aborting")

    if len(adata.obs[obs].unique()) < 2:
        raise ValueError(f"adata.obs[{obs}] specifies only one category, aborting")
    elif len(adata.obs[obs].unique()) == 2:
        print_legend = True
    else:
        print_legend = False

        colors = cycle([
        colour.red,
        colour.green,
        colour.blue,
        colour.orange,
        colour.purple,
        colour.skyblue,
        colour.teal,
        colour.pink,
        colour.violet,
        colour.darkblue,
        colour.magenta,
        colour.darkgreen,
        colour.darkorange,
        colour.gray,
        colour.maroon,
        colour.olive,
        colour.orchid,
        colour.beet,
        colour.indigo,
        colour.gold,
        colour.navy,
        colour.salmon
    ])

    fig, ax = plt.subplots(nrows=1, ncols=1)
    fig.set_figheight(5)
    fig.set_figwidth(5)
    for _cluster, _color in zip(sorted(adata.obs[obs].unique()), colors):
        idx = np.where(adata.obs[obs] == _cluster)[0]
        if print_legend:
            ax.scatter(adata.obsm[obsm][idx,0], adata.obsm[obsm][idx,1], s=2, facecolors=_color, edgecolors="none", alpha=1, label=_cluster)
        else:
            ax.scatter(adata.obsm[obsm][idx,0], adata.obsm[obsm][idx,1], s=2, facecolors=_color, edgecolors="none", alpha=1)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.sca(ax)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
    ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
    if print_legend:
        ax.legend(markerscale=5, edgecolor=colour.black)
    plt.savefig(outfile)

parser = argparse.ArgumentParser(
    prog="Integration of sc-RNAseq data",
    description="""From two samples of sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    perform integration on embedding dimensions, create clusters using leiden algorithm,
    and run UMAP algorithm. This programm allows to search cell evolutions between two experiments""",
    usage="python cluster.py [<args>]"
)

parser.add_argument(
    "--i1", "--infile1", "--infile-ref",
    dest="infile_ref",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="path to .h5ad file (including file) considering as reference sample"
)

parser.add_argument(
    "--i2", "--infile2", "--infile-interest",
    dest="infile_interest",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="path to .h5ad file (including file) considering as sample to integrate"
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
    "-l", "--label",
    dest="label",
    type=str,
    required=False,
    default=None,
    help="label used in `adata.obs` for characterizing sample, useful for plotting"
)

parser.add_argument(
    "-m", "--metric",
    dest="metric",
    type=str,
    required=False,
    default="euclidean",
    help="metric used for bbknn-based integration algorithm"
)

parser.add_argument(
    "-k", "--k-neighbors",
    dest="k_neighbors",
    type=int,
    required=False,
    default=20,
    help="number of closest neighbors computed when computing KNN graph"
)

parser.add_argument(
    "-i", "--dim-integration",
    dest="dim_integration",
    type=int,
    required=False,
    default=50,
    help="number of integrating embedding dimensions computed"
)

parser.add_argument(
    "-c", "--dim-clustering",
    dest="dim_clustering",
    type=int,
    required=False,
    default=15,
    help="number of principal components taken into account for clustering cells and running UMAP"
)

parser.add_argument(
    "-r", "--resolution",
    dest="resolution",
    type=float,
    required=False,
    default=0.6,
    help="parameter value controlling the coarseness of the clustering when using Leiden algorithm"
)

parser.add_argument(
    "-j", "--jobs",
    dest="n_jobs",
    type=int,
    required=False,
    default=1,
    help="number of process to use"
)

parser.add_argument(
    "-v", "--verbose",
    dest="verbose",
    type=str2bool,
    required=False,
    default=False,
    help="get information about running programm"
)

args = parser.parse_args()

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

if args.verbose:
    print("\tcomputation of reference sample embedding components...")
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

if args.verbose:
    print("\tintegration of interest sample")
sc.tl.ingest(
    adata=adata_d["interest"],
    adata_ref=adata_d["reference"],
    obs=None,
    embedding_method=["pca", "umap"],
    n_jobs=args.n_jobs
)
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

if args.verbose:
    print("\tPlot of embedding components")
scatterplot(
    concat_adata,
    obs="condition",
    obsm="X_pca",
    xlabel=r"$\mathrm{PC_{1}}$",
    ylabel=r"$\mathrm{PC_{2}}$",
    outfile=Path(f"{fig_outpath}/ingest_pca"),
)
scatterplot(
    concat_adata,
    obs="condition",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    outfile=Path(f"{fig_outpath}/ingest_umap"),
)
scatterplot(
    concat_adata,
    obs="cluster",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    outfile=Path(f"{fig_outpath}/ingest_umap_clusters"),
)

if args.verbose:
    print("\tSaving data...")
concat_adata.write_h5ad(filename=f"{data_outpath}/ingest.h5ad", compression="gzip")

print("Integration using bbknn...")

clean_adata(
    concat_adata,
    obs="cluster"
)

if args.verbose:
    print("\tcomputation of embedding components...")
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

if args.verbose:
    print("\tintegration of embedding components...")
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

if args.verbose:
    print("\tPlot of embedding components")
scatterplot(
    concat_adata,
    obs="condition",
    obsm="X_pca",
    xlabel=r"$\mathrm{PC_{1}}$",
    ylabel=r"$\mathrm{PC_{2}}$",
    outfile=Path(f"{fig_outpath}/bbknn_pca"),
)
scatterplot(
    concat_adata,
    obs="condition",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    outfile=Path(f"{fig_outpath}/bbknn_umap"),
)
scatterplot(
    concat_adata,
    obs="cluster",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    outfile=Path(f"{fig_outpath}/bbknn_umap_clusters"),
)

if args.verbose:
    print("\tSaving data...")
concat_adata.write_h5ad(filename=f"{data_outpath}/bbknn.h5ad", compression="gzip")

del concat_adata

print("Integration using scanorama...")

for key in adata_d.keys():
    clean_adata(adata_d[key])

adata_l = list(adata_d.values())
del adata_d

if args.verbose:
    print("\tcomputation of integrated embedding components...")
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

if args.verbose:
    print("\tPlot of embedding components")
scatterplot(
    concat_adata,
    obs="condition",
    obsm="X_scanorama",
    xlabel=r"$\mathrm{x_{1}^{\mathrm{scanorama}}}$",
    ylabel=r"$\mathrm{x_{2}^{\mathrm{scanorama}}}$",
    outfile=Path(f"{fig_outpath}/scanorama_components2"),
)
scatterplot(
    concat_adata,
    obs="condition",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    outfile=Path(f"{fig_outpath}/scanorama_umap2"),
)
scatterplot(
    concat_adata,
    obs="cluster",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    outfile=Path(f"{fig_outpath}/scanorama_umap_clusters2"),
)

if args.verbose:
    print("\tSaving data...")
concat_adata.write_h5ad(filename=f"{data_outpath}/scanorama.h5ad", compression="gzip")
