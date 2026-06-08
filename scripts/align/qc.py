#!/usr/bin/env python

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import std

import numpy as np


def read_matrix_shape(matrix_file: Path) -> tuple[int, int, int]:
    with open(matrix_file) as handle:
        for line in handle:
            if line.startswith("%"):
                continue

            n_rows, n_cols, n_values = line.split()
            return int(n_rows), int(n_cols), int(n_values)

    raise ValueError(f"missing MatrixMarket shape line in {matrix_file}")


def barcode_umi_counts(matrix_file: Path) -> np.ndarray:
    _, n_barcodes, n_values = read_matrix_shape(matrix_file)
    counts = np.zeros(n_barcodes, dtype=np.int64)

    with open(matrix_file) as handle:
        for line in handle:
            if line.startswith("%"):
                continue

            # Skip matrix dimensions.
            break

        for line in handle:
            _, barcode, value = line.split()
            counts[int(barcode) - 1] += int(value)

    std.print_info(f"matrix entries: {n_values}")
    return counts


def knee_count(counts: np.ndarray) -> int:
    positive = np.sort(counts[counts > 0])[::-1]
    if len(positive) == 0:
        return 0
    if len(positive) <= 2:
        return len(positive)
    if positive[0] == positive[-1]:
        return len(positive)

    ranks = np.arange(1, len(positive) + 1)
    x = np.log10(ranks)
    y = np.log10(positive)

    x = (x - x[0]) / (x[-1] - x[0])
    y = (y - y[-1]) / (y[0] - y[-1])
    distances = y - (1 - x)

    return int(np.argmax(distances)) + 1


def selected_indices(
    counts: np.ndarray,
    method: str,
    min_umi: int | None,
    top_barcodes: int | None,
) -> np.ndarray:
    order = np.argsort(counts)[::-1]

    if method == "threshold":
        if min_umi is None:
            raise ValueError("--min-umi is required with --method threshold")
        return np.flatnonzero(counts >= min_umi)

    if method == "top":
        if top_barcodes is None:
            raise ValueError("--top-barcodes is required with --method top")
        top = order[:top_barcodes]
        return top[counts[top] > 0]

    n_cells = knee_count(counts)
    return order[:n_cells]


def selection_summary(
    method: str,
    min_umi: int | None,
    top_barcodes: int | None,
) -> str:
    if method == "threshold":
        return f"method=threshold, min-umi={min_umi}"
    if method == "top":
        return f"method=top, top-barcodes={top_barcodes}"
    return "method=auto"


def write_barcodes(
    barcode_file: Path,
    outfile: Path,
    indices: np.ndarray,
) -> None:
    selected = set(indices.tolist())

    with open(barcode_file) as barcodes, open(outfile, "w") as output:
        for index, barcode in enumerate(barcodes):
            if index in selected:
                output.write(barcode)


parser_description = """
Filter barcodes from a count matrix.

The default method estimates a knee point from the barcode rank plot. A fixed
UMI threshold or a fixed number of top barcodes can be used instead.
"""

script_name = Path(__file__).name

parser = argparse.ArgumentParser(
    prog="qc",
    description=parser_description,
    usage=(
        f"python {script_name} [-h] <FILE> <FILE> <FILE> "
        "[--method {auto,threshold,top}] [--min-umi INT] [--top-barcodes INT]"
    ),
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "matrix",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="MatrixMarket count matrix",
)

parser.add_argument(
    "barcodes",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="barcode file matching matrix columns",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="filtered barcode output file",
)

parser.add_argument(
    "--method",
    choices=["auto", "threshold", "top"],
    default="auto",
    help="barcode filtering method (default: auto)",
)

parser.add_argument(
    "--min-umi",
    type=int,
    default=None,
    metavar="INT",
    help="minimum UMI count per barcode",
)

parser.add_argument(
    "--top-barcodes",
    type=int,
    default=None,
    metavar="INT",
    help="number of top barcodes to keep",
)

args = parser.parse_args()

if args.min_umi is not None and args.min_umi <= 0:
    parser.error("--min-umi must be a positive integer")

if args.top_barcodes is not None and args.top_barcodes <= 0:
    parser.error("--top-barcodes must be a positive integer")

if args.method == "auto" and args.min_umi is not None:
    parser.error("--min-umi requires --method threshold")

if args.method == "auto" and args.top_barcodes is not None:
    parser.error("--top-barcodes requires --method top")

if args.outfile.parent:
    os.makedirs(args.outfile.parent, exist_ok=True)

std.print_task(f"loading count matrix (file={std.format_path(args.matrix)})")
counts = barcode_umi_counts(args.matrix)

std.print_task("selecting cell barcodes")
std.print_info(selection_summary(args.method, args.min_umi, args.top_barcodes))
indices = selected_indices(
    counts=counts,
    method=args.method,
    min_umi=args.min_umi,
    top_barcodes=args.top_barcodes,
)

if len(indices) == 0:
    raise ValueError("barcode filtering selected no cells")

threshold = int(counts[indices].min())
total_positive = int(np.count_nonzero(counts))
std.print_result(
    f"selected {len(indices)}/{total_positive} expressed barcodes "
    f"(minimum UMI count: {threshold})"
)

std.print_task(f"saving barcodes (file={std.format_path(args.outfile)})")
write_barcodes(args.barcodes, args.outfile, indices)
