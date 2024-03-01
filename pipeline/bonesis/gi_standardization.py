#!/usr/bin/env python

import os
from pathlib import Path

from typing import Union, Any, Sequence, Dict, Set, List, Tuple

import pandas as pd
from pandas._typing import Axis

class GeneName(object):

    def __init__(self, gi_file: Path) -> None:
        self.gi_file = gi_file
        self.gene_synonyms = self.__synonyms_from_NCBI(self.gi_file)
        return None
    
    def __get__(self, attribute: str = None) -> Any:
        if attribute is None:
            return self.gene_synonyms
        else:
            return getattr(self, attribute)
    
    def __set__(self, gi_file: Path) -> None:
        self.gi_file = gi_file
        self.gene_synonyms = self.__synonyms_from_NCBI(self.gi_file)
        return None
   
    def __synonyms_from_NCBI(self, gi_file: Path) -> dict:
        """
        Create a dictionary matching each gene name to its NCBI reference gene name.
        For speeding up the task facing a large matrix from NCBI, the parsing of the NCBI gene data is run with awk.

        Parameters
        ----------
        gi_file
            Path to the NCBI gene info data

        Returns
        -------
        Return a dictionary where keys correspond to gene name and values correspond to reference gene name
        """

        # Parse the downloaded NCBI gene information
        gi_file_cut = Path(f"{gi_file}_cut")
        command_parsing = "awk -F'\t' '{print $3 \"\t\" $5 \"\t\" $11}' " + str(gi_file) + " | tr \| '\t' > " + str(gi_file_cut) + " ; sed -i 1d " + str(gi_file_cut)
        os.system(command_parsing)

        # Extract gene information
        gene_synonyms_dict = dict()
        reference_names = set()

        with open (gi_file_cut, "r") as file_synonyms:
            for gene in file_synonyms:
                gene = gene.strip().upper()
                gene_synonyms_list = gene.split("\t")
                ncbi_reference_name = gene_synonyms_list.pop(0)
                res = [_synonym for _synonym in gene_synonyms_list if (_synonym != "-" and _synonym != ncbi_reference_name)]

                # Create the dictionnary matching each gene name to its reference gene name
                gene_synonyms_dict[ncbi_reference_name] = ncbi_reference_name
                reference_names.add(ncbi_reference_name)

                for gene in res:
                    if gene not in reference_names and gene not in gene_synonyms_dict:
                        # Warning with NCBI list of synonyms: a noun can be the synonym of several reference names. Arbitrary, the choosen one is the first.
                        gene_synonyms_dict[gene] = ncbi_reference_name

        os.system(f"rm {str(gi_file_cut)}")
        return gene_synonyms_dict
    
    def get_reference_gene_name(self, gene_name: str) -> str:
        """
        Provide the reference name with respect to a gene name.

        Parameters
        ----------
        gene_name
            Name of a gene
        gene_synonyms_dict
            Dictionary where keys correspond to gene name and values correspond to reference gene name

        Returns
        -------
        Given a gene name, return its reference name.
        """

        gene_name = gene_name.upper()
        if gene_name in self.gene_synonyms:
            return self.gene_synonyms[gene_name]
        return gene_name

    def interaction_list_standardization(self, interactions_list: Sequence[Tuple[str, str, Dict[str, int]]]) -> List[Tuple[str, str, Dict[str, int]]]:
        """
        Create a copy of the input list of pairwise interactions, with each gene name replaced by its reference name.

        Parameters
        ----------
        interaction_list
            list of tuples containing string (source) + string (target) + dict (sign = -1 or 1)

        Returns
        -------
        return an interaction list where each gene name is converted into its reference value.
        """

        # Copy the interactions list by replacing each genename by its reference genename into it:
        standardized_interactions_list = list()
        for interaction in interactions_list:
            source = self.get_reference_gene_name(interaction[0])
            target = self.get_reference_gene_name(interaction[1])
            standardized_interactions_list.append((source, target, interaction[2]))

        return standardized_interactions_list

    def df_standardization(
        self,
        df: pd.DataFrame,
        axis: Axis = 0,
        genes_to_standardize: Sequence[str] = None,
        inplace: bool = False
    ) -> Path:
        """
        Replace gene name with its reference gene name into data

        Parameters
        ----------
        df
            dataframe where names must be standardized
        axis
            whether to rename labels from the index (0 or `index`) or columns (1 or `columns`)
        genes_to_standardize
            sequence containing gene names to standardize (default: all genes)
        inplace
            return a copy instead of updating `df`
        
        Returns
        -------
        Depending on `inplace`, update or return dataframe with standardized gene name.
        """

        df = df.copy() if not inplace else df

        if genes_to_standardize is None:
            genes_to_standardize = set(self.gene_synonyms.keys())
        else:
            genes_to_standardize = set(genes_to_standardize)
        _gene_synonyms = {gene:self.get_reference_gene_name(gene) for gene in genes_to_standardize if gene in self.gene_synonyms}
        df.rename(mapper=str.upper, axis=axis, inplace=True)
        df.rename(mapper=_gene_synonyms, axis=axis, inplace=True)

        if not inplace:
            return df
