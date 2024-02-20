#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import importlib

import os, argparse
import json, pickle
from pathlib import Path

import anndata as ad, anndatatools as adt

import matplotlib.pyplot as plt
from anndatatools.plotting import fig

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
                raise KeyError("key `eval` in json file must contains only strings and lists")

parser = argparse.ArgumentParser(
    prog="figure plotting",
    description="""From sc-rnaSeq data recorded in the hdf5 format (<filename>.h5ad),
    plot figure using a json file.""",
    usage="""python [-i <PATH> -o <PATH>] -j <PATH>"""
)

parser.add_argument(
    "-i", "--infile",
    dest="infile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="PATH",
    help="path to .h5ad file (including file)"
)

parser.add_argument(
    "-o", "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="PATH",
    help="path to figure file (including file)"
)

parser.add_argument(
    "-j", "--json",
    dest="jsonfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="figure parameters based on syntax of anndata.scatterplot"
)

args = parser.parse_args()

with open(args.jsonfile) as file:
    params = json.load(file)

if args.infile is not None:
    infile = args.infile
elif "infile" in params:
    infile = Path(params["infile"])
else:
    raise argparse.ArgumentError("infile must be must called with --infile or specified in json file")

if args.outfile is not None:
    outfile = args.outfile
elif "outfile" in params:
    outfile = Path(params["outfile"])
else:
    raise argparse.ArgumentError("outfile must be must called with --outfile or specified in json file")

if not outfile.exists():
    os.makedirs(outfile)

adata = ad.read_h5ad(infile)

if "modules" in params:
    for module in params["modules"]:
        if isinstance(module, str):
            importlib.import_module(module)
        elif isinstance(module, dict):
            for name, alias in module.items():
                import_module_as(name, alias)

if "eval" in params:
    do_eval(params["eval"], params["figure"])

fig, ax = adt.pl.embedding_plot(
    adata,
    **params["figure"]
)
adt.pl.set_default(ax)
#plt.grid(False)
#plt.axis('off')
plt.savefig(outfile)
if "n_components" in params["figure"]:
    if params["figure"]["n_components"] == 3:
        pickle.dump(fig, open(Path(f"{outfile}.fig.pickle"), "wb"))
plt.close()