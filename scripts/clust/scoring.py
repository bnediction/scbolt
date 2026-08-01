import argparse
import json
import os
from pathlib import Path

import anndata as ad
import bonesistools as bt
import pandas as pd
from scbolt import cli, console

CLUSTER_INFO_ROWS = ["cells", "proportion", "median_expression", "median_reads"]
CORRECTION_METHODS = ("none", "benjamini-hochberg", "bonferroni")
ORA_RESULT_FILE = "ora_results.xlsx"
SIGNATURE_PVALS_ADJ_FILE = "signature_pvals_adj.csv"
SIGNATURE_FOLD_ENRICHMENT_FILE = "signature_fold_enrichment.csv"


def format_compact_number(value) -> str:
    value = float(value)
    if value.is_integer():
        return f"{int(value)}"
    return f"{value:g}"


def format_signature_table(display: pd.DataFrame) -> list[str]:
    row_labels = [str(row) for row in display.index]
    column_labels = [str(column) for column in display.columns]
    index_width = max(len("cluster"), *(len(label) for label in row_labels))
    column_widths = []
    for column, column_label in zip(display.columns, column_labels):
        column_widths.append(
            max(
                len(column_label),
                *(len(str(display.loc[row, column])) for row in display.index),
            )
        )

    header = "cluster".ljust(index_width)
    for column, width in zip(column_labels, column_widths):
        header += f"  {column.rjust(width)}"

    lines = [header]
    for row, row_label in zip(display.index, row_labels):
        line = row_label.ljust(index_width)
        for column, width in zip(display.columns, column_widths):
            line += f"  {str(display.loc[row, column]).rjust(width)}"
        lines.append(line)
    return lines


def format_signature_summary(info: pd.DataFrame) -> str:
    display = info.copy().astype(object)

    for row in display.index:
        if row == "cells":
            display.loc[row] = display.loc[row].map(lambda value: f"{int(value)}")
        elif row == "proportion":
            display.loc[row] = display.loc[row].map(lambda value: f"{value:.2%}")
        elif row in {"median_expression", "median_reads"}:
            display.loc[row] = display.loc[row].map(format_compact_number)
        else:
            display.loc[row] = display.loc[row].map(lambda value: f"{value:.2%}")

    lines = format_signature_table(display)
    width = max(len(line) for line in lines)

    cluster_info_rows = [row for row in CLUSTER_INFO_ROWS if row in display.index]
    header = lines[0]
    cluster_info = lines[1 : 1 + len(cluster_info_rows)]
    signature_scores = lines[1 + len(cluster_info_rows) :]

    formatted_lines = [
        "cluster metadata".center(width),
        "-" * width,
        header,
        *cluster_info,
        "",
        "signature scoring (p-values)".center(width),
        "-" * width,
        *signature_scores,
    ]
    table = "\n".join(formatted_lines)
    return "     " + table.replace("\n", "\n     ")


def make_excel_sheet_name(name: object, used_names: set[str]) -> str:
    sheet_name = "".join(
        "_" if character in "[]:*?/\\" else character for character in str(name)
    ).strip("'")
    if not sheet_name:
        sheet_name = "cluster"
    sheet_name = sheet_name[:31]

    candidate = sheet_name
    suffix = 1
    while candidate in used_names:
        suffix_text = f"_{suffix}"
        candidate = f"{sheet_name[: 31 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    used_names.add(candidate)
    return candidate


def write_signature_outputs(
    outfile: Path,
    pvals: pd.DataFrame,
    pvals_adj: pd.DataFrame,
    fold_enrichment: pd.DataFrame,
    ora_results: dict[object, pd.DataFrame],
) -> None:
    outdir = outfile.parent
    pvals_adj_file = outdir / SIGNATURE_PVALS_ADJ_FILE
    fold_enrichment_file = outdir / SIGNATURE_FOLD_ENRICHMENT_FILE
    ora_result_file = outdir / ORA_RESULT_FILE

    console.print_task(f"saving raw p-value matrix (file={console.format_path(outfile)})")
    pvals.to_csv(outfile, sep=",", index=True)

    console.print_task(
        f"saving adjusted p-value matrix (file={console.format_path(pvals_adj_file)})"
    )
    pvals_adj.to_csv(pvals_adj_file, sep=",", index=True)

    console.print_task(
        "saving fold-enrichment matrix "
        f"(file={console.format_path(fold_enrichment_file)})"
    )
    fold_enrichment.to_csv(fold_enrichment_file, sep=",", index=True)

    console.print_task(f"saving full ORA results (file={console.format_path(ora_result_file)})")
    used_sheet_names: set[str] = set()
    with pd.ExcelWriter(ora_result_file) as writer:
        for cluster, ora_result in ora_results.items():
            table = ora_result.reset_index()
            if "overlap" in table:
                table["overlap"] = table["overlap"].map(
                    lambda genes: (
                        ", ".join(genes)
                        if isinstance(genes, (list, set, tuple))
                        else genes
                    )
                )
            table.to_excel(
                writer,
                sheet_name=make_excel_sheet_name(cluster, used_sheet_names),
                index=False,
            )


