#!/usr/bin/env python

from pandas._typing import Axis
from pandas import DataFrame
from bonesistools.databases.ncbi import GeneSynonyms

def get_cfg(
    df: DataFrame,
    axis: Axis=0,
    genesyn: GeneSynonyms=None
) -> dict:
    """
    Convert configurations instantiated in dataframe into dictionary.

    Parameters
    ----------
    df
        DataFrame object
    axis
        whether configuration names are df.index (0 or 'index') or df.obs (1 or 'column')
    gensyn
        GeneSynonyms object, used for standardizing gene names
    
    Returns
    -------
    return Dict object.
    """
    
    if axis in [0, "index"]:
        df = df.copy().T
    elif axis in [1, "column"]:
        pass
    else:
        raise ValueError(f"invalid value for 'axis' (got {axis}, expected 'index' or 'column')")
    
    if genesyn is not None and isinstance(genesyn, GeneSynonyms):
        genesyn.df_standardization(
            df,
            axis=0,
            copy=False
        )

    return {config: genes.dropna().to_dict() for config, genes in df.items()}