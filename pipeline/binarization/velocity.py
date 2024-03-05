#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

from typing import Optional, Union, Any, Sequence, NamedTuple
from numbers import Number
from collections import namedtuple

import sys
import os, argparse
from pathlib import Path

import pandas as pd
import decoupler as dc
import numpy as np

import itertools
import networkx as nx

from utils.genesyn import GeneSynonyms

def collectri_to_grn(
    collectri: pd.DataFrame,
    sign_label: str = "weight",
    remove_pmid: bool = False
    ) -> nx.MultiDiGraph:
    if sign_label is not None:
        collectri = collectri.rename(columns = {sign_label:"sign"})
    if remove_pmid is True:
        remove_pmid = "PMID" in collectri.columns
    return nx.from_pandas_edgelist(
        df = collectri.drop("PMID", axis=1) if remove_pmid else collectri,
        source="source",
        target="target",
        edge_attr=True,
        create_using=nx.MultiDiGraph
    )

def gene_removal(df: pd.DataFrame, graph: nx.Graph, copy: bool=True) -> Union[pd.DataFrame, None]:
    df = df.copy() if copy is True else df
    genes_to_remove = list()
    for gene in df.columns:
        if gene not in graph.nodes:
            genes_to_remove.append(gene)
    print(f"{len(genes_to_remove)} genes in dataframe are not found in graph", file=sys.stderr)
    df.drop(labels=genes_to_remove, axis="columns", inplace=True)
    return df if copy is True else None

parser = argparse.ArgumentParser(
    prog="computation of inter-cluster velocities",
    description="""compute velocity between cluster with respect to binarized meta-observations""",
    usage=""""python velocity.py [-h] -i <path> [<args>]"""
)

parser.add_argument(
    "infile",
    type=lambda x: Path(x).resolve(),
    metavar="PATH",
    help="infile in csv format"
)

# args = parser.parse_args()

args = parser.parse_args("""data/rna/binarization/cluster_bin_node_clusters.csv""".split())

meta_bin = pd.read_csv(args.infile, index_col=0)
GeneSynonyms()(data=meta_bin, axis=1, copy=False)

collectri_db = dc.get_collectri(organism="mouse", split_complexes=True)
grn = collectri_to_grn(collectri_db, sign_label="weight", remove_pmid=True)
GeneSynonyms()(data=grn, copy=False)

print(f"GRN has {len(grn.nodes)} nodes and {len(grn.edges)} edges", file=sys.stderr)

gene_removal(meta_bin, grn, copy=False)

##########################

### Given a node and a radius, compute the subgraph

def get_edge_sign(graph: nx.Graph, root: Any, target: Any):
    edge_data = graph.get_edge_data(root, target)
    signs = {value["sign"] for value in edge_data.values()}
    for sign in signs:
        if sign not in [-1, 1]:
            raise ValueError("edge attribute `sign` is not equal to -1 or 1")
    if len(signs) == 1:
        return list(signs)[0]
    else:
        return 0

def get_path_sign(graph: nx.Graph, path: list):
    signs = iter(get_edge_sign(graph, path[dist], path[dist+1]) for dist in range(len(path) -1))
    effect = 1
    for sign in signs:
        if sign == -1:
            effect = - effect
        elif sign == 0:
            return 0
        elif sign == 1:
            pass
        else:
            raise ValueError("value of `sign` is not equal to -1, 0 or 1")
    return effect

def interaction_scoring(
    graph: nx.Graph,
    source: Any,
    target: Any,
    weights: Sequence[Number],
    radius: int=3
) -> NamedTuple:

    if len(weights) != radius:
        raise ValueError("length of `weight` is not equal to `radius`-1")

    paths = list(nx.algorithms.all_simple_paths(G=graph, source=source, target=target, cutoff=radius))
    if not paths:
        return namedtuple("InteractionPaths", ["score", "path_number", "maxscore"])(float("nan"), 0, float("nan"))
    else:
        _score, _maxscore = (0, 0)
        for n, path in enumerate(paths):
            _score += get_path_sign(graph, path) * weights[len(path) - 2]
            _maxscore += weights[len(path) - 2]
        return namedtuple("InteractionPaths", ["score", "path_number", "maxscore"])(_score, n, _maxscore)
    
### Create a dict such that [target][root] : score

gene_set = list(meta_bin.columns)

def all_interaction_scoring(
    graph: nx.Graph,
    weights: Sequence[Number],
    radius: int = 3,
    gene_set: Optional[Sequence[str]] = None,
    base: float = 0.75
) -> dict:

    interaction_signs = dict()
    if gene_set is None:
        gene_set = set(graph.nodes)
    else:
        gene_set = set(gene_set).intersection(set(graph.nodes))
    
    if not (0 < base < 1):
        raise ValueError("`base` is not between 0 and 1")
    
    interaction_signs = {gene: dict() for gene in gene_set}

    for u, v in itertools.combinations(gene_set, 2):
        from_u = interaction_scoring(graph=graph, source=u, target=v, weights=weights, radius=radius)
        from_v = interaction_scoring(graph=graph, source=v, target=u, weights=weights, radius=radius)
        _u_is_source = False
        _v_is_source = False
        _sign = 0
        if from_u.score != float("nan"):
            if abs(from_u.score) / from_u.maxscore >= from_u.maxscore * base:
                _u_is_source = True
                _sign = 1 if from_u.score / from_u.maxscore > 0 else -1
        if from_v.score != float("nan"):
            if abs(from_v.score) / from_v.maxscore >= from_v.maxscore * base:
                _v_is_source = True
                _sign = 1 if from_u.score / from_u.maxscore > 0 else -1
        if _u_is_source ^ _v_is_source:
            source = u if _u_is_source is True else v
            target = v if _u_is_source is True else u
            interaction_signs[source][target] = _sign
    
    return interaction_signs


radius=3
nexponential_weight = lambda base, radius: 1 / base**np.arange(0, radius)
weights = nexponential_weight(base=2, radius=radius)

interaction_dict = all_interaction_scoring(
    graph=grn,
    weights=weights,
    radius=radius,
    gene_set=set(meta_bin.columns)
)
