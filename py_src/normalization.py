#!/usr/bin/python3

import os
from pathlib import Path

import matplotlib.pyplot as plt, color_settings as colour, plot_settings

import scanpy as sc

import numpy as np, scipy
from sklearn.linear_model import LinearRegression

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
    "n_jobs":6
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

print(f"Normalizing Data...")

sc.pp.normalize_total(adata, target_sum=1e4, inplace=True)
sc.pp.log1p(adata)

print(f"Correcting batch (unwanted) effects...")

corrected_ad = adata.copy()
corrected_ad = regress_out(corrected_ad, correction, intercept=False, n_jobs=args["n_jobs"])
sc.pp.scale(corrected_ad)
corrected_ad.write_h5ad(filename=f"{data_outpath}/corrected_{args['suffix']}", compression="gzip")

