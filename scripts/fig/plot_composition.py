#!/usr/bin/python3

import argparse
import json
import os
from pathlib import Path

import anndata as ad
import std
from bonesistools import sctools as sct

import matplotlib.pyplot as plt


std.set_default_plot_params(sct.pl)


parser = argparse.ArgumentParser(
    prog="composition plotting",
    description="plot composition figure from anndata object",
    usage="python <PATH> --infile <PATH> --outfile <PATH> --obs <LITERAL> --groupby <LITERAL>",
)

parser.add_argument(
    dest="jsonfile",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="composition figure parameters",
)

parser.add_argument(
    "--infile",
    dest="infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="path to .h5ad file",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="path to figure file",
)

parser.add_argument(
    "--obs",
    dest="obs",
    type=str,
    required=True,
    metavar="LITERAL",
    help="observation column defining stacked segments",
)

parser.add_argument(
    "--groupby",
    dest="groupby",
    type=str,
    required=True,
    metavar="LITERAL",
    help="observation column defining bars",
)

args = parser.parse_args()

with open(args.jsonfile) as file:
    params = json.load(file)

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(os.path.dirname(args.outfile))

adata = ad.read_h5ad(args.infile)
figure_params = params["figure"]
figure_params["obs"] = args.obs
figure_params["groupby"] = args.groupby
figure_params.setdefault("xlabel", args.groupby)
figure_params.setdefault("legend", {})
figure_params["legend"].setdefault("title", args.obs)

figure = sct.pl.composition(adata, **figure_params)
if figure is None:
    raise RuntimeError("composition plot did not return a figure and axis")
fig, ax = figure

sct.pl.set_default_axis(ax)
plt.savefig(args.outfile, bbox_inches="tight", pad_inches=0.3)
plt.close(fig)
std.crop_pdf(args.outfile)
