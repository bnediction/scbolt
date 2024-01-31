#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import random
random.seed(100)

import os, argparse
from pathlib import Path

import numpy as np, math

import pandas as pd, anndata as ad, scanpy as sc, json
import anndatatools as adt

import matplotlib.pyplot as plt, color_settings as colour, plot_settings
from matplotlib.ticker import FormatStrFormatter
from color_settings import color_cycle

class arguments:
    def __init__(
        self,
        infile=Path("data/scRNA/integration/tables/bbknn.h5ad"),
        signatures=Path("data/public/signatures/signatures.json"),
        outpath=Path("data/scRNA/markers"),
        group="leiden",
        condition="condition",
        logfc_threshold = 0.25,
        prefix=None,
        verbose=True,
    ):
        self.infile = infile
        self.signatures = signatures
        self.outpath = outpath
        self.condition = condition
        self.logfc_threshold = logfc_threshold
        self.prefix = prefix
        self.verbose = verbose
        self.group=group

args = arguments()

data_outpath = Path(f"{args.outpath}/tables")

if not data_outpath.exists():
    os.makedirs(data_outpath)

print(f"Loading data...")

adata = sc.read_h5ad(args.infile)

print(f"Marker analysis...")

layer = "log-normalize"
adata_d = {_condition: adata[adata.obs[args.condition] == _condition].copy() for _condition in sorted(adata.obs[args.condition].unique())}
markers_d = dict()
del adata

for _condition in sorted(adata_d.keys()):
    
    sc.tl.rank_genes_groups(
        adata_d[_condition],
        layer=layer,
        use_raw=False,
        groupby=args.group,
        reference="rest",
        method="wilcoxon",
        tie_correct=True,
        corr_method="bonferroni"
    )
    markers_d[_condition] = adt.extract_rank_genes_groups(
        adata_d[_condition],
        logfc_keeping=False
    )
    markers_d[_condition] = markers_d[_condition].loc[markers_d[_condition]["adj_pvals"] < 0.05]
    markers_d[_condition] = adt.update_logfoldchanges(
        df=markers_d[_condition],
        adata=adata_d[_condition],
        layer=layer,
        groupby=args.group,
        is_log=True,
        cluster_rebalancing=False,
        threshold=args.logfc_threshold
    )

print(f"Signature analysis...")

with open(args.signatures, "r") as signatures_f:
    signatures_d = json.load(signatures_f)

valid_gene_names = set(next(iter(adata_d.values())).var_names)
for cell_type, signature in signatures_d.items():
    signatures_d[cell_type] = {gene for gene in signature if gene in valid_gene_names}
signatures_d = {cell_type: signature for cell_type, signature in signatures_d.items() if signature}
del valid_gene_names

for adata in adata_d.values():
    layer="log-normalize"
    adata.X = adata.layers[layer]
    for cell_type, signature in signatures_d.items():
        sc.tl.score_genes(
            adata,
            gene_list=signature,
            gene_pool=None,
            n_bins=25,
            ctrl_size=100,
            score_name=cell_type,
            random_state=0,
            copy=False,
            use_raw=False
        )

print("Summarizing clusters...")

info_d = dict()

for _condition in sorted(adata_d.keys()):
    info_d[_condition] = pd.DataFrame.from_dict(
        adt.get_info(
            adata_d[_condition],
            signatures_d,
            markers_d[_condition],
            groupby=args.group
        ),
        orient="columns"
    )

info_df = pd.concat(list(info_d.values()), keys=list(info_d.keys()))

print("Saving data...")

for _condition in markers_d.keys():
    markers_d[_condition].to_csv(f"{data_outpath}/{args.prefix}{_condition}_markers.csv", sep=",", index=False)
info_df.to_csv(f"{data_outpath}/{args.prefix}cluster_cell_types.csv", sep=",", index=True)

if args.verbose:
    print(info_df.transpose())
