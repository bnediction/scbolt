#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

from typing import Union

import anndata as ad

from utils.genesyn import GeneSynonyms

def set_ncbi_reference_name(
    adata: ad.AnnData,
    annotations: str = "var",
    copy: bool = False
) -> Union[ad.AnnData, None]:

    adata = adata.copy() if copy else adata

    if annotations == "obs":
        GeneSynonyms()(adata.obs, axis="index", copy=False)
    elif annotations == "var":
        GeneSynonyms()(adata.var, axis="index", copy=False)
    else:
        raise ValueError("`annotations` must take either value `obs` or `var`")
    
    return adata if copy else None
