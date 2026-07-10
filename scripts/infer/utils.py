#!/usr/bin/env python

import inspect
from typing import Any, Optional, Sequence
from pandas._typing import Axis
from pandas import DataFrame
import bonesis
import bonesistools as bt
import std


def get_cfg(df: DataFrame, axis: Axis = 0, genesyn: Optional[Any] = None) -> dict:
    """
    Convert configurations from dataframe format into dictionary format.

    Parameters
    ----------
    df: pd.DataFrame
        DataFrame object.
    axis: pd.Axis (default: 0)
        Whether configuration names are df.index (0 or 'index') or df.obs (1 or 'column').
    gensyn: callable (optional, default: None)
        Gene synonym converter used for standardizing gene names.

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

    if genesyn is not None:
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


def load_prior_network(
    domain: str,
    organism: str,
    genesyn: Any,
    dorothea_levels: Optional[Sequence[str]] = None,
    omnipath_version: str = "latest",
    hcop_version: str = "bundled",
    dorothea_api: str = "modern",
    dorothea_compatibility: bool = True,
):
    if domain == "collectri":
        std.print_info(
            f"loading CollecTRI prior network "
            f"(organism={organism}, version={omnipath_version}, "
            f"hcop={hcop_version})"
        )
        kwargs = {
            "organism": organism,
            "version": omnipath_version,
            "genesyn": genesyn,
        }
        if "hcop_version" in inspect.signature(bt.resources.omnipath.collectri).parameters:
            kwargs["hcop_version"] = hcop_version
        return bt.resources.omnipath.collectri(**kwargs)

    if domain == "dorothea":
        flavor = {"modern": "modern", "legacy": "legacy"}[dorothea_api]
        if dorothea_levels is None:
            levels = ["A", "B", "C", "D"] if flavor == "legacy" else ["A", "B", "C"]
        else:
            levels = list(dorothea_levels)
        std.print_info(
            f"loading DoRothEA prior network "
            f"(organism={organism}, levels={','.join(levels)}, "
            f"version={omnipath_version}, hcop={hcop_version}, "
            f"flavor={flavor}, compatibility={str(dorothea_compatibility).lower()})"
        )
        return bt.resources.omnipath.dorothea(
            organism=organism,
            levels=levels,
            version=omnipath_version,
            hcop_version=hcop_version,
            flavor=flavor,
            compatibility=dorothea_compatibility,
            genesyn=genesyn,
        )

    std.print_task(f"loading custom prior network (file={std.format_path(domain)})")
    return bt.logic.ig.read_influence_graph(
        infile=domain,
        genesyn=genesyn,
    )
