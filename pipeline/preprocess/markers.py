#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path
from utils.argtype import Store_prefix

import pandas as pd, scanpy as sc, json
import anndatatools as adt

parser = argparse.ArgumentParser(
    prog="Cell type analysis",
    description="""From sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    search for gene markers and compare markers and signatures in order to provide
    useful information about potential cell-types on each condition and each group.""",
    usage="python markers.py [-h] <FILE> <FILE> <PATH> -g <LITERAL> [-c <LITERAL> <args>]"
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="counting file (h5ad format)"
)

parser.add_argument(
    "signatures",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="file containing signatures (json format)"
)

parser.add_argument(
    "outpath",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="output path"
)

parser.add_argument(
    "-p", "--prefix",
    dest="prefix",
    action=Store_prefix,
    required=False,
    default="",
    metavar="LITERAL",
    help="prefix for each saving file"
)

parser.add_argument(
    "-c", "--condition",
    dest="condition",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="column name such as adata.obs[`LITERAL`] distinguishes samples"
)

parser.add_argument(
    "--cluster",
    dest="cluster",
    type=str,
    required=True,
    metavar="LITERAL",
    help="column name such as adata.obs[`LITERAL`] distinguishes cluster"
)

parser.add_argument(
    "-l", "--logfc-threshold",
    dest="logfc_threshold",
    type=float,
    required=False,
    default=0.25,
    metavar="FLOAT",
    help="threshold denoting the minimum log2 fold-changes being considered as a gene marker (default: 0.25)"
)

parser.add_argument(
    "-v", "--verbose",
    dest="verbose",
    required=False,
    action="store_true",
    help="display information about running programm"
)

args = parser.parse_args()

if not args.outpath.exists():
    os.makedirs(args.outpath)

print(f"Loading data...")

adata = sc.read_h5ad(args.infile)

print(f"Marker analysis...")

layer = "log-normalize"
if args.condition is None:
    adata_d = {"all": adata.copy()}
else:
    adata_d = {_condition: adata[adata.obs[args.condition] == _condition].copy() for _condition in sorted(adata.obs[args.condition].unique())}
markers_d = dict()
del adata

for _condition in sorted(adata_d.keys()):
    
    sc.tl.rank_genes_groups(
        adata_d[_condition],
        layer=layer,
        use_raw=False,
        groupby=args.cluster,
        reference="rest",
        method="wilcoxon",
        tie_correct=True,
        corr_method="bonferroni"
    )
    markers_d[_condition] = adt.tl.extract_rank_genes_groups(
        adata_d[_condition],
        logfc_keeping=False
    )
    markers_d[_condition] = markers_d[_condition].loc[markers_d[_condition]["adj_pvals"] < 0.05]
    markers_d[_condition] = adt.tl.update_logfoldchanges(
        df=markers_d[_condition],
        adata=adata_d[_condition],
        layer=layer,
        groupby=args.cluster,
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
        adt.tl.get_info(
            adata_d[_condition],
            signatures_d,
            markers_d[_condition],
            groupby=args.cluster
        ),
        orient="index"
    )

if args.condition is None:
    info_df = info_d["all"]
else:
    info_df = pd.concat(list(info_d.values()), keys=list(info_d.keys()))

print("Saving data...")

if args.condition is None:
    markers_d["all"].to_csv(f"{args.outpath}/{args.prefix}markers.csv", sep=",", index=False)
else:
    for _condition in markers_d.keys():
        markers_d[_condition].to_csv(f"{args.outpath}/{args.prefix}{_condition}_markers.csv", sep=",", index=False)
info_df.to_csv(f"{args.outpath}/{args.prefix}cluster_cell_types.csv", sep=",", index=True)
info_df.transpose().to_csv(f"{args.outpath}/{args.prefix}cluster_cell_types.transpose.csv", sep=",", index=True)

if args.verbose:
    print(info_df.transpose())
