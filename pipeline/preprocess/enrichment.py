#!/usr/bin/env python

# wget --quiet --show-progress --directory-prefix=data/public/enrichment https://current.geneontology.org/ontology/subsets/goslim_mouse.obo
# wget --quiet --show-progress --directory-prefix=data/public/enrichment https://current.geneontology.org/annotations/mgi.gaf.gz
# https://geneontology.org/docs/download-go-annotations/

import warnings
warnings.filterwarnings("ignore")

import argparse
from pathlib import Path
from utils.stdout import Section, disable_print

from databases.genesyn import GeneSynonyms

from goatools.utils import read_geneset
from goatools.obo_parser import GODag
from goatools.anno.idtogos_reader import IdToGosReader
from goatools.anno.gaf_reader import GafReader
from goatools.anno.genetogo_reader import Gene2GoReader
from goatools.goea.go_enrichment_ns import GOEnrichmentStudyNS

parser = argparse.ArgumentParser(
    prog="Gene enrichment analysis",
    description="""Perform gene ontology enrichment analysis.""",
    usage="python markers.py [-h] <FILE> <FILE> <FILE> <FILE> <PATH> -g <LITERAL> [-c <LITERAL> <args>]"
)

parser.add_argument(
    "study",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="txt file containing interest gene set"
)

parser.add_argument(
    "population",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="txt file containing background gene set"
)

parser.add_argument(
    "go",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="obo file (DAG containing HPO terms)"
)

parser.add_argument(
    "annotations",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="annotation.tab file (annotations of genes-to-HPO terms)"
)

parser.add_argument(
    "gene2go",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="NCBI gene-to-GO terms file)"
)

parser.add_argument(
    "-v", "--verbose",
    dest="verbose",
    required=False,
    action="store_true",
    help="display additional information"
)

arguments = """data/rna/enrichment/ct/cluster0.txt data/rna/enrichment/ct/background.txt data/public/enrichment/go-basic.obo data/public/enrichment/mgi.gaf data/public/enrichment/gene2go --verbose"""

args = parser.parse_args(arguments.split())

section = Section(verbose = args.verbose)
genesynonyms = GeneSynonyms()

print(f"Loading data...")

section("Loading background gene set...", reset=True)

with disable_print():
    study_ids = read_geneset(args.study)
    study_ids = genesynonyms.sequence_standardization(
        gene_sequence=study_ids,
        in_alias_type="genename",
        out_alias_type="geneid"
    )
    if None in study_ids:
        study_ids.remove(None)
    study_ids = set(map(int, study_ids))

    population_ids = read_geneset(args.population)
    population_ids = genesynonyms.sequence_standardization(
        gene_sequence=population_ids,
        in_alias_type="genename",
        out_alias_type="geneid"
    )
    if None in population_ids:
        population_ids.remove(None)
    population_ids = set(map(int, population_ids))

section("Loading gene ontologies...")

with disable_print():
    go_dag = GODag(args.go)

section("Loading geneid-to-go associations...")

with disable_print():
    annotations = Gene2GoReader(args.gene2go, taxids=[10090])
    associations = annotations.get_ns2assc()

if args.verbose:
    for namespace, geneid2go in associations.items():
        print(f"{namespace} {len(geneid2go):,} annotated mouse genes")

# The following give a little more results:
# annotations = GafReader(args.annotations)
# geneid2go = annotations.get_ns2assc()

print(f"Gene Ontology Enrichment Analysis...")

with disable_print():
    goea = GOEnrichmentStudyNS(
        pop=population_ids,
        ns2assoc=associations,
        godag=go_dag,
        propagate_counts=False,
        alpha=0.05,
        methods=['fdr_bh']
    )

goea_results = goea.run_study(study_ids)
goea.wr_xlsx("nbt3102_geneids.xlsx", goea_results)
