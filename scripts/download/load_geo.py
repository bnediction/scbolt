import argparse
import tempfile
import warnings
from pathlib import Path

import bonesistools as bt
import pandas as pd
from scbolt import cli, console, omics

script_name = Path(__file__).name


def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=cli.HelpFormatter,
        prog="load_geo",
        description="Download and import a GEO count matrix into AnnData.",
        usage=(f"python {script_name} <GSM> <FILE> [--cache-dir <DIR>]"),
    )

    parser.add_argument("gsm", metavar="GSM")
    parser.add_argument("outfile", type=lambda x: Path(x).resolve(), metavar="FILE")
    parser.add_argument("--cache-dir", type=lambda x: Path(x).resolve(), metavar="DIR")
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()

    console.print_task(f"loading GEO count matrix (sample={args.gsm})")
    if args.cache_dir is None:
        with tempfile.TemporaryDirectory(prefix="scbolt-geo-") as cache_dir:
            adata = bt.omics.io.from_geo(
                args.gsm,
                cache_dir=cache_dir,
                quiet=args.quiet,
            )
    else:
        adata = bt.omics.io.from_geo(
            args.gsm,
            cache_dir=args.cache_dir,
            quiet=args.quiet,
        )

    if "symbol" in adata.var:
        symbols = pd.Index(adata.var["symbol"].astype(str), name=None)
        if symbols.has_duplicates:
            console.print_info("merging duplicated gene symbols")
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Variable names are not unique.*",
                    category=UserWarning,
                )
                adata.var_names = symbols
                bt.omics.pp.merge_duplicate_vars(adata, copy=False)

    keep_var_columns = [column for column in ["Accession", "symbol"] if column in adata.var]
    adata.var = adata.var.loc[:, keep_var_columns].copy()
    adata.obs.index.name = None
    adata.var.index.name = None
    adata.var_names_make_unique()
    adata = adata[sorted(adata.obs.index), sorted(adata.var.index)].to_memory()
    adata.obs.index.name = None
    adata.var.index.name = None
    adata.layers["counts"] = adata.X.copy()
    adata.X = None
    adata.uns["scbolt"] = {
        "input_source": "GEO",
        "gsm": args.gsm,
        "matrix_type": "public_count_matrix",
    }

    if adata.n_obs == 0:
        raise ValueError("imported AnnData has no cells")
    if adata.n_vars == 0:
        raise ValueError("imported AnnData has no genes")

    args.outfile.parent.mkdir(parents=True, exist_ok=True)
    console.print_task(f"saving AnnData (file={console.format_path(args.outfile)})")
    omics.write_h5ad(adata, filename=args.outfile)


if __name__ == "__main__":
    main()
