#!/usr/bin/env python

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import cli
import std

import pysam


def copy_bam_tags(
    infile: str | Path,
    outfile: str | Path,
    tags: dict[str, str],
) -> dict[tuple[str, str], int]:
    """
    Copy BAM tags from source names to destination names.

    Parameters
    ----------
    infile: str or Path
        Input BAM file.
    outfile: str or Path
        Output BAM file with copied tags.
    tags: dict[str, str]
        Mapping of source tags to destination tags.

    Returns
    -------
    dict[tuple[str, str], int]
        Number of reads copied for each source/destination tag pair.
    """

    copied = {(source, destination): 0 for source, destination in tags.items()}

    with pysam.AlignmentFile(infile, "rb") as bam_in:
        with pysam.AlignmentFile(outfile, "wb", template=bam_in) as bam_out:
            for read in bam_in:
                for source, destination in tags.items():
                    if read.has_tag(source):
                        value, value_type = read.get_tag(source, with_value_type=True)
                        read.set_tag(destination, value, value_type=value_type)
                        copied[(source, destination)] += 1
                bam_out.write(read)

    return copied


parser_description = """
Copy BAM tags from source names to destination names.

By default, this copies CR/UR tags to CB/UB tags. Custom tag mappings can be
passed with --tag, using <source>:<destination> syntax.
"""

parser = argparse.ArgumentParser(
    prog="retag-bam",
    description=parser_description,
    usage="python retag_bam.py [-h] <FILE> <FILE> [--tag LITERAL:LITERAL ...]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input BAM file",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output BAM file with copied tags",
)

parser.add_argument(
    "--tag",
    dest="tags",
    action=cli.Store_dict,
    type_key=str,
    type_value=str,
    default={"CR": "CB", "UR": "UB"},
    help="tag mapping from source to destination (default: CR:CB UR:UB)",
)

args = parser.parse_args()

if args.outfile.parent:
    os.makedirs(args.outfile.parent, exist_ok=True)

std.print_task(f"loading BAM file from {args.infile}")
std.print_task(f"saving retagged BAM file in {args.outfile}")

copied = copy_bam_tags(args.infile, args.outfile, args.tags)

missing_tags = [
    f"{source}->{destination}"
    for (source, destination), count in copied.items()
    if count == 0
]
if missing_tags:
    raise ValueError(
        "no source tags found for "
        f"{', '.join(missing_tags)}; check the input BAM tags"
    )

copied_str = ", ".join(
    f"{source}->{destination} for {count} reads"
    for (source, destination), count in copied.items()
)
std.print_result(
    f"copied {copied_str}"
)
