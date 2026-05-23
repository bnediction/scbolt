#!/usr/bin/env python

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import std


def get_sign_column(dorothea):
    for column in ("sign", "weight", "mor"):
        if column in dorothea.columns:
            return column
    raise ValueError("DoRothEA table must contain a sign, weight or mor column")


parser = argparse.ArgumentParser(
    prog="load_dorothea_legacy",
    description="Download DoRothEA through decoupler.get_dorothea and export a signed interaction graph.",
    usage="python load_dorothea_legacy.py --organism <ORGANISM> --outfile <FILE>",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "--organism",
    dest="organism",
    default="mouse",
    required=False,
    metavar="ORGANISM",
    help="organism passed to decoupler.get_dorothea (default: mouse)",
)

parser.add_argument(
    "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing source, target and sign columns (format: csv)",
)

args = parser.parse_args()

if args.outfile.parent:
    os.makedirs(args.outfile.parent, exist_ok=True)

std.print_task(f"loading DoRothEA with decoupler.get_dorothea (organism: {args.organism})")

try:
    import decoupler as dc
except ImportError as error:
    raise ImportError(
        "decoupler is required. Use the scbolt-decoupler-legacy environment."
    ) from error

if not hasattr(dc, "get_dorothea"):
    raise AttributeError(
        "decoupler.get_dorothea is not available. "
        "Use a legacy decoupler release in the scbolt-decoupler-legacy environment."
    )

import pandas as pd

dorothea = dc.get_dorothea(organism=args.organism)
sign_column = get_sign_column(dorothea)

dorothea = dorothea[["source", "target", sign_column]].rename(
    columns={sign_column: "sign"}
)
dorothea["sign"] = pd.to_numeric(dorothea["sign"]).map(lambda sign: -1 if sign < 0 else 1)
dorothea = dorothea.drop_duplicates().sort_values(["source", "target", "sign"])

std.print_result(f"interactions: {len(dorothea)}")
std.print_task(f"saving DoRothEA prior network in {str(args.outfile)}")
dorothea.to_csv(args.outfile, index=False)
