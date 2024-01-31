#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import argparse
from pathlib import Path

import pandas as pd, scanpy as sc, json
import anndatatools as adt

def str2prefix(v: str):
    if v is None:
        return ""
    elif isinstance(v, str):
        if v:
            v = v if v[-1] in ["-","_"] else v + "_"
        return v
    else:
        raise argparse.ArgumentTypeError("String value expected.")

def str2bool(v: str):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")

parser = argparse.ArgumentParser(
    prog="Cell type analysis of sc-RNAseq data",
    description="""From sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    search for gene markers and compare markers and signatures in order to provide
    useful information about potential cell-types on each condition and each group.""",
    usage="python markers.py [<args>]"
)

parser.add_argument(
    "-i", "--infile",
    dest="infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="path to .h5ad file (including file)"
)

parser.add_argument(
    "-s", "--signatures",
    dest="signatures",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="path to .json signatures file (including file)"
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
    "-c", "--condition",
    dest="condition",
    type=str,
    required=True,
    help="column name in adata.obs distinguishing samples"
)

parser.add_argument(
    "-g", "--group", "--cluster",
    dest="group",
    type=str,
    required=True,
    help="column name in adata.obs distinguishing cluster"
)

parser.add_argument(
    "-p", "--prefix",
    dest="prefix",
    type=str2prefix,
    required=False,
    default="",
    help="prefix for each saving file"
)

parser.add_argument(
    "-l", "--logfc-threshold",
    dest="logfc_threshold",
    type=float,
    required=False,
    default=0.25,
    help="threshold describing the minimum log2 fold-changes for being a gene marker"
)

parser.add_argument(
    "-v", "--verbose",
    dest="verbose",
    type=str2bool,
    required=False,
    default=False,
    help="get summarizing information about cluster in stdout"
)

args = parser.parse_args()

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
        orient="index"
    )

info_df = pd.concat(list(info_d.values()), keys=list(info_d.keys()))

print("Saving data...")

for _condition in markers_d.keys():
    markers_d[_condition].to_csv(f"{args.outpath}/{args.prefix}{_condition}_markers.csv", sep=",", index=False)
info_df.to_csv(f"{args.outpath}/{args.prefix}cluster_cell_types.csv", sep=",", index=True)

if args.verbose:
    print(info_df)
