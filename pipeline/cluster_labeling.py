#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import os, argparse
from pathlib import Path

import anndata as ad

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
    usage="""python cluster_labeling.py [-h] -i <PATH> -o <PATH> -c <LITERAL> -n <LITERAL=LITERAL [LITERAL=LITERAL ...]> [<args>]"""
)

parser.add_argument(
    "-i", "--infile",
    dest="infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="path to .h5ad infile (including file)"
)

parser.add_argument(
    "-o", "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="path to .h5ad outfile (including file)"
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

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

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
adata.write_h5ad(filename=args.outfile, compression="gzip")
