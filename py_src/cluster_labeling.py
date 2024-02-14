#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import os, argparse
import pickle
from pathlib import Path

import anndata as ad, anndatatools as adt

import matplotlib.pyplot as plt
import color_settings as colour

class Store_dict(argparse.Action):

    def __init__(
        self,
        typevar: type = str,
        *args,
        **kwargs
    ):
        if typevar == str:
            strvar = "LITERAL"
        else:
            strvar = typevar.__name__.upper()
        kwargs["metavar"] = f"{strvar}={strvar}"
        super(Store_dict, self).__init__(*args, **kwargs)

    def __call__(
        self,
        parser,
        namespace,
        values,
        option_string=None
    ):
        setattr(namespace, self.dest, dict())
        for value in values:
            key, value = value.split("=")
            getattr(namespace, self.dest)[key] = value

def str2prefix(v: str):
    if v is None:
        v = ""
    elif isinstance(v, str):
        if v:
            v = v if v[-1] in ["-","_"] else v + "_"
    else:
        raise argparse.ArgumentTypeError("String value expected.")
    return v

parser = argparse.ArgumentParser(
    prog="labeling of clusters",
    description="""From sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    rename labels using user-defined names.""",
    usage="""python cluster_labeling.py [-h] -i <PATH> -c <LITERAL> -n <LITERAL=LITERAL [LITERAL=LITERAL ...]> [<args>]"""
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
    help="output path (default: ./)"
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
    "-c", "--column",
    dest="column",
    type=str,
    required=True,
    metavar="LITERAL",
    help="name of the column in adata.obs from which user want to redifine category names."
)

parser.add_argument(
    "-n", "--name",
    dest="labels",
    required=True,
    nargs="+",
    action=Store_dict,
    help="mapping between old and new names for labels"
)

parser.add_argument(
    "--obsm",
    dest="obsm",
    required=False,
    default=None,
    metavar="LITERAL",
    help="""ndarray name stored in .obsm[`obsm`] used for plotting figure."""
)

parser.add_argument(
    "--plot-3d",
    dest="plot_3d",
    required=False,
    action="store_true",
    help="plot figures in three dimensions"
)

args = parser.parse_args()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

print(f"Loading data...")
adata = ad.read_h5ad(args.infile)

print(f"Rename categories...")
if args.column not in adata.obs:
    raise KeyError(f"adata.obsm[`{args.column}`] does not exist.")
elif not hasattr(adata.obs[args.column], "cat"):
    raise ValueError("values in adata.obs[`{args.column}`] are not derived from a Categorical type.")
else:
    adata.obs[args.column] = adata.obs[args.column].cat.rename_categories(args.labels)

print("Saving data...")
adata.write_h5ad(filename=f"{data_outpath}/{args.prefix}cluster_labels.h5ad", compression="gzip")