script_name = Path(__file__).name

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scoring",
        description="Score signature-related phenotypes with respect to cell clusters.",
        usage=f"python {script_name} [-h] <FILE> <FILE> <FILE> <FILE> --cluster <LITERAL> [<args>]",
        formatter_class=cli.HelpFormatter,
    )

    parser.add_argument(
        "infile",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help="input file storing counts (format: h5ad)",
    )

    parser.add_argument(
        "signatures",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help="input file storing phenotype-gene list associations (format: json)",
    )

    parser.add_argument(
        "markers",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help="input file storing gene sets for each spreadsheet (format: xlsx)",
    )

    parser.add_argument(
        "outfile",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help="output file storing raw signature p-values (format: csv)",
    )

    parser.add_argument(
        "--cluster",
        dest="cluster",
        type=str,
        required=True,
        metavar="LITERAL",
        help="column name in 'adata.obs' distinguishing cell populations (required)",
    )

    parser.add_argument(
        "--ignore-sheets",
        dest="ignore_sheets",
        type=str,
        required=False,
        nargs="+",
        default=None,
        metavar="LITERAL",
        help="spreadsheet names to ignore (default: None)",
    )

    parser.add_argument(
        "--correction",
        dest="correction",
        type=str,
        required=False,
        default="none",
        choices=CORRECTION_METHODS,
        metavar="LITERAL",
        help=(
            "p-value correction method: none, benjamini-hochberg or bonferroni "
            "(default: none)"
        ),
    )

    args = parser.parse_args()

    ora_correction = "benjamini-hochberg" if args.correction == "none" else args.correction

    if not Path(os.path.dirname(args.outfile)).exists():
        os.makedirs(Path(os.path.dirname(args.outfile)))

    console.print_task(f"loading AnnData (file={console.format_path(args.infile)})")
    adata = ad.read_h5ad(args.infile)

    console.print_task(
        f"loading signature definitions (file={console.format_path(args.signatures)})"
    )
    with open(args.signatures, "r") as file:
        signatures = json.load(file)

    console.print_task(f"loading marker workbook (file={console.format_path(args.markers)})")
    ignored_sheets = set(args.ignore_sheets or [])
    with pd.ExcelFile(args.markers) as file:
        markers = {}
        for sheet_name in file.sheet_names:
            if sheet_name not in ignored_sheets:
                df = file.parse(sheet_name, header=None)
                markers[sheet_name] = df[df.columns[0]].to_list()

    console.print_task("analyzing cell signatures")

    console.print_debug("deleting signature genes absent from AnnData")
    background = adata.var_names
    for phenotype, genes in signatures.items():
        signatures[phenotype] = {gene for gene in genes if gene in background}
    signatures = {
        phenotype: signature for phenotype, signature in signatures.items() if signature
    }

    console.print_info(
        "estimating over-representation p-values " f"(correction={args.correction})"
    )

    info = {}
    ora_results = {}
    pvals = {}
    pvals_adj = {}
    fold_enrichment = {}
    signature_names = list(signatures)
    for group in sorted(adata.obs[args.cluster].unique()):
        group_adata = adata[adata.obs[args.cluster] == group]
        group_info = {}
        group_info["cells"] = group_adata.n_obs
        group_info["proportion"] = round(group_adata.n_obs / adata.n_obs, ndigits=6)
        group_info["median_expression"] = group_adata.obs["n_features"].median()
        group_info["median_reads"] = group_adata.obs["total"].median()
        ora_result = bt.omics.tl.ora(
            query_set=markers[group],
            signatures=signatures,
            background=group_adata.var_names,
            correction=ora_correction,
            include_overlap=True,
        )
        ora_results[group] = ora_result
        pvals[group] = ora_result["pvals"].reindex(signature_names)
        pvals_adj[group] = ora_result["pvals_adj"].reindex(signature_names)
        fold_enrichment[group] = ora_result["fold_enrichment"].reindex(signature_names)
        pvalue_column = "pvals" if args.correction == "none" else "pvals_adj"
        pvalue_scores = ora_result[pvalue_column].to_dict()
        pvalues = {
            signature: pvalue_scores[signature]
            for signature in signatures
            if signature in pvalue_scores
        }
        group_info.update({k: round(v, ndigits=6) for k, v in pvalues.items()})
        info[group] = group_info
    info = pd.DataFrame.from_dict(info)

    console.print_result("signature summary\n\n" f"{format_signature_summary(info)}\n")

    write_signature_outputs(
        outfile=args.outfile,
        pvals=pd.DataFrame(pvals).reindex(signature_names),
        pvals_adj=pd.DataFrame(pvals_adj).reindex(signature_names),
        fold_enrichment=pd.DataFrame(fold_enrichment).reindex(signature_names),
        ora_results=ora_results,
    )


if __name__ == "__main__":
    main()
