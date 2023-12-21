#!/usr/bin/python3

from pathlib import Path

import os
import argparse
import scanpy as sc

parser = argparse.ArgumentParser(
    prog="Loading 10X sparse matrix format sc-RNAseq data",
    description="""converter of sc-rnaSeq data in the 10X sparse matrix format into the hdf5 format.\n
    The structure of 10X sparse matrix format is a directory containing three files:\n
    - matrix.mtx.gz (sparse matrix in the Market Exchange MEX format\n
    -- also named coordinate list format -- which corresponds to compressed reordered sparse counting data)\n
    - barcodes.tsv.gz (information about each cell)\n
    - features.tsv.gz (information about each gene)\n""",
    usage="python load_10X.py -i <inpath>  [<args>]")

parser.add_argument(
    "-i", "--inpath",
    dest="inpath",
    type=lambda x: Path(x).resolve(),
    required=True,
    help="directory to the 10X sparse matrix data"
)

parser.add_argument(
    "-o", "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=Path("./out.h5ad").resolve(),
    help="hdf5 output filename"
)

parser.add_argument(
    "-s", "--sample_info",
    dest="sample_info",
    type=str,
    required=False,
    default=None,
    help="sample metadata (format: key_1=value_1,...,key_n=value_n"
)

args = parser.parse_args()

outpath = Path(os.path.split(args.outfile)[0]).resolve()

if not outpath.exists():
    os.makedirs(outpath)

adata = sc.read_10x_mtx(path=args.inpath)
adata.var["symbol"] = list(adata.var.index)

for metadatum in args.sample_info.split(","):
    key, value = metadatum.split("=")
    adata.uns[key] = value

adata.write_h5ad(filename=args.outfile, compression="gzip")