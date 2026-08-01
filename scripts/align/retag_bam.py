import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import pysam
from scbolt import cli, console


def load_barcodes(barcode_file: str | Path | None) -> set[str] | None:
    if barcode_file is None:
        return None

    with open(barcode_file) as handle:
        return {line.strip() for line in handle if line.strip()}


def copy_bam_tags(
    infile: str | Path,
    outfile: str | Path,
    tags: dict[str, str],
    barcodes: set[str] | None = None,
    barcode_tag: str = "CR",
    jobs: int = 1,
) -> tuple[dict[tuple[str, str], int], int, int]:
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
    barcodes: set[str] or None
        Optional barcode whitelist. If provided, only reads whose barcode tag
        matches one of these values are written.
    barcode_tag: str
        BAM tag used to match reads against the barcode whitelist.
    jobs: int
        Number of jobs used by pysam for BAM compression/decompression.

    Returns
    -------
    dict[tuple[str, str], int]
        Number of reads copied for each source/destination tag pair.
    int
        Number of reads written to the output BAM file.
    int
        Number of reads skipped because of barcode filtering.
    """

    copied = {(source, destination): 0 for source, destination in tags.items()}
    kept_reads = 0
    skipped_reads = 0

    with (
        pysam.AlignmentFile(infile, "rb", threads=jobs) as bam_in,
        pysam.AlignmentFile(
            outfile,
            "wb",
            template=bam_in,
            threads=jobs,
        ) as bam_out,
    ):
        for read in bam_in:
            if barcodes is not None:
                if not read.has_tag(barcode_tag):
                    skipped_reads += 1
                    continue
                if read.get_tag(barcode_tag) not in barcodes:
                    skipped_reads += 1
                    continue

            for source, destination in tags.items():
                if read.has_tag(source):
                    value, value_type = read.get_tag(source, with_value_type=True)
                    read.set_tag(destination, value, value_type=value_type)
                    copied[(source, destination)] += 1
            bam_out.write(read)
            kept_reads += 1

    return copied, kept_reads, skipped_reads


parser_description = """
Copy BAM tags from source names to destination names.

By default, this copies CR/UR tags to CB/UB tags. Custom tag mappings can be
passed with --tag, using <source>:<destination> syntax.
"""

script_name = Path(__file__).name

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="retag-bam",
        description=parser_description,
        usage=(
            f"python {script_name} [-h] <FILE> <FILE> "
            "[--tag LITERAL:LITERAL ...] [--barcodes FILE] "
            "[--barcode-tag TAG] [--jobs INT]"
        ),
        formatter_class=cli.HelpFormatter,
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

    parser.add_argument(
        "--barcodes",
        type=lambda x: Path(x).resolve(),
        default=None,
        metavar="FILE",
        help="keep only reads matching one of these barcodes",
    )

    parser.add_argument(
        "--barcode-tag",
        default="CR",
        metavar="TAG",
        help="read tag used to match barcodes (default: CR)",
    )

    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        metavar="INT",
        help="BAM compression/decompression jobs (default: 1)",
    )

    args = parser.parse_args()

    if args.jobs <= 0:
        parser.error("--jobs must be a positive integer")

    if args.outfile.parent:
        os.makedirs(args.outfile.parent, exist_ok=True)

    console.print_task(f"loading BAM (file={console.format_path(args.infile)})")
    if args.barcodes is not None:
        console.print_task(f"loading selected barcodes (file={console.format_path(args.barcodes)})")
    barcodes = load_barcodes(args.barcodes)
    if barcodes is not None:
        console.print_info(f"identified {len(barcodes)} barcodes")

    console.print_task(f"saving retagged BAM (file={console.format_path(args.outfile)})")

    copied, kept_reads, skipped_reads = copy_bam_tags(
        args.infile,
        args.outfile,
        args.tags,
        barcodes=barcodes,
        barcode_tag=args.barcode_tag,
        jobs=args.jobs,
    )

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
    console.print_result(f"copied {copied_str}")

    if barcodes is not None:
        total_reads = kept_reads + skipped_reads
        kept_fraction = kept_reads / total_reads if total_reads else 0
        console.print_result(f"kept {kept_reads}/{total_reads} reads " f"({kept_fraction:.1%})")


if __name__ == "__main__":
    main()
