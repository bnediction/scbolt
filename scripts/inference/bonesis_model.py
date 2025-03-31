#!/usr/bin/env python

from pathlib import Path
from bonesistools.databases.genesyn import GeneSynonyms

import pandas as pd

from bonesis import BoNesis

def bomodel(bo: BoNesis, file: Path) -> None:
    with open(file, "r") as file:
        for line in file:
            eval(line)
    return None

def load_bin(file: Path, gene_synonyms: GeneSynonyms = None) -> dict:
    meta_bin = pd.read_csv(file, index_col=0)
    if gene_synonyms is not None and isinstance(gene_synonyms, GeneSynonyms):
        gene_synonyms.df_standardization(meta_bin, axis=0, copy=False)
    return {config: genes.dropna().to_dict() for config, genes in meta_bin.items()}
