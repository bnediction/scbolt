#!/usr/bin/env python

# wget --quiet --show-progress --directory-prefix=data/public/enrichment https://current.geneontology.org/ontology/subsets/goslim_mouse.obo
# wget --quiet --show-progress --directory-prefix=data/public/enrichment https://current.geneontology.org/annotations/mgi.gaf.gz
# https://geneontology.org/docs/download-go-annotations/

import warnings
warnings.filterwarnings("ignore")

import os
import argparse
from pathlib import Path
from utils.stdout import Section

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
    usage="python enrichment.py [-h] <FILE> --population <FILE> --study <FILE> [<FILE> ...] --go|--annotations <FILE> --gene2go <FILE> [-v]"
)

parser.add_argument(
    "outfile",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="xlsx file containing gene ontology enrichment results"
)

parser.add_argument(
    "--population",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="txt file containing background gene set"
)

parser.add_argument(
    "--study",
    dest="study",
    type=lambda x: Path(x).resolve(),
    nargs="+",
    required=True,
    metavar="FILE",
    help="txt files containing interest gene set"
)

parser.add_argument(
    "--go",
    dest="go",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="obo file (DAG containing HPO terms)"
)

parser.add_argument(
    "--annot", "--annotations",
    dest="annotations",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="annotation.tab file containing annotations of genes-to-HPO terms (cannot be used with argument --gene2go)"
)

parser.add_argument(
    "--gene2go",
    dest="gene2go",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="FILE",
    help="NCBI gene-to-GO terms file (cannot be used with argument --annotations)"
)

parser.add_argument(
    "-v", "--verbose",
    dest="verbose",
    required=False,
    action="store_true",
    help="display additional information"
)

arguments = """data/rna/enrichment/ct/goea.xlsx \
    --population data/rna/enrichment/ct/background.txt \
    --study data/rna/enrichment/ct/cluster0.txt data/rna/enrichment/ct/cluster2.txt data/rna/enrichment/ct/cluster4.txt data/rna/enrichment/ct/cluster6.txt data/rna/enrichment/ct/cluster1.txt  data/rna/enrichment/ct/cluster3.txt  data/rna/enrichment/ct/cluster5.txt \
    --go data/public/enrichment/go-basic.obo \
    --gene2go data/public/enrichment/gene2go \
    --verbose"""

# arguments = """data/rna/enrichment/ct/cluster0.txt data/rna/enrichment/ct/background.txt data/public/enrichment/go-basic.obo data/public/enrichment/mgi.gaf data/public/enrichment/gene2go --verbose"""
# args = parser.parse_args()
args = parser.parse_args(arguments.split())

if args.go is None and args.annotations is None:
    raise argparse.ArgumentError("one of the following arguments is required: --go or --annotations")
elif args.go is not None and args.annotations is not None:
    raise argparse.ArgumentError("the following arguments cannot be used simultaneously: --go and --annotations")
else:
    annotations_alias_type = "geneid" if args.go else "MGI"

section = Section(verbose = args.verbose)
genesynonyms = GeneSynonyms()

print(f"Loading data...")

section("Loading background gene set...", reset=True)

population_ids = read_geneset(args.population)
population_ids = genesynonyms.sequence_standardization(
    gene_sequence=population_ids,
    in_alias_type="genename",
    out_alias_type=annotations_alias_type
)
if None in population_ids:
    population_ids.remove(None)
population_ids = set(map(int, population_ids))

section("Loading study gene sets...")

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
    _study_ids = set(map(int, _study_ids))
    study_ids[os.path.basename(_study_file).rsplit(".", maxsplit=1)[0]] = _study_ids

section("Loading gene ontologies...")

go_dag = GODag(args.go)

section("Loading gene-to-go associations...")

if args.gene2go:
    annotations = Gene2GoReader(args.gene2go, taxids=[10090])
else:
    annotations = GafReader(args.annotations)
associations = annotations.get_ns2assc()

if args.verbose:
    for namespace, geneid2go in associations.items():
        print(f"{namespace} {len(geneid2go):,} annotated mouse genes")

print(f"Gene Ontology Enrichment Analysis...")

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

with ExcelWriter(args.outfile) as xlsx_writer:
    for cluster in study_ids.keys():
        xlsx_infile = f"{os.path.dirname(args.outfile)}/{cluster}"
        goea_results = read_excel(xlsx_infile, sheet_name=0)
        goea_results.to_excel(xlsx_writer, sheet_name=cluster)
