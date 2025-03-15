#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import os
import argparse
from pathlib import Path
from utils.stdout import (
    disable_print,
    print_task,
    print_info,
    print_warning
)

import re

from pandas import (
    ExcelWriter,
    read_excel
)

from databases.genesyn import GeneSynonyms

from goatools.utils import read_geneset
from goatools.obo_parser import GODag
from goatools.anno.gaf_reader import GafReader
from goatools.anno.genetogo_reader import Gene2GoReader
from goatools.goea.go_enrichment_ns import GOEnrichmentStudyNS

parser = argparse.ArgumentParser(
    prog="Gene enrichment analysis",
    description="""Perform gene ontology enrichment analysis.""",
    usage="python enrichment.py [-h] <FILE> --population <FILE> --study <FILE> [<FILE> ...] --go <FILE> --gene2go|--annotations <FILE> [-v]"
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="file containing gene ontology enrichment results (xlsx format)"
)

parser.add_argument(
    "--population",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="file containing background gene set (txt format)"
)

parser.add_argument(
    "--study",
    dest="study",
    type=lambda x: Path(x).resolve(),
    nargs="+",
    required=True,
    metavar="FILE",
    help="files containing interest gene set (txt format)"
)

parser.add_argument(
    "--go",
    dest="go",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="file containing DAG with HPO terms (obo format)"
)

parser.add_argument(
    "--annotations",
    dest="annotations",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="file containing annotations of genes-to-HPO terms (annotation.tab format, cannot be used with argument --gene2go)"
)

parser.add_argument(
    "--gene2go",
    dest="gene2go",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="file containing NCBI gene-to-GO terms (cannot be used with argument --annotations)"
)

parser.add_argument(
    "-v", "--verbose",
    dest="verbose",
    required=False,
    default=False,
    action="store_true",
    help="print information in stdout"
)

args = parser.parse_args()

if not Path(os.path.dirname(args.outfile)).exists():
    os.makedirs(os.path.dirname(args.outfile))

if args.go is None and args.annotations is None:
    raise argparse.ArgumentError("one of the following arguments is required: --go or --annotations")
elif args.go is not None and args.annotations is not None:
    raise argparse.ArgumentError("the following arguments cannot be used simultaneously: --go and --annotations")
else:
    annotations_alias_type = "geneid" if args.go else "MGI"

genesynonyms = GeneSynonyms()

print_task("background gene set loading")

with disable_print(disable=not args.verbose):
    population_ids = read_geneset(args.population)
    population_ids = genesynonyms.sequence_standardization(
        gene_sequence=population_ids,
        in_alias_type="genename",
        out_alias_type=annotations_alias_type
    )
    if None in population_ids:
        population_ids.remove(None)
    if annotations_alias_type == "geneid":
        population_ids = set(map(lambda geneid: int(geneid) if geneid.isnumeric() else None, population_ids))
    if None in population_ids:
        population_ids.remove(None)

print_task("study gene sets loading")

with disable_print(disable=not args.verbose):
    study_ids = dict()
    for _study_file in args.study:
        _study_ids = read_geneset(_study_file)
        _study_ids = genesynonyms.sequence_standardization(
        gene_sequence=_study_ids,
        in_alias_type="genename",
        out_alias_type=annotations_alias_type
    )
        if None in _study_ids:
            _study_ids.remove(None)
        if annotations_alias_type == "geneid":
            _study_ids = set(map(lambda geneid: int(geneid) if geneid.isnumeric() else None, _study_ids))
        if None in _study_ids:
            _study_ids.remove(None)
        study_ids[os.path.basename(_study_file).rsplit(".", maxsplit=1)[0]] = _study_ids

print_task("gene ontologies loading")

go_dag = GODag(args.go)

with open(args.go, "r") as go_reader:
    go_definitions = dict()
    for line in go_reader:
        if re.search("^id: GO:[0-9]{7}", line):
            _id = re.findall("GO:[0-9]{7}|$", line)[0]
        elif re.search("^def: \".+\.\"", line):
            _definition = re.findall("^def: \".+\.\"|$", line)[0]
            _definition = re.sub("^def: \"", "", _definition)
            _definition = re.sub("\"$", "", _definition)
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

print_task("gene-to-go associations loading")

with disable_print(disable=not args.verbose):
    if args.gene2go:
        annotations = Gene2GoReader(args.gene2go, taxids=[10090])
    else:
        annotations = GafReader(args.annotations)
    associations = annotations.get_ns2assc()

for namespace, geneid2go in associations.items():
    print_info(f"{namespace} {len(geneid2go):,} annotated mouse genes")

print_task("gene ontology enrichment analysis")

with disable_print(disable=not args.verbose):
    goea = GOEnrichmentStudyNS(
        pop=population_ids,
        ns2assoc=associations,
        godag=go_dag,
        propagate_counts=False,
        alpha=0.05,
        methods=['fdr_bh']
    )

    for cluster, genes in study_ids.items():
        _goea_all_results = goea.run_study(genes)
        _goea_significant_results = [result for result in _goea_all_results if result.p_fdr_bh < 0.05]
        goea.wr_xlsx(f"{os.path.dirname(args.outfile)}/{cluster}", _goea_significant_results)

print_task("data saving")

with disable_print(disable=not args.verbose):
    with ExcelWriter(args.outfile) as xlsx_writer:
        for cluster in study_ids.keys():
            xlsx_infile = f"{os.path.dirname(args.outfile)}/{cluster}"
            if os.path.isfile(xlsx_infile):
                goea_results = read_excel(xlsx_infile, sheet_name=0)
                for index, row in goea_results.iterrows():
                    _go = row["GO"]
                    if _go in go_definitions:
                        goea_results.at[index, "definition"] = go_definitions[_go]
                column_names = list(goea_results.columns)
                idx_study_items, idx_definition = column_names.index("study_items"), column_names.index("definition")
                column_names[idx_definition], column_names[idx_study_items] = column_names[idx_study_items], column_names[idx_definition]
                goea_results = goea_results[column_names]
                goea_results.sort_values(by="p_fdr_bh", axis=0, ascending=True)
                goea_results.to_excel(xlsx_writer, sheet_name=cluster)
                os.remove(xlsx_infile)
            else:
                print_warning(f"{xlsx_infile} not found")