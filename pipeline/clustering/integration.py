#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
import pickle
from pathlib import Path
from utils.stdout import print_task, print_info
from utils.argtype import Required_length

from typing import Sequence

from collections import OrderedDict as odict

import anndata as ad, anndatatools as adt
import scanpy as sc
import scanorama

import matplotlib.pyplot as plt
from anndatatools.plotting import color

@adt.adata_checker
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

        return adata if copy else None

parser = argparse.ArgumentParser(
    prog="single-cell integration and clustering",
    description="""perform integration on embedding dimensions, create clusters using leiden algorithm,
    and run UMAP algorithm. This programm allows to search cell evolutions between two experiments""",
    usage="""python integration.py [-h] <FILE> <FILE> <PATH> [<args>]"""
)

parser.add_argument(
    "infiles",
    type=lambda x: Path(x).resolve(),
    action=Required_length,
    min=2,
    metavar="FILE",
    help="input files, first one being considered as reference (h5ad format)"
)

parser.add_argument(
    "-o", "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="integrated file (h5ad format)"
)

parser.add_argument(
    "--labels",
    dest="labels",
    type=str,
    required=False,
    action=Required_length,
    min=2,
    default=None,
    metavar="LITERAL",
    help="labels used for characterizing samples, ordered with infiles"
)

parser.add_argument(
    "--method",
    dest="method",
    type=str,
    required=False,
    default="bbknn",
    choices=["bbknn", "ingest", "scanorama"],
    metavar="[bbknn | ingest | scanorama]",
    help="integration method to use (default: bbknn)"
)

parser.add_argument(
    "--layer",
    dest="layer",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="layer used (if not specified, use adata.X)"
)

parser.add_argument(
    "-p", "--dim-pca",
    dest="dim_pca",
    type=int,
    required=False,
    default=50,
    metavar="INT",
    help="number of principal components (default: 50)"
)

parser.add_argument(
    "-c", "--dim-clustering",
    dest="dim_clustering",
    type=int,
    required=False,
    default=15,
    metavar="INT",
    help="number of principal components taken into account for clustering cells (default: 15)"
)

parser.add_argument(
    "-u", "--dim-umap",
    dest="dim_umap",
    type=int,
    required=False,
    default=2,
    metavar="INT",
    help="number of embedding dimensions (default: 2)"
)

parser.add_argument(
    "-z", "--zero-center",
    dest="zero_center",
    required=False,
    action="store_true",
    help="compute standard PCA from covariance matrix if `True`, otherwise omit zero-centering variables"
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    type=int,
    required=False,
    default=None,
    metavar="INT",
    help="select the most variable genes for dimension reduction (default: None)"
)

parser.add_argument(
    "-m", "--metric",
    dest="metric",
    type=str,
    required=False,
    default="euclidean",
    metavar="METRIC",
    help="metric used for knn and bbknn-based integration algorithms (default: euclidean)"
)

parser.add_argument(
    "-k", "--k-neighbors",
    dest="k_neighbors",
    type=int,
    required=False,
    default=20,
    metavar="INT",
    help="number of closest neighbors computed when performing KNN graph (default: 20)"
)

parser.add_argument(
    "-r", "--resolution",
    dest="resolution",
    type=float,
    required=False,
    default=0.6,
    metavar="FLOAT",
    help="parameter value controlling the coarseness of the clustering when using Leiden algorithm (default: 0.6)"
)

parser.add_argument(
    "--add-legend",
    dest="legend",
    required=False,
    action="store_true",
    help="add legend to figures"
)

parser.add_argument(
    "--plot-3d",
    dest="plot_3d",
    required=False,
    action="store_true",
    help="plot figures in three dimensions"
)

parser.add_argument(
    "-j", "--jobs",
    dest="n_jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of process to use (default: 1)"
)

parser.add_argument(
    "-s", "--seed",
    dest="seed",
    type=int,
    required=False,
    default=0,
    metavar="FLOAT",
    help="random number generator"
)

