#!/usr/bin/env python

# wget --quiet --show-progress --directory-prefix=data/public/enrichment https://current.geneontology.org/ontology/subsets/goslim_mouse.obo
# wget --quiet --show-progress --directory-prefix=data/public/enrichment https://current.geneontology.org/annotations/mgi.gaf.gz
# https://geneontology.org/docs/download-go-annotations/

import warnings
warnings.filterwarnings("ignore")

import argparse
from pathlib import Path

from utils.genesyn import GeneSynonyms

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

arguments = """data/rna/enrichment/ct/cluster0.txt data/rna/enrichment/ct/background.txt data/public/enrichment/go-basic.obo data/public/enrichment/mgi.gaf data/public/enrichment/gene2go"""

args = parser.parse_args(arguments.split())

gene_syn = GeneSynonyms()

study_ids = read_geneset(args.study)
population_ids = read_geneset(args.population)

godag = GODag(args.go)

gaf = GafReader(args.annotations)
associations = dict()
for association in gaf.associations:
    gene_symbol = association.DB_Symbol
    ncbi_gene_symbol = gene_syn.get_reference_gene_name(gene_symbol)
    if ncbi_gene_symbol in associations:
        associations[ncbi_gene_symbol].append(association.GO_ID)
    else:
        associations[ncbi_gene_symbol] = [association.GO_ID]

########


gad = gaf.get_ns2assc()

gaf.associations

for namespace, associations in gad.items():
    for protein_id, go_ids in sorted(associations.items())[:3]:
        print("{NS} {PROT:7} : {GOs}".format(
            NS=namespace,
            PROT=protein_id,
            GOs=' '.join(sorted(go_ids))))


# anno = IdToGosReader(args.annotations, godag=godag)

annotations = Gene2GoReader(args.gene2go, taxids=[10090])
associations = annotations.get_ns2assc()

if args.verbose:
    for namespace, gene2go in associations.items():
        print(f"{namespace}: {len(gene2go):,} annotated mouse genes")

goeaobj = GOEnrichmentStudyNS(
        GeneID2nt_mus.keys(), # List of mouse protein-coding genes
        associations, # geneid/GO associations
        godag,
        propagate_counts = False,
        alpha = 0.05,
        methods = ['fdr_bh'])

