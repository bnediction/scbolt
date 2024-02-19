#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import random
random.seed(100)

import os, argparse
from pathlib import Path

import scanpy as sc
import numpy as np
from sklearn.linear_model import LinearRegression

import matplotlib.pyplot as plt
from anndatatools.plotting import (
    fig,
    color
)

class Range(argparse.Action):
    
    def __init__(
        self,
        min=None,
        max=None,
        *args,
        **kwargs
    ):
        self.min = min
        self.max = max
        kwargs["metavar"] = f"[{self.min}-{self.max}]"
        super(Range, self).__init__(*args, **kwargs)

    def __call__(
        self,
        parser,
        namespace,
        value,
        option_string=None
    ):
        if not (self.min <= value <= self.max):
            raise argparse.ArgumentError(self, f"value {value} not in range [{self.min}-{self.max}].")
        setattr(namespace, self.dest, value)

def str2prefix(v: str):
    if v:
        v = v if v[-1] in ["-","_"] else v + "_"
    return v

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

    if sc.preprocessing._simple.issparse(counts):
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
    and correct batch effects.""",
    usage="python normalization.py -i <path> [<args>]"
)

parser.add_argument(
    "-i", "--infile",
    dest="infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="path to .h5ad file (including file)"
)

parser.add_argument(
    "-o", "--outpath",
    dest="outpath",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=Path("./").resolve(),
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "-p", "--prefix",
    dest="prefix",
    type=str2prefix,
    required=False,
    default="",
    metavar="LITERAL",
    help="prefix for each saving file"
)

parser.add_argument(
    "-c", "--correction",
    dest="correction",
    type=str,
    required=False,
    nargs="+",
    default=["G2M_score", "S_score", "G1_score"],
    metavar="LITERAL",
    help="batch effect to correct (ex: 'G2M_score+S_score+G1_score')"
)

parser.add_argument(
    "-m", "--min-cell-expression-proportion",
    dest="min_cell_expression_proportion",
    type=float,
    required=False,
    min=0,
    max=1,
    action=Range,
    default=0.001,
    metavar="[0-1]",
    help="remove gene for which the proportion of expressed cells is inferior to the given value (between 0 and 1, default=0.001)"
)

parser.add_argument(
    "-f", "--hvg-filtering",
    dest="hvg_filtering",
    required=False,
    action="store_true",
    help="remove highly variables genes (HVG)"
)

parser.add_argument(
    "-j", "--jobs",
    dest="n_jobs",
    type=int,
    required=False,
    default=1,
    metavar="INT",
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

print(f"Filtering genes...")

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
    plt.savefig(f"{fig_outpath}/gene-number.png")

adata.layers["raw"] = adata.X.copy()

print(f"Normalizing data...")

adata.layers["normalize"] = sc.pp.normalize_total(adata, target_sum=1e4, inplace=False)["X"]
adata.layers["log-normalize"] = adata.layers["normalize"].copy()
sc.pp.log1p(adata, base=np.exp(1), layer="log-normalize")

print(f"Selecting higly variable genes (HVG)...")

sc.pp.highly_variable_genes(adata, layer="raw", flavor="seurat_v3", span=0.3, n_bins=20, n_top_genes=2000, inplace=True)
if args.hvg_filtering:
    adata = adata[:, adata.var.highly_variable]

print(f"Scaling data...")

adata.layers["scale"] = adata.layers["log-normalize"].copy()
sc.pp.scale(adata, layer="scale", copy=False)

print(f"Correcting batch (unwanted) effects and scaling data...")

adata.layers["correct"] = regress_out(adata, args.correction, layer="log-normalize", intercept=False, n_jobs=args.n_jobs)
sc.pp.scale(adata, layer="correct")

print("Saving data...")

adata.write_h5ad(filename=f"{data_outpath}/{args.prefix}corrected.h5ad", compression="gzip")