parser.add_argument(
    "-v", "--verbose",
    dest="verbose",
    required=False,
    action="store_true",
    help="display information about running programm"
)

args = parser.parse_args()

if not (args.dim_pca >= args.dim_clustering > args.dim_umap):
    raise argparse.ArgumentError(
        f"invalid values for arguments: pca dimension >= clustering dimension > umap dimension not satisfied"
    )

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

if args.labels:
    labels = args.labels
else:
    labels = ["reference"]
    labels.extend([f"interest_{i}" for i in range(1,len(args.infiles))])

print_task("data loading")

adata_d = odict()
for i, label in enumerate(labels):
    adata_d[label] = ad.read_h5ad(args.infiles[i])
    clean_adata(adata_d[label])
    if i == 0:
        valid_genes = set(adata_d[label].var.index)
    else:
        valid_genes = valid_genes.intersection(set(adata_d[label].var.index))

valid_genes = list(valid_genes)

for k in adata_d.keys():
    if args.layer:
        adata_d[k].X = adata_d[k].layers[args.layer]
    adata_d[k] = adata_d[k][:,valid_genes]

del valid_genes

if args.method=="ingest":

    print_info("integration using ingest algorithm")

    if args.hvg is not None:
        print_task("highly variable gene selection")
        for k in adata_d.keys():
            sc.pp.highly_variable_genes(
                adata_d[k],
                layer="raw",
                flavor="seurat_v3",
                span=0.3,
                n_bins=20,
                n_top_genes=args.hvg,
                inplace=True
            )
    else:
        print_info("no highly variable gene selection")

    print_task("pca computation (reference sample)")
    sc.tl.pca(
        adata_d[labels[0]],
        zero_center=args.zero_center,
        n_comps=args.dim_pca,
        use_highly_variable=True if args.hvg is not None else False,
        copy=False
    )

    print_task("knn computation (reference sample)")
    sc.pp.neighbors(
        adata_d[labels[0]],
        n_neighbors=args.k_neighbors,
        n_pcs=args.dim_clustering,
        copy=False
    )

    print_task("umap computation (reference sample)")
    sc.tl.umap(
        adata_d[labels[0]],
        n_components=args.dim_umap,
        random_state=args.seed
    )

    print_task("pca and umap integration")
    for _label in labels[1:]:
        sc.tl.ingest(
            adata=adata_d[_label],
            adata_ref=adata_d[labels[0]],
            obs=None,
            embedding_method=["pca", "umap"],
            inplace=True,
            n_jobs=args.n_jobs
        )
    try:
        adata = ad.concat(
            adatas=list(adata_d.values()),
            join="inner",
            label="condition",
            keys=list(adata_d.keys()),
            merge="same",
            uns_merge="same"
        )
    except:
        raise RuntimeError("Anndatas concatenation did not work")

    print_task("knn computation (integrated)")
    sc.pp.neighbors(
        adata,
        n_neighbors=args.k_neighbors,
        use_rep="X_pca",
        n_pcs=args.dim_clustering,
        metric=args.metric,
        copy=False
    )

    print_task("leiden clustering (integrated)")
    sc.tl.leiden(
        adata,
        resolution=args.resolution,
        key_added=f"leiden"
    )

