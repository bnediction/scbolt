#!/usr/bin/env python

from typing import Optional
from pandas._typing import Axis
from pandas import DataFrame
import bonesis
from bonesistools.databases.ncbi import GeneSynonyms


def get_cfg(
    df: DataFrame, axis: Axis = 0, genesyn: Optional[GeneSynonyms] = None
) -> dict:
    """
    Convert configurations from dataframe format into dictionary format.

    Parameters
    ----------
    df: pd.DataFrame
        DataFrame object.
    axis: pd.Axis (default: 0)
        Whether configuration names are df.index (0 or 'index') or df.obs (1 or 'column').
    gensyn: bt.dbs.ncbi.GeneSynonyms (optional, default: None)
        GeneSynonyms object used for standardizing gene names.

    Returns
    -------
    Return Dict object.
    """

    if axis in [0, "index"]:
        df = df.copy().T
    elif axis in [1, "column"]:
        pass
    else:
        raise ValueError(
            f"invalid value for 'axis' (got {axis}, expected 'index' or 'column')"
        )

    if genesyn is not None and isinstance(genesyn, GeneSynonyms):
        genesyn(df, axis=0, copy=False)

    return {config: genes.to_dict() for config, genes in df.items()}


def load_bonesis_code(
    bo: bonesis.BoNesis,
    code: str,
    filename: str = "<bonesis>",
    namespace: dict | None = None,
) -> dict:
    """
    Load BoNesis DSL code through the safe AST validator.

    The `bo` symbol is kept in the namespace for compatibility with older
    scBOLT specifications using `bo.obs(...)`, while the BoNesis language
    symbols also allow direct DSL calls such as `obs(...)`.
    """

    if namespace is None:
        namespace = {}
    namespace.setdefault("bo", bo)

    try:
        return bo.load_code(
            code,
            defs=namespace,
            safe=True,
            filename=filename,
        )
    except TypeError as error:
        if "unexpected keyword argument" in str(error):
            raise RuntimeError(
                "safe BoNesis DSL loading requires BoNesis with "
                "`load_code(..., safe=True)` support"
            ) from error
        raise
