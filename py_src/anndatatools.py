from typing import Optional

import numpy as np

import anndata as ad
import pandas as pd
import scanpy as sc

def expression_with_cluster(
    adata: ad.AnnData,
    groupby: str,
    layer: Optional[str] = None,
    is_log: Optional[bool] = False
    ) -> pd.DataFrame:
    """Creates a counting dataframe with one last column corresponding to cluster associated to a cell.
    
    Parameters
    ----------
    adata
        Annotated data matrix.
    groupby
        Any key in anndata.obs corresponding to defined clusters or groups.
    layer
        Any key in anndata.layer.
        If not specify, counts are derived from anndata.X.
    is_log
        Boolean value specifying if the counts are logarithmized.
    """

    if layer and sc.preprocessing._simple.issparse(adata.layers[layer]):
        counts_df = pd.DataFrame.sparse.from_spmatrix(adata.layers[layer], index=adata.obs.index, columns = adata.var.index)
    elif layer:
         counts_df = pd.DataFrame(adata.layers[layer], index=adata.obs.index, columns = adata.var.index)
    elif sc.preprocessing._simple.issparse(adata.layers[layer]):
        counts_df = pd.DataFrame.sparse.from_spmatrix(adata.X, index=adata.obs.index, columns = adata.var.index)
    else:
        counts_df = pd.DataFrame(adata.X, index=adata.obs.index, columns = adata.var.index)
    
    if is_log:
        if "log1p" in adata.uns_keys() and adata.uns["log1p"].get('base') is not None:
            counts_df = np.expm1(counts_df * np.log(adata.uns['log1p']['base']))
        else:
            counts_df = np.expm1(counts_df)
    
    return counts_df.assign(cluster=adata.obs[groupby])

def log_fold_changes(
    adata: ad.AnnData,
    groupby: str,
    layer: Optional[str] = None,
    is_log: Optional[bool] =False,
    cluster_rebalancing: Optional[bool] = False
    ) -> pd.DataFrame:
    """Log2 fold change is a metric translating how much the transcript's expression
    has changed between cells in and out of a cluster. The reported values are based
    on a logarithmic scale to base 2 with respect to the fold change ratios.
    According to <https://www.biostars.org/p/453129/>, computed log2 fold changes
    are different between FindAllMarkers (package Seurat) and rank_gene_groups
    (module Scanpy). As mentionned, results derived from Scanpy are inconsistent.
    Furthermore, anndatatools computes this metric in the right way, with identical
    results to Seurat by keeping default options.

    Parameters
    ----------
    adata
        Annotated data matrix.
    groupby
        Any key in anndata.obs corresponding to defined clusters or groups.
    layer
        Any key in anndata.layer.
        If not specify, log2 fold changes are derived from anndata.X.
    is_log
        Boolean value specifying if the counts is logarithmized.
    cluster_rebalancing
        If no cluster rebalancing, cells are equally-weighted.
        Otherwise, cells are weighted with cluster size such as clusters are equally-weighted.
        It means that cells in small cluster have a greater weight than other cells in order
        to correct cluster size effects.
    """

    def add_one_cluster_log_fold_changes(log_fold_changes_df, _mean_in, _mean_out, cluster):

        log_fold_changes_one_cluster_df = pd.DataFrame(np.log2(_mean_in) - np.log2(_mean_out), columns=["log2foldchange"])
        log_fold_changes_one_cluster_df.reset_index(names="gene", inplace=True)
        log_fold_changes_one_cluster_df.insert(0, "cluster", cluster)
        log_fold_changes_df = pd.concat([log_fold_changes_df, log_fold_changes_one_cluster_df.copy()])
        return log_fold_changes_df
    
    log_fold_changes_df = pd.DataFrame(columns=["cluster","gene","log2foldchange"])
    counts_df = expression_with_cluster(adata, groupby=groupby, layer=layer, is_log=is_log)

    if cluster_rebalancing:
        
        mean_counts_df = counts_df.groupby(by="cluster", sort=True).mean()
        for cluster in sorted(pd.unique(adata.obs[groupby])):
            _mean_in = mean_counts_df.loc[cluster]
            _mean_out = mean_counts_df.drop(index=cluster, inplace=False).mean()
            log_fold_changes_df = add_one_cluster_log_fold_changes(log_fold_changes_df, _mean_in, _mean_out, cluster)
    
    else:

        for cluster in sorted(pd.unique(adata.obs[groupby])):
            counts_df = expression_with_cluster(adata, groupby=groupby, layer=layer, is_log=is_log)
            _mean_in = counts_df.loc[counts_df[groupby] == cluster, counts_df.columns != groupby].mean()
            _mean_out = counts_df.loc[counts_df[groupby] != cluster, counts_df.columns != groupby].mean()
            log_fold_changes_df = add_one_cluster_log_fold_changes(log_fold_changes_df, _mean_in, _mean_out, cluster)

    return log_fold_changes_df.reset_index(drop=True)
