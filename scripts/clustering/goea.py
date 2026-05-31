#!/usr/bin/env python

import warnings

warnings.filterwarnings("ignore")

import os, std
import argparse
from pathlib import Path

import re

from pandas import ExcelFile, ExcelWriter, read_excel

import bonesistools as bt

from goatools.obo_parser import GODag
from goatools.anno.gaf_reader import GafReader
from goatools.anno.genetogo_reader import Gene2GoReader
from goatools.goea.go_enrichment_ns import GOEnrichmentStudyNS

parser = argparse.ArgumentParser(
    prog="goea",
    description="Perform Gene Ontology enrichment analysis.",
    usage="python goea.py [-h] <FILE> <FILE> --background <LITERAL> --go <FILE> (--gene2go <FILE> | --annotations <FILE>) [<args>]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing gene sets for each spreadsheet (format: xlsx)",
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="output file containing gene ontology enrichment results (format: xlsx)",
)

parser.add_argument(
    "--background",
    dest="background",
    type=str,
    required=True,
    metavar="LITERAL",
    help="spreadsheet name containing background gene set",
)

parser.add_argument(
    "--go",
    dest="go",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="input file containing the Gene Ontology DAG (format: obo)",
)

parser.add_argument(
    "--annotations",
    dest="annotations",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="input file containing gene-to-GO annotations (format: annotation.tab; cannot be used with --gene2go)",
)

parser.add_argument(
    "--gene2go",
    dest="gene2go",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="input file containing NCBI gene-to-GO annotations (format: gene2go; cannot be used with --annotations)",
)

parser.add_argument(
    "--organism",
    dest="organism",
    choices=["mouse", "human", "escherichia-coli"],
    default="mouse",
    required=False,
    metavar="[mouse | human | escherichia-coli]",
    help="gene-related organism (default: mouse)",
)

parser.add_argument(
    "--gene-type",
    dest="gene_type",
    type=str,
    required=False,
    default="name",
    metavar="[name | gene_id | ensembl_id | <database>]",
    help="gene identifier input format in infile (default: name)",
)

args = parser.parse_args()

if args.gene2go is None and args.annotations is None:
    raise ValueError(
        "one of the following arguments is required: --gene2go or --annotations"
    )
elif args.gene2go is not None and args.annotations is not None:
    raise ValueError(
        "the following arguments cannot be used simultaneously: --gene2go and --annotations"
    )
else:
    annotations_type = "gene_id" if args.gene2go else "MGI"

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(Path(os.path.dirname(args.outfile)))

genesyn = bt.dbs.ncbi.GeneSynonyms(organism=args.organism)

std.print_task(f"loading gene set workbook (file={std.format_path(args.infile)})")
with ExcelFile(args.infile) as file:
    study_geneset = {}
    for sheet_name in file.sheet_names:
        df = file.parse(sheet_name, header=None)
        study_geneset[sheet_name] = set(df[df.columns[0]])

background_geneset = study_geneset[args.background]
del study_geneset[args.background]

if args.gene_type != annotations_type:
    std.print_debug(
        f"standardizing gene identifiers ({args.gene_type} => {annotations_type})"
    )

for cluster, geneset in study_geneset.items():
    geneset = (
        genesyn(
            geneset,
            input_identifier_type=args.gene_type,
            output_identifier_type=annotations_type,
        )
        if args.gene_type != annotations_type
        else geneset
    )
    geneset = set(
        map(lambda gene_id: int(gene_id) if gene_id.isnumeric() else None, geneset)
    )
    geneset.discard(None)
    study_geneset[cluster] = geneset

background_geneset = (
    genesyn(
        background_geneset,
        input_identifier_type=args.gene_type,
        output_identifier_type=annotations_type,
    )
    if args.gene_type != annotations_type
    else background_geneset
)
background_geneset = set(
    map(
        lambda gene_id: int(gene_id) if gene_id.isnumeric() else None,
        background_geneset,
    )
)
background_geneset.discard(None)

go_file = args.go
if go_file is None:
    raise ValueError("argument --go is required")

std.print_task(f"loading gene ontology (file={std.format_path(go_file)})")

go_dag = GODag(obo_file=go_file, prt=open(os.devnull, "w"))

with open(go_file, "r") as go_reader:
    go_definitions = dict()
    for line in go_reader:
        if re.search("^id: GO:[0-9]{7}", line):
            _id = re.findall("GO:[0-9]{7}|$", line)[0]
        elif re.search('^def: ".+\."', line):
            _definition = re.findall('^def: ".+\."|$', line)[0]
            _definition = re.sub('^def: "', "", _definition)
            _definition = re.sub('"$', "", _definition)
        elif line == "\n":
            if "_id" in locals() and "_definition" in locals():
                if _id != "" and _definition != "":
                    go_definitions[_id] = _definition
                del _id, _definition
            elif "_id" in locals():
                del _id
            elif "_definition" in locals():
                del _definition
            else:
                continue

std.print_task(
    "loading gene-to-GO associations "
    f"(file={std.format_path(args.gene2go if args.gene2go else args.annotations)})"
)
with std.disable_print():
    if args.gene2go:
        annotations = Gene2GoReader(args.gene2go, taxids=[10090])
    else:
        annotations = GafReader(args.annotations)
    associations = annotations.get_ns2assc()

for namespace, gene_id2go in associations.items():
    std.print_info(f"{namespace} {len(gene_id2go):,} annotated {args.organism} genes")

std.print_task("performing gene ontology enrichment analysis (method=GOEA)")

goea = GOEnrichmentStudyNS(
    pop=background_geneset,
    ns2assoc=associations,
    godag=go_dag,
    propagate_counts=False,
    alpha=0.05,
    methods=["fdr_bh"],
    log=open(os.devnull, "w"),
)

for cluster, geneset in study_geneset.items():
    _goea_all_results = goea.run_study(study_ids=geneset, log=open(os.devnull, "w"))
    _goea_significant_results = [
        result for result in _goea_all_results if result.p_fdr_bh < 0.05
    ]
    if not _goea_significant_results:
        std.print_warning(f"no GOEA enrichment results for cluster {cluster}")
    else:
        std.print_result(
            f"{len(_goea_significant_results)} enrichment results for cluster {cluster}"
        )
        with std.disable_print():
            goea.wr_xlsx(
                f"{os.path.dirname(args.outfile)}/{cluster}", _goea_significant_results
            )

std.print_task(f"saving GOEA workbook (file={std.format_path(args.outfile)})")

with ExcelWriter(args.outfile) as xlsx_writer:
    for cluster in study_geneset.keys():
        xlsx_infile = f"{os.path.dirname(args.outfile)}/{cluster}"
        if os.path.isfile(xlsx_infile):
            goea_results = read_excel(xlsx_infile, sheet_name=0)
            for index, row in goea_results.iterrows():
                _go = row["GO"]
                if _go in go_definitions:
                    goea_results.at[index, "definition"] = go_definitions[_go]
            column_names = list(goea_results.columns)
            idx_study_items, idx_definition = column_names.index(
                "study_items"
            ), column_names.index("definition")
            column_names[idx_definition], column_names[idx_study_items] = (
                column_names[idx_study_items],
                column_names[idx_definition],
            )
            goea_results = goea_results[column_names]
            goea_results = goea_results.sort_values(by="p_fdr_bh", ascending=True)
            goea_results.to_excel(xlsx_writer, sheet_name=cluster)
            os.remove(xlsx_infile)
        else:
            std.print_warning(f"file {xlsx_infile} not found")