elif args.method=="bbknn":

    print_info("integration using bbknn algorithm")

    if "adata" not in globals():
        try:
            adata = ad.concat(
                list(adata_d.values()),
                join="inner",
                label="condition",
                keys=list(adata_d.keys()),
                merge="same",
                uns_merge="same"
            )
        except:
            raise RuntimeError("Anndatas concatenation did not work, aborting")

    clean_adata(
        adata,
        obs="leiden"
    )

    if args.hvg:
        print_task("highly variable genes estimation")
        sc.pp.highly_variable_genes(
            adata,
            layer="raw",
            flavor="seurat_v3",
            span=0.3,
            n_bins=20,
            n_top_genes=args.hvg,
            inplace=True
        )
    else:
        print_info("no highly variable genes estimation")

    print_task("pca computation")
    sc.tl.pca(
        adata,
        zero_center=args.zero_center,
        n_comps=args.dim_pca,
        use_highly_variable=True if args.hvg is not None else False,
        copy=False
    )

    print_task("knn integration")
    sc.external.pp.bbknn(
        adata,
        batch_key="condition",
        use_rep="X_pca",
        metric=args.metric,
        copy=False,
        neighbors_within_batch=args.k_neighbors,
        n_pcs=args.dim_clustering,
    )

    print_task("umap computation (integrated)")
    sc.tl.umap(
        adata,
        n_components=args.dim_umap,
        random_state=args.seed
    )

    print_task("knn computation (integrated)")
    sc.pp.neighbors(
        adata,
        n_neighbors=args.k_neighbors,
        use_rep="X_pca",
        n_pcs=args.dim_clustering,
        metric=args.metric,
        copy=False
    )

    print_task("leiden clustering (integrated)")
    sc.tl.leiden(
        adata,
        resolution=args.resolution,
        key_added=f"leiden"
    )

elif args.method=="scanorama":

    print_info("integration using scanorama algorithm")

    for k in adata_d.keys():
        clean_adata(adata_d[k])
    adata_l = list(adata_d.values())
    del adata_d

    print_task("pca integration")
    adata_l = scanorama.correct_scanpy(
        adata_l,
        dimred=args.dim_pca,
        return_dimred=True
    )
    try:
        adata = ad.concat(
            adata_l,
            join="inner",
            label="condition",
            keys=labels,
            merge="same",
            uns_merge="same"
        )
        del adata_l
    except:
        raise RuntimeError("Anndatas concatenation did not work")

    print_task("knn computation (integrated)")
    sc.pp.neighbors(
        adata,
        n_neighbors=args.k_neighbors,
        use_rep="X_scanorama",
        n_pcs=args.dim_clustering,
        copy=False
    )
    adata.obsm["X_pca"] = adata.obsm["X_scanorama"]

    print_task("leiden clustering (integrated)")
    sc.tl.leiden(
        adata,
        resolution=args.resolution,
        key_added=f"leiden"
    )

    print_task("umap computation (integrated)")
    sc.tl.umap(
        adata,
        n_components=args.dim_umap,
        random_state=args.seed
    )

print_task("embedding component plotting")

adt.pl.embedding_plot(
    adata,
    obs="condition",
    obsm="X_pca",
    xlabel=r"$\mathrm{PC_{1}}$",
    ylabel=r"$\mathrm{PC_{2}}$",
    outfile=Path(f"{os.path.dirname(args.outfile)}/pca"),
    add_legend=args.legend,
    s=2,
    alpha=1,
    lgd_params={
        "title":"conditions",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":color.black,
        "shadow":False,
        "loc":"best"
    }
)
for obs in ["condition", "leiden"]:
    fig, _ = adt.pl.embedding_plot(
        adata,
        obs=obs,
        obsm="X_umap",
        xlabel=r"$\mathrm{UMAP_{1}}$",
        ylabel=r"$\mathrm{UMAP_{2}}$",
        zlabel=r"$\mathrm{UMAP_{3}}$",
        add_legend=args.legend,
        s=2,
        alpha=1,
        lgd_params={
            "title":"clusters" if obs != "condition" else "conditions",
            "ncol":1,
            "markerscale":5,
            "frameon":True,
            "edgecolor":color.black,
            "shadow":False
        },
        n_components = 3 if args.dim_umap > 2 and args.plot_3d is True else 2,
        background_visible=False
    )
    plt.savefig(f"{os.path.dirname(args.outfile)}/umap_{obs}.pdf")
    if args.dim_umap > 2 and args.plot_3d:
        f"{os.path.dirname(args.outfile)}/umap_{obs}.pdf"
        pickle.dump(fig, open(f"{os.path.dirname(args.outfile)}/umap_{obs}.fig.pkl", "wb"))

print_task("data saving")

adata.write_h5ad(filename=args.outfile, compression="gzip")
