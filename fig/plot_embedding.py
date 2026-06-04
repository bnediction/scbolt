#!/usr/bin/python3

import importlib

import os
import argparse
import json
from pathlib import Path

import anndata as ad
from bonesistools import sctools as sct

import matplotlib.pyplot as plt

import warnings
warnings.filterwarnings("ignore")

sct.pl.set_default_params()


def import_module_as(module, alias):
    module = importlib.import_module(module)
    globals()[alias] = module


def do_eval(_eval_params, _figure_params):
    if isinstance(_eval_params, str):
        _figure_params[_eval_params] = eval(_figure_params[_eval_params])
    else:
        for _eval in _eval_params:
            if isinstance(_eval, str):
                _figure_params[_eval] = eval(_figure_params[_eval])
            elif isinstance(_eval, list):
                do_eval(_eval[1:], _figure_params[_eval[0]])
            else:
                raise KeyError(
                    "key `eval` in json file must contains only strings and lists"
                )


parser = argparse.ArgumentParser(
    prog="figure plotting",
    description="""plot figure from anndata object""",
    usage="""python <PATH> [--infile <PATH> --outfile <PATH>]""",
)

parser.add_argument(
    dest="jsonfile",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="figure parameters based on syntax of anndata.scatterplot",
)

parser.add_argument(
    "--infile",
    dest="infile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="PATH",
    help="path to .h5ad file (including file)",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="PATH",
    help="path to figure file (including file)",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="Column name in scdata.obs for annotation of observations",
)

parser.add_argument(
    "--use-rep",
    dest="use_rep",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help="embedding projection",
)

args = parser.parse_args()

with open(args.jsonfile) as file:
    params = json.load(file)

if args.infile is not None:
    infile = args.infile
elif "infile" in params:
    infile = Path(params["infile"])
else:
    raise argparse.ArgumentError(
        "infile must be must called with --infile or specified in json file"
    )

if args.outfile is not None:
    outfile = args.outfile
elif "outfile" in params:
    outfile = Path(params["outfile"])
else:
    raise argparse.ArgumentError(
        "outfile must be must called with --outfile or specified in json file"
    )

if not Path(os.path.dirname(outfile)).exists():
    os.makedirs(os.path.dirname(outfile))

adata = ad.read_h5ad(infile)

if "modules" in params:
    for module in params["modules"]:
        if isinstance(module, str):
            globals()[module] = importlib.import_module(module)
        elif isinstance(module, dict):
            for name, alias in module.items():
                import_module_as(name, alias)

if "eval" in params:
    do_eval(params["eval"], params["figure"])

if args.obs:
    params["figure"]["obs"] = args.obs

if args.use_rep:
    params["figure"]["use_rep"] = args.use_rep

if "n_components" not in params["figure"]:
    params["figure"]["n_components"] = (
        3 if adata.obsm[params["figure"]["use_rep"]].shape[1] > 2 else 2
    )

fig, ax = sct.pl.embedding_plot(adata, **params["figure"])

sct.pl.set_default_axis(ax)
if "grid" in params:
    plt.grid(params["grid"])
if "axis" in params:
    plt.axis(params["axis"])
plt.savefig(outfile, bbox_inches="tight", pad_inches=0.3)
plt.close()
try:
    os.system(f"pdfcrop --margins '0 0 0 0' {outfile} {outfile} > {os.devnull}")
except OSError:
    print("unavailable unix command 'pdfcrop': no figure trimming")
