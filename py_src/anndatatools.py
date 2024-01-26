import types
from typing import Optional, Sequence, Union

from pathlib import Path

import numpy as np
from math import ceil
from scipy.stats import hypergeom
from scipy.sparse import csr_matrix, issparse, diags
from sklearn.metrics import pairwise_distances

import matplotlib.pyplot as plt, plot_settings
import color_settings as colour
from matplotlib.ticker import FormatStrFormatter
from matplotlib.colors import Colormap
from itertools import cycle
from color_settings import color_cycle

import anndata as ad
import pandas as pd

def _expression_with_cluster(
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
        Any key in adata.layers.
        If provided, use adata.layers[layer] for expression values instead of adata.X.
    is_log
        Boolean value specifying if the counts are logarithmized.
        If value parameter is `True`, perform an exponential transformation.
        If counts are still logarithmized but user want to keep logarithmized counts,
        please specify `False` to the value parameter.
    """

    if not isinstance(adata, ad.AnnData):
        raise TypeError(f"Argument `adata` must be of type {type(ad.AnnData)}, not {type(adata)}")

    if layer and issparse(adata.layers[layer]):
        counts_df = pd.DataFrame.sparse.from_spmatrix(adata.layers[layer], index=adata.obs.index, columns = adata.var.index)
    elif layer:
         counts_df = pd.DataFrame(adata.layers[layer], index=adata.obs.index, columns = adata.var.index)
    elif issparse(adata.layers[layer]):
        counts_df = pd.DataFrame.sparse.from_spmatrix(adata.X, index=adata.obs.index, columns = adata.var.index)
    else:
        counts_df = pd.DataFrame(adata.X, index=adata.obs.index, columns = adata.var.index)
    
    if is_log:
        if "log1p" in adata.uns_keys() and adata.uns["log1p"].get('base') is not None:
            counts_df = np.expm1(counts_df * np.log(adata.uns['log1p']['base']))
        else:
            counts_df = np.expm1(counts_df)
    
    return counts_df.assign(cluster=adata.obs[groupby])

def extract_markers(
    adata: ad.AnnData,
    keep_logfoldchanges: bool = False
    ) -> pd.DataFrame:
    """Extracts markers in adata.uns['rank_genes_groups'] and convert it into a marker-defined dataframe.
    
    Parameters
    ----------
    adata
        Annotated data matrix.
    keep_logfoldchanges
        Specify if dataframe columns contain log2_fold_changes computed with Scanpy.
        Since these values are inconsistent (<https://www.biostars.org/p/453129/>),
        one does prefer recompute consistent log2_fold_changes.
    """

    if not isinstance(adata, ad.AnnData):
        raise TypeError(f"Argument `adata` must be of type {type(ad.AnnData)}, not {type(adata)}")
    if "rank_genes_groups" in adata.uns.keys():
        markers_uns = adata.uns["rank_genes_groups"]
    else:
        raise ValueError("adata.uns does not contain key 'rank_genes_groups'.\
            Please use `scanpy.tl.rank_genes_groups` function before, aborting")
    
    groupby = markers_uns["params"]["groupby"]

    markers_d = {
        "gene":list(),
        "cluster":list(),
        "p_value":list(),
        "adj_p_value":list(),
        "score":list()
    }
    if keep_logfoldchanges:
        markers_d["log2foldchange"] = list()

    for cluster in sorted(adata.obs[groupby].unique()):
        markers_d["gene"].extend(markers_uns["names"][cluster])
        markers_d["cluster"].extend([cluster] * adata.n_vars)
        markers_d["p_value"].extend(markers_uns["pvals"][cluster])
        markers_d["adj_p_value"].extend(markers_uns["pvals_adj"][cluster])
        markers_d["score"].extend(markers_uns["scores"][cluster])
        if keep_logfoldchanges:
            markers_d["log2foldchange"].extend(markers_uns["logfoldchanges"][cluster])

    markers_df = pd.DataFrame.from_dict(markers_d, orient="columns")

    return markers_df

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
    
    if not isinstance(adata, ad.AnnData):
        raise TypeError(f"Argument `adata` must be of type {type(ad.AnnData)}, not {type(adata)}")
    
    log_fold_changes_df = pd.DataFrame(columns=["cluster","gene","log2foldchange"])
    counts_df = _expression_with_cluster(adata, groupby=groupby, layer=layer, is_log=is_log)

    if cluster_rebalancing:
        mean_counts_df = counts_df.groupby(by=groupby, sort=True).mean()
        for cluster in sorted(pd.unique(adata.obs[groupby])):
            _mean_in = mean_counts_df.loc[cluster]
            _mean_out = mean_counts_df.drop(index=cluster, inplace=False).mean()
            log_fold_changes_df = add_one_cluster_log_fold_changes(log_fold_changes_df, _mean_in, _mean_out, cluster)
    else:
        for cluster in sorted(pd.unique(adata.obs[groupby])):
            counts_df = _expression_with_cluster(adata, groupby=groupby, layer=layer, is_log=is_log)
            _mean_in = counts_df.loc[counts_df[groupby] == cluster, counts_df.columns != groupby].mean()
            _mean_out = counts_df.loc[counts_df[groupby] != cluster, counts_df.columns != groupby].mean()
            log_fold_changes_df = add_one_cluster_log_fold_changes(log_fold_changes_df, _mean_in, _mean_out, cluster)

    return log_fold_changes_df.reset_index(drop=True)

def hypergeometric_test(
    adata: ad.AnnData,
    signature: Sequence[str],
    markers: Sequence[str]
    ) -> float:
    """Computes the p-value (or survival function) of an hypergeometric
    distribution using scRNA-seq data in order to test whether marker genes
    significantly match signature genes.
    Given a population size N and a number of success states K,
    it describes the probability of having at least k successes
    in n draws, without replacement, where:
    - N is the number of genes in anndata,
    - K is the number of signature genes,
    - n is the number of markers,
    - k is the number of gene matching both signature genes and markers.
    Smaller the p-value, higher the probability that genes of the given
    cluster comes from the cell-type associated to the given signature.    

    Parameters
    ----------
    adata
        Annotated data matrix.
    signature
        Set of signature genes in a given cell-type.
        A signature is a set of overexpressed genes in a cell-type.
    markers
        Set of markers (genes) in a given cluster.
        A marker set is a set of overexpressed genes in a cluster.
    """

    if not isinstance(adata, ad.AnnData):
        raise TypeError(f"Argument `adata` must be of type {type(ad.AnnData)}, not {type(adata)}")
    
    background = set(adata.var.index)
    if not isinstance(signature, set):
        signature = set(signature)
    if not isinstance(markers, set):
        markers = set(markers)
    marked_genes = markers.intersection(signature)

    N = len(background)         # population size
    K = len(signature)          # number of success states
    n = len(markers)            # number of draws
    k = len(marked_genes)       # number of observed successes (matching genes)
    
    pvalue = hypergeom.sf(k = k, M = N, n = K, N = n, loc = 1)
    
    return pvalue

def _shared_nearest_neighbors_graph(
    adata: ad.AnnData,
    cluster_key: str,
    prune_snn: float
) -> csr_matrix:

    if not isinstance(adata, ad.AnnData):
        raise TypeError(f"Argument `adata` must be of type {type(ad.AnnData)}, not {type(adata)}")
    else:
        k_neighbors = adata.uns[cluster_key]["params"]["n_neighbors"] - 1
    if prune_snn < 0:
        raise ValueError("`prune_snn` parameter must be positive, aborting")
    elif prune_snn < 1:
        prune_snn = ceil(k_neighbors*prune_snn)
    elif prune_snn >= k_neighbors:
        raise ValueError("`prune_snn` parameter must be smaller than `n_neighbors` used for KNN computation, aborting")

    n_cells = adata.n_obs
    distances_key = adata.uns[cluster_key]["distances_key"]

    neighborhood_graph = adata.obsp[distances_key].copy()
    if not issparse(neighborhood_graph):
        neighborhood_graph = csr_matrix(neighborhood_graph)
    neighborhood_graph.data[neighborhood_graph.data > 0] = 1

    neighborhood_graph = neighborhood_graph * neighborhood_graph.transpose()
    neighborhood_graph -= (k_neighbors * diags(np.ones(n_cells), offsets=0, shape=(n_cells, n_cells)))
    neighborhood_graph.sort_indices()
    neighborhood_graph = neighborhood_graph.astype(dtype=np.int8)

    if prune_snn:
        mask = (neighborhood_graph.data <= prune_snn)
        neighborhood_graph.data[mask] = 0
        neighborhood_graph.eliminate_zeros()

    return neighborhood_graph

def shared_neighbors(
    adata: ad.AnnData,
    knn_key: str = "neighbors",
    snn_key: str = "shared_neighbors",
    prune_snn: Optional[float] = 1/15,
    metric: Optional[str] = "euclidean",
    normalize_similarities: bool = True,
    distances_key: Optional[str] = None,
    similarities_key: Optional[str] = None,
    copy: bool = False
) -> ad.AnnData:
    """Compute a shared neighborhood (SNN) graph of observations.

    The neighbor search relies on a previously computed neighborhood graph
    (such as kNN algorithm).

    Parameters
    ----------
    adata
        Annotated data matrix.
    knn_key
        If not specified, the used neighbors data are retrieved from .uns['neighbors'].
        If specified, the used neighbors data are retrieved from .uns[key_added].
    snn_key
        If not specified, the shared neighbors data are stored in .uns['shared_neighbors'].
        If specified, the shared neighbors data are added to .uns[key_added].
    prune_snn
        If zero value, no prunning is performed. If strictly positive, removes edge between two neighbors
        in the shared neighborhood graph who have a number of neighbors less than the specified value.
        Value can be relative (float between 0 and 1) or absolute (integer between 1 and k).
    metric
        Metric used for computing distances between two neighbors by using .obsm['X_pca'].
    normalize_similarities
        If false, similarities provide the absolute number of shared neighbors (integer between 0 and k),
        otherwise provide the relative number of shared neighbors (float between 0 and k).
    distances_key
        If specified, distances are stored in .obsp[distances_key],
        otherwise in .obsp[snn_key+'_distances'].
    similarities_key
        If specified, distances are stored in .obsp[similarities_key],
        otherwise in .obsp[snn_key+'_similarities'].
    copy
        Return a copy instead of writing to adata.

    Returns
    -------
    Depending on `copy`, updates or returns `adata` with the following:

    See `snn_key` parameter description for the storage path of
    similarities and distances.

    **similarities** : sparse matrix.
        Weighted adjacency matrix of the shared neighborhood graph.
        Weights should be interpreted as number of shared neighbors.
    **distances** : sparse matrix of dtype `float64`.
        Instead of decaying weights, this stores distances for each pair of
        neighbors.
    """

    if not isinstance(adata, ad.AnnData):
        raise TypeError(f"Argument `adata` must be of type {type(ad.AnnData)}, not {type(adata)}")
    if knn_key not in adata.uns:
        raise ValueError((
            "Neighborhood graph not already computed or not finding. "
            "Please use `scanpy.pp.neighbors` function before or "
            "specify `key_added` parameter when scanpy.pp.neighbors has been called, aborting"
    ))
    if prune_snn is None:
        prune_snn = 0
    if metric is None:
        metric = "euclidean"
    if distances_key is None:
        distances_key = f"{snn_key}_distances"
    if similarities_key is None:
        similarities_key = f"{snn_key}_similarities"
    n_neighbors = adata.uns[knn_key]["params"]["n_neighbors"]

    adata = adata.copy() if copy else adata
    
    snn_graph = _shared_nearest_neighbors_graph(adata, cluster_key=knn_key, prune_snn = prune_snn)

    n_pcs = adata.uns[knn_key]["params"]["n_pcs"]

    X = adata.obsm["X_pca"][:,0:n_pcs]
    zeros_ones = snn_graph.toarray()
    zeros_ones[zeros_ones > 0] = 1
    
    distances_matrix = pairwise_distances(X, metric=metric)
    distances_matrix = np.multiply(zeros_ones, distances_matrix)
    distances_matrix = csr_matrix(distances_matrix)
    similarities_matrix = snn_graph.copy()
    if normalize_similarities:
        similarities_matrix = similarities_matrix.astype(float)
        similarities_matrix.data /= n_neighbors

    adata.obsp[distances_key] = distances_matrix
    adata.obsp[similarities_key] = similarities_matrix

    adata.uns[snn_key] = dict()
    adata.uns[snn_key]["distances_key"] = distances_key
    adata.uns[snn_key]["similarities_key"] = similarities_key
    adata.uns[snn_key]["params"] = {
        "knn_base": f"adata.uns['{knn_key}']",
        "prune_snn": prune_snn if prune_snn >= 1 else ceil(n_neighbors*prune_snn),
        "metric": metric
    }

    return adata if copy else None

def __default_plot(
    plot: types.FunctionType
):

    def wrapper(
        adata: ad.AnnData,
        obs: str,
        obsm: str,
        xlabel: Optional[str] = None,
        ylabel: Optional[str] = None,
        colors: Optional[Union[Sequence[Sequence[str]], cycle, Colormap]] = None,
        **kwargs
    ):

        if obs not in adata.obs:
            raise ValueError(f"adata.obs[{obs}] does not exist, aborting")
        if obsm not in adata.obsm:
            raise ValueError(f"adata.obsm[{obsm}] does not exist, aborting")

        if xlabel is None:
            xlabel = ""
        if ylabel is None:
            ylabel = ""

        if colors is None:
            colors = color_cycle

        fig, ax = plot(
            adata,
            obs,
            obsm,
            xlabel,
            ylabel,
            colors,
            **kwargs
        )
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        plt.sca(ax)
        ax.xaxis.set_major_formatter(kwargs["formatter"]) if "formatter" in kwargs else ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
        ax.yaxis.set_major_formatter(kwargs["formatter"]) if "formatter" in kwargs else ax.yaxis.set_major_formatter(FormatStrFormatter("%g")) 
        
        return fig, ax
    
    return wrapper

@__default_plot
def __scatterplot_discrete(
    adata: ad.AnnData,
    obs: str,
    obsm: str,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    colors: Optional[Union[Sequence[Sequence[str]], cycle]] = None,
    **kwargs
):

    if len(adata.obs[obs].unique()) < 2:
        raise ValueError(f"adata.obs[{obs}] specifies only one category, aborting")
    elif "print_legend" in kwargs:
        print_legend = kwargs["print_legend"]
    elif len(adata.obs[obs].unique()) == 2:
        print_legend = True
    else:
        print_legend = False
    
    fig, ax = plt.subplots(nrows=1, ncols=1)
    fig.set_figheight(kwargs["figheight"] if "figheight" in kwargs else 5)
    fig.set_figwidth(kwargs["figwidth"] if "figwidth" in kwargs else 5)
        
    for _cluster, _color in zip(sorted(adata.obs[obs].unique()), colors):
        idx = np.where(adata.obs[obs] == _cluster)[0]
        if print_legend:
            ax.scatter(adata.obsm[obsm][idx,0], adata.obsm[obsm][idx,1], s=2, facecolors=_color, edgecolors="none", alpha=1, label=_cluster)
        else:
            ax.scatter(adata.obsm[obsm][idx,0], adata.obsm[obsm][idx,1], s=2, facecolors=_color, edgecolors="none", alpha=1)

    if print_legend:
        ax.legend(markerscale=5, edgecolor=colour.black)
    
    return fig, ax

@__default_plot
def __scatterplot_continuous(
    adata: ad.AnnData,
    obs: str,
    obsm: str,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    colors: Optional[Colormap] = None,
    **kwargs
):
    if colors:
        _cmap = colors.name
    else:
        _cmap="autumn"

    fig, ax = plt.subplots(nrows=1, ncols=1)
    fig.set_figheight(kwargs["figheight"] if "figheight" in kwargs else 5)
    fig.set_figwidth(kwargs["figwidth"] if "figwidth" in kwargs else 6.5)

    sc = ax.scatter(
        adata.obsm[obsm][:,0],
        adata.obsm[obsm][:,1],
        s=3,
        c=adata.obs[obs],
        cmap=_cmap,
        edgecolors="none",
        alpha=1
    )
    fig.colorbar(sc)

    return fig, ax

def scatterplot(
    adata: ad.AnnData,
    obs: str,
    obsm: str,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    colors: Optional[Colormap] = None,
    outfile: Optional[Path] = None,
    **kwargs
):
    """Compute a scatterplot between the two first columns of .obsm[`obsm`]
    by using a classification/clusterization with respect to .obs[`obs`].

    Parameters
    ----------
    adata
        Annotated data matrix.
    obs
        The classification is retrieved by .obs[`obs`], which must be categorical/qualitative values.
    obsm
        The data points are retrieved by the first and second columns in .obsm[`obsm`].
    xlabel
        Set the label for the x-axis.
    ylabel
        Set the label for the y-axis.
    colors
        Visualization of the mapping from a list of color values.
    outfile
        If specified, save the figure.
    **kwargs
        Supplemental features for figure plotting:
        - figheight[float]: specify the figure height
        - figwidth[float]: specify the figure width
        - formatter[matplotlib.ticker.FormatStrFormatter]: specify the format on x- and y-axis.
        - print_legend[bool]: when .obs[`obs`] are discrete values, specify whether to draw legend
    
    Returns
    -------
    Depending on `outfile`, save figure or create a current figure.
    """

    if pd.api.types.is_float_dtype(adata.obs[obs]):
        fig, ax = __scatterplot_continuous(
            adata,
            obs,
            obsm,
            xlabel,
            ylabel,
            colors,
            **kwargs
        )
    elif pd.api.types.is_integer_dtype(adata.obs[obs]) or \
         pd.api.types.is_bool_dtype(adata.obs[obs]) or \
         pd.api.types.is_string_dtype(adata.obs[obs]) or \
         pd.api.types.is_categorical_dtype(adata.obs[obs]):
        fig, ax = __scatterplot_discrete(
            adata,
            obs,
            obsm,
            xlabel,
            ylabel,
            colors,
            **kwargs
        )
    
    if outfile:
        plt.savefig(outfile)
        plt.close()
        return None
    else:
        return fig, ax
