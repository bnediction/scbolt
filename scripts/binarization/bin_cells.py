#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path

import pickle

import anndata as ad
import bonesistools as bt

import numpy as np

from scboolseq import scBoolSeq

import matplotlib.pyplot as plt

bt.adt.pl.set_default_params()

parser = argparse.ArgumentParser(
    prog="cell binarization",
    description="""compute cell-related binarization from single-cell sequencing data, \
    using scBoolSeq method (see Magaña López et al. (2023): <https://hal.science/hal-04294917/>).""",
    usage=""""python bin_cells.py [-h] <FILE...> -o <PATH> -c <LITERAL> [<args>]"""
)

parser.add_argument(
    dest="infiles",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="input file(s) (h5ad format)"
)

parser.add_argument(
    "-o", "--outpath",
    dest="outpath",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="output path (storing cell_bin.csv, statistics.csv and bin.h5ad)"
)

parser.add_argument(
    "-c", "--cluster",
    dest="groupby",
    type=str,
    required=True,
    nargs="+",
    metavar="LITERAL",
    help="clusters retrieving from adata.obs[`cluster`] used for cluster-related binarization"
)

parser.add_argument(
    "--conditions",
    dest="conditions",
    type=str,
    required=False,
    action=bt.utils.cmd.Required_length,
    min=2,
    metavar="LITERAL",
    default=None,
    help="condition related to each dataset (ordered with h5ad files)",
)

parser.add_argument(
    "-e", "--exclude",
    dest="exclude",
    type=str,
    required=False,
    nargs="+",
    metavar="LITERAL",
    help="cluster names to remove for cluster-related binarization"
)

parser.add_argument(
    "-l", "--layer",
    dest="layer",
    type=str,
    required=False,
    default="log-normalize",
    metavar="LITERAL",
    help="layer used for binarization (default: `log-normalize`)"
)

parser.add_argument(
    "--hvg",
    dest="hvg",
    required=False,
    action="store_true",
    help="select the most variable genes for binarization"
)

parser.add_argument(
    "--zeroes_are_zeroes",
    dest="zeroes_are_zeroes",
    required=False,
    action="store_true",
    help="""when zero-inflated is inferred for a gene-related distribution:
    if its counting with respect to a cell is equal to zero, binarize to zero"""
)

args = parser.parse_args()

scbool = scBoolSeq(
    margin_quantile = 0.10,
    zeroinf_binarizer = "zero_or_not",
    zeroes_are = 0 if args.zeroes_are_zeroes else np.nan
)

if not args.outpath.exists():
    os.makedirs(args.outpath)

bt.utils.std.print_task("data loading")

adatas = [ad.read_h5ad(infile) for infile in args.infiles]

for i in range(len(adatas)):
    adatas[i].var_names_make_unique()

if len(args.infiles) > 1:
    if args.conditions is None:
        raise argparse.ArgumentError(None, "option --condition must be specified when using multiple infiles")
    elif len(args.infiles) != len(args.conditions):
        raise argparse.ArgumentError(None, "infiles and --condition require the same number of values")
    else:
        try:
            adata = ad.concat(
                adatas,
                axis=0,
                label="condition",
                keys=args.conditions,
                merge="first",
                uns_merge="same"
            )
#            adata.obs_names_make_unique() ### handle issue when there are identical barcodes between anndata
        except:
            raise RuntimeError("Anndatas concatenation did not work, aborting")
else:
    adata = adatas[0]

del adatas

if args.hvg is True:
    bt.utils.std.print_task("selecting highly variable genes")
    if "highly_variable" in adata.var:
        del adata.var["highly_variable"]
    from scanpy import preprocessing
    preprocessing.highly_variable_genes(adata, layer="raw", flavor="seurat_v3", span=0.3, n_bins=20, n_top_genes=2000, inplace=True)
    adata = adata[:,adata.var["highly_variable"]]
else:
    bt.utils.std.print_info("not selecting highly variable genes")

gene_list = adata.var.index
counts_df = bt.adt.tl.anndata_to_dataframe(adata, layer=args.layer)

bt.utils.std.print_task("data binarization")

bt.utils.std.print_info("inferring estimators")
with bt.utils.std.disable_print():
    scbool.fit(counts_df, simulation=False)

bt.utils.std.print_info("estimating boolean values by cell")
with bt.utils.std.disable_print():
    cell_df = scbool.binarize(counts_df)
    adata.layers["bin"] = cell_df
    adata.obs["pct_bin"] = (~cell_df.isna()).mean(axis=1)
    adata.var["distribution"] = scbool.criteria_["Category"]

bt.stdout.print_task("plotting")
fig, _ = bt.adt.pl.embedding_plot(
    adata,
    obs="pct_bin",
    obsm="X_umap",
    xlabel=r"$\mathrm{UMAP_{1}}$",
    ylabel=r"$\mathrm{UMAP_{2}}$",
    zlabel=r"$\mathrm{UMAP_{3}}$",
    add_legend=True,
    figwidth=6,
    s=3,
    alpha=1,
    lgd_params={
        "title":r"$\% \mathrm{bin}$",
        "ncol":1,
        "markerscale":5,
        "frameon":True,
        "edgecolor":bt.adt.pl.get_color("black"),
        "shadow":False
    },
    n_components = 3 if adata.obsm["X_umap"].shape[1] > 2 else 2,
    background_visible=False
)
plt.savefig(Path(f"{args.outpath}/pct_bin.pdf"))

bt.stdout.print_task("data saving")

cell_df.to_csv(f"{args.outpath}/binarized_cells.csv", sep=",", index=True)
scbool.criteria_.to_csv(f"{args.outpath}/statistics.csv", sep=",", index=True)
adata.write_h5ad(filename=f"{args.outpath}/bin.h5ad", compression="gzip")

with open(Path(f"{args.outpath}/scboolseq.pkl"), "wb") as file:
    pickle.dump(scbool, file)
