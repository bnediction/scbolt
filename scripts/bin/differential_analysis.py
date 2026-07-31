#!/usr/bin/env python

import argparse
import itertools
import json
import os
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Optional

import bonesistools as bt
import decoupler as dc
import networkx as nx
import numpy as np
import pandas as pd

from scbolt import cli, console


def collectri_to_grn(
    collectri: pd.DataFrame,
    sign_label: Optional[str] = "weight",
    remove_pmid: bool = False,
) -> nx.MultiDiGraph:
    if sign_label is not None:
        collectri = collectri.rename(columns={sign_label: "sign"})
    if remove_pmid is True:
        remove_pmid = "PMID" in collectri.columns
    return nx.from_pandas_edgelist(
        df=collectri.drop("PMID", axis=1) if remove_pmid else collectri,
        source="source",
        target="target",
        edge_attr=True,
        create_using=nx.MultiDiGraph,
    )


def gene_removal(
    df: pd.DataFrame, graph: nx.Graph, copy: bool = True
) -> Optional[pd.DataFrame]:
    df = df.copy() if copy is True else df
    genes_to_remove = list()
    for gene in df.columns:
        if gene not in graph.nodes:
            genes_to_remove.append(gene)
    df.drop(labels=genes_to_remove, axis="columns", inplace=True)
    return df if copy is True else None


def sign_likelihood(
    interaction_scores: dict,
    gene_set: Optional[Iterable[str]] = None,
    minimum_path_number: int = 3,
    relative_threshold: float = 0.75,
    enable_loop: bool = False,
):

    if not (0 < relative_threshold < 1):
        raise ValueError(
            "`relative_threshold` must be between 0 and 1: `relative_threshold` = {relative_threshold}"
        )
    selected_genes = set(interaction_scores)
    if gene_set is not None:
        selected_genes.intersection_update(gene_set)

    interactions = bt.logic.ig.infer_signed_interactions(
        scores=interaction_scores,
        genes=selected_genes,
        minimum_path_number=minimum_path_number,
        threshold=relative_threshold,
        allow_bidirectional=enable_loop,
    )
    interaction_signs = {gene: {} for gene in selected_genes}
    for source, target, data in interactions:
        interaction_signs[source][target] = data["sign"]

    return interaction_signs


def nexponential_fun(base, radius):
    return 1 / base ** np.arange(0, radius)


script_name = Path(__file__).name


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="differential_analysis",
        description="""Compute pairwise inter-cluster predecessor scores from binarized meta-observations.""",
        usage=f"python {script_name} [-h] <FILE> <PATH> [<args>]",
        formatter_class=cli.HelpFormatter,
    )

    parser.add_argument(
        "infile",
        type=lambda x: Path(x).resolve(),
        metavar="FILE",
        help="input file storing binarized meta-observations (format: csv)",
    )

    parser.add_argument(
        dest="outpath",
        type=lambda x: Path(x).resolve(),
        metavar="PATH",
        help="output directory storing sign likelihood and pairwise predecessor scores",
    )

    parser.add_argument(
        "--depth",
        "--radius",
        dest="radius",
        type=int,
        required=False,
        default=3,
        metavar="INT",
        help="maximum path length between a source and a target (default: 3)",
    )

    parser.add_argument(
        "--min-path-number",
        dest="min_path_number",
        type=int,
        required=False,
        default=1,
        metavar="INT",
        help=(
            "minimum number of paths required to consider a gene pair as source-target "
            "candidates (default: 1)"
        ),
    )

    parser.add_argument(
        "--base",
        dest="base",
        type=int,
        required=False,
        default=2,
        metavar="INT",
        help="base in the non-exponential weighting function (default: 2)",
    )

    parser.add_argument(
        "--relative-threshold",
        dest="threshold",
        type=float,
        action=cli.Range,
        min=0.0,
        max=1.0,
        required=False,
        default=0.75,
        help=(
            "relative path-score threshold required to consider a source-target gene pair "
            "(default: 0.75)"
        ),
    )

    parser.add_argument(
        "--enable-loop",
        dest="enable_loop",
        required=False,
        action="store_true",
        help="allow mutual influences between genes in a pair",
    )

    args = parser.parse_args()
    if args.base <= 1:
        raise ValueError(f"incorrect value for `base` argument : {args.base}")


    bdc = bt.logic.ba.BooleanPredecessorInference

    console.print_task(f"loading binarized matrix (file={console.format_path(args.infile)})")

    meta_bin = pd.read_csv(args.infile, index_col=0).transpose()

    collectri_db = dc.get_collectri(organism="mouse", split_complexes=True)
    grn = collectri_to_grn(collectri_db, sign_label="weight", remove_pmid=True)

    console.print_info(f"grn: {len(grn.nodes)} genes; {len(grn.edges)} interactions")

    identifiers = bt.resources.ncbi.identifiers()
    identifiers(meta_bin, axis=1, copy=False)
    identifiers(grn, copy=False)
    gene_set_before_cleaning = set(meta_bin.columns)
    gene_removal(meta_bin, grn, copy=False)
    gene_set = set(meta_bin.columns)

    console.print_info(
        f"dataframe: {len(gene_set_before_cleaning)} genes; {len(gene_set_before_cleaning)- len(gene_set)}/{len(gene_set_before_cleaning)} genes removed (no matching with grn genes)"
    )

    console.print_task("checking successors")

    console.print_info("extracting paths (method=depth-first search)")
    interaction_scores = bt.logic.ig.interaction_scores_from_walks(
        graph=grn,
        weights=nexponential_fun(base=args.base, radius=args.radius),
        max_depth=args.radius,
        genes=gene_set,
    )

    console.print_info("estimating pairwise gene sign likelihood")
    interaction_signs = sign_likelihood(
        interaction_scores=interaction_scores,
        gene_set=gene_set,
        minimum_path_number=args.min_path_number,
        relative_threshold=args.threshold,
        enable_loop=args.enable_loop,
    )

    with open(f"{args.outpath}/sign_likelihood.json", "w") as outfile:
        json.dump(interaction_signs, outfile)

    console.print_info("testing predecessors (method=differential Boolean calculus)")

    score_matrix = OrderedDict({condition: {} for condition in meta_bin.index})
    for c1, c2 in itertools.product(meta_bin.index, repeat=2):
        score_matrix[c1][c2] = 0

    for source, targets in interaction_signs.items():
        for target, sign in targets.items():
            pair_df = meta_bin.loc[:, [source, target]]
            for c1, c2 in itertools.product(meta_bin.index, repeat=2):
                _predecessor = bdc.pairwise_predecessor_test(
                    source_v1=pair_df.loc[c1, source],
                    source_v2=pair_df.loc[c2, source],
                    target_v1=pair_df.loc[c1, target],
                    target_v2=pair_df.loc[c2, target],
                    sign=sign,
                )
                if _predecessor is True:
                    score_matrix[c1][c2] += 1
                elif _predecessor is False:
                    score_matrix[c1][c2] -= 1
                else:
                    pass

    score_df = pd.DataFrame.from_dict(score_matrix, orient="index")

    console.print_task(
        f"saving differential analysis outputs (directory={os.path.relpath(args.outpath)})"
    )

    score_df.to_csv(f"{args.outpath}/pairwise_predecessor_scores.csv", sep=",", index=True)

    console.print_result("pairwise scores:")
    print(f"\n{score_df}\n")


if __name__ == "__main__":
    main()
