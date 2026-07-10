#!/usr/bin/env python

from pathlib import Path

import os
import std
import argparse
import cli
import re

import anndata as ad
import pandas as pd
import scanpy as sc
import bonesistools as bt

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="adata_conversion",
    description="""Convert single-omics counting data into the desired format.
    In case of 10x sparse matrix format, it is a directory containing three files:
    - matrix.mtx.gz (sparse matrix in the Market Exchange MEX format, also named coordinate list format)
    - barcodes.tsv.gz (information about each cell)
    - features.tsv.gz (information about each gene)""",
    usage=(
        f"python {script_name} [-h] <PATH | FILE> <PATH | FILE> "
        "--from <h5ad | loom | 10x> --to <h5ad | loom | csv | csvs> "
        "[--metadata <KEY=VALUE ...>] [<args>]"
    ),
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    "input",
    type=lambda x: Path(x).resolve(),
    metavar="PATH | FILE",
    help="input data directory or file, depending on --from",
)

parser.add_argument(
    "output",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output data directory or file, depending on --to",
)

parser.add_argument(
    "--from",
    dest="from_format",
    type=str,
    choices=["h5ad", "loom", "10x"],
    metavar="[h5ad | loom | 10x]",
    required=True,
    help="matrix data input format",
)

parser.add_argument(
    "--to",
    dest="to_format",
    type=str,
    choices=["h5ad", "loom", "csv", "csvs"],
    metavar="[h5ad | loom | csv | csvs]",
    required=True,
    help="matrix data output format",
)

parser.add_argument(
    "--expression",
    dest="expression",
    type=str,
    required=False,
    default=None,
    metavar="LITERAL",
    help=("Expression layer saved when converting to CSV.\n" "Default: adata.X."),
)

parser.add_argument(
    "--only-hvg",
    dest="only_hvg",
    action="store_true",
    required=False,
    help="reduce feature dimension to highly variable genes",
)

parser.add_argument(
    "--remove-positions",
    dest="remove_positions",
    required=False,
    action="store_true",
    help="remove chromosome, position on it and strand directions for each gene",
)

parser.add_argument(
    "--metadata",
    dest="metadata",
    type=str,
    nargs="*",
    required=False,
    default=None,
    metavar="KEY=VALUE",
    help="dataset-related metadata",
)

parser.add_argument(
    "--standardization",
    dest="standardization",
    required=False,
    action="store_true",
    help="convert gene names by their NCBI reference names",
)

parser.add_argument(
    "--sort",
    dest="sort",
    required=False,
    action="store_true",
    help="sort observations and variables",
)

parser.add_argument(
    "--compression",
    dest="compression",
    required=False,
    action="store_true",
    help="output file compression (if output format is h5ad)",
)


def add_metadata(adata: ad.AnnData, **metadata) -> None:
    for k, v in metadata.items():
        adata.uns[k] = v


args = parser.parse_args()

from_format = args.from_format
to_format = args.to_format

if from_format == to_format:
    raise ValueError("Argument --from and --to must be different")

if to_format == "csvs":
    os.makedirs(name=args.output, exist_ok=True)
else:
    os.makedirs(name=os.path.dirname(args.output), exist_ok=True)

std.print_task(f"loading data (file={std.format_path(args.input)})")
if from_format == "h5ad":
    adata = sc.read_h5ad(filename=args.input)
elif from_format == "loom":
    adata = sc.read_loom(filename=args.input)
elif from_format == "10x":
    adata = sc.read_10x_mtx(path=args.input)
else:
    raise ValueError(f"unsupported input format: {from_format}")

adata.obs.index = pd.Index(
    map(
        lambda barcode: re.sub("[^ATCG]", "", re.sub("^.*:", "", barcode)),
        adata.obs.index,
    )
)

if args.only_hvg:
    std.print_info("keeping highly variable genes only")
    if "highly_variable" in adata.var:
        adata._inplace_subset_var(adata.var["highly_variable"])
    else:
        raise KeyError(
            "column 'highly_variable' not found in adata.var: please use 'sc.pp.highly_variable_genes' before)"
        )

if args.remove_positions:
    for column in ["Chromosome", "Start", "End", "Strand"]:
        if column in adata.var.columns:
            del adata.var[column]

if args.metadata:

    def split(metadata):
        return [metadatum.split("=") for metadatum in metadata]

    metadata_d = {info[0]: info[1] for info in split(args.metadata)}
    add_metadata(adata, **metadata_d)

if args.standardization:
    std.print_info("standardizing gene names")
    adata.var["symbol"] = list(adata.var.index)
    for input_identifier_type in ["name", "gene_id", "ensembl_id"]:
        bt.omics.pp.convert_gene_identifiers(
            adata, axis="var", input_identifier_type=input_identifier_type, copy=False
        )
    bt.omics.pp.merge_duplicate_vars(
        adata,
        copy=False,
    )

if args.sort:
    adata = adata[sorted(adata.obs.index), sorted(adata.var.index)].to_memory()

std.print_task(f"saving data (file={std.format_path(args.output)})")
if to_format == "h5ad":
    std.write_h5ad(
        adata,
        filename=args.output,
        compression="gzip" if args.compression else None,
    )
elif to_format == "loom":
    adata.write_loom(filename=args.output, write_obsm_varm=True)
elif to_format == "zarr":
    adata.write_zarr(store=args.output)
elif to_format == "csv":
    bt.omics.tl.to_dataframe(adata=adata, layer=args.expression).to_csv(
        path_or_buf=args.output, sep=",", index=True
    )
elif to_format == "csvs":
    adata.write_csvs(dirname=args.output, sep=",")
    bt.omics.io.to_mtx(adata=adata, filename=Path(f"{args.output}/matrix"))
    if adata.layers.keys():
        os.makedirs(name=Path(f"{args.output}/layers"), exist_ok=True)
        for layer in adata.layers:
            bt.omics.io.to_mtx(
                adata=adata, filename=Path(f"{args.output}/layers/{layer}"), layer=layer
            )
else:
    raise ValueError(f"unsupported output format: {to_format}")
