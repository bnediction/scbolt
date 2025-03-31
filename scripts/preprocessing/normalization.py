#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import random
random.seed(100)

import os, argparse
from pathlib import Path
from utils.argtype import Range
from utils.stdout import print_task

import scanpy as sc
import numpy as np
from sklearn.linear_model import LinearRegression

import matplotlib.pyplot as plt
from bonesistools.anndatatools.plotting import (
    fig,
    color
)

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

def regress_out(adata, correction, layer=None, intercept=False, n_jobs=1):

    if layer is None:
        counts = adata.X.copy()
    else:
        counts = adata.layers[layer].copy()

    if sc.pp._simple.issparse(counts):
        counts = counts.toarray()
    regressors = adata.obs[correction]
    regressors.insert(0, 'ones', 1.0)
    regressors = regressors.to_numpy()

    for i in range(adata.n_vars):
        interest = counts[:,i].reshape(-1, 1)
        corrected_interest = regress_out_feature(interest, regressors, intercept=intercept, n_jobs=n_jobs)
        counts[:,i] = corrected_interest
    
    return counts

parser = argparse.ArgumentParser(
    prog="Normalization of sc-RNAseq data",
    description="""From one-condition sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    filter low-quality genes (gene poorly expressed and no HVG),
    normalize data with respect to the depth library, scale data
    and correct unwanted effects.""",
    usage="python normalization.py <FILE> <PATH> [<args>]"
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="counting file (h5ad format)"
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="normalized counting file (h5ad format)"
)

parser.add_argument(
    "-c", "--correction",
    dest="correction",
    type=str,
    required=False,
    nargs="+",
    default=["G2M_score", "S_score", "G1_score"],
    metavar="LITERAL",
    help="unwanted effects to correct (default = [`G2M_score`, `S_score`, `G1_score`])"
)

parser.add_argument(
    "-m", "--min-cell-expression-proportion",
    dest="min_cell_expression_proportion",
    type=float,
    action=Range,
    min=0,
    max=1,
    required=False,
    default=0.001,
    help="remove genes for which the proportion of expressed cells is inferior to the given value (default = 0.001)"
)

parser.add_argument(
    "-f", "--hvg-filtering",
    dest="hvg_filtering",
    required=False,
    action="store_true",
    help="remove highly variable genes (HVG)"
)

parser.add_argument(
    "-j", "--jobs",
    dest="n_jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
    help="number of allocated processors"
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

print_task("data loading")

adata = sc.read_h5ad(args.infile)

print_task("gene filtering")

if args.min_cell_expression_proportion:

    _k = [adata.n_vars]

    threshold = args.min_cell_expression_proportion*adata.n_obs
    sc.pp.filter_genes(data=adata, min_cells=threshold)

    _k.append(adata.n_vars)

    fig, ax = plt.subplots(nrows=1, ncols=1)
    plt.bar(
        ["before filtering", "after filtering"], _k,
        width=0.8,
        linewidth=2,
        color=color.pink,
        edgecolor=color.red
    )
    ax.update({"xmargin": 0.1})
    plt.savefig(f"{os.path.dirname(args.outfile)}/gene-number.pdf")

adata.layers["raw"] = adata.X.copy()

print_task("data normalisation")

adata.layers["normalize"] = sc.pp.normalize_total(adata, target_sum=1e4, inplace=False)["X"]
adata.layers["log-normalize"] = adata.layers["normalize"].copy()
sc.pp.log1p(adata, base=np.exp(1), layer="log-normalize")

print_task("selecting higly variable genes (HVG)")

sc.pp.highly_variable_genes(adata, layer="raw", flavor="seurat_v3", span=0.3, n_bins=20, n_top_genes=2000, inplace=True)
if args.hvg_filtering:
    adata = adata[:, adata.var.highly_variable]

print_task("data scaling")

adata.layers["scale"] = adata.layers["log-normalize"].copy()
sc.pp.scale(adata, layer="scale", copy=False)

print_task("unwanted effects correction and data scaling")

adata.layers["correct"] = regress_out(adata, args.correction, layer="log-normalize", intercept=False, n_jobs=args.n_jobs)
sc.pp.scale(adata, layer="correct")

print_task("data saving")

adata.write_h5ad(filename=f"{args.outfile}", compression="gzip")
