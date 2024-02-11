import types
from typing import Optional, Sequence, Union, Any

import sys
from pathlib import Path

import numpy as np
from math import ceil
from scipy.stats import hypergeom
from scipy.sparse import csr_matrix, issparse, diags
from sklearn.metrics import pairwise_distances

import networkx as nx

import matplotlib.pyplot as plt, plot_settings
import color_settings as colour
from matplotlib.axes._axes import Axes
from matplotlib.ticker import FormatStrFormatter
from matplotlib.colors import Colormap
from mpl_toolkits import mplot3d
from mpl_toolkits.mplot3d import Axes3D
from itertools import cycle
from color_settings import COLORS

import anndata as ad
import pandas as pd

def adata_arg_checking(
    function: types.FunctionType
):

    def wrapper(adata, *args, **kwargs):
        if not isinstance(adata, ad.AnnData):
            raise TypeError(f"Argument `adata` must be of type {type(ad.AnnData)}, not {type(adata)}")
        return function(adata, *args, **kwargs)
    
    return wrapper

@adata_arg_checking
def anndata_to_dataframe(
    adata: ad.AnnData,
    obs: Optional[Union[str, Sequence[str]]] = None,
    layer: Optional[str] = None,
    is_log: Optional[bool] = False
) -> pd.DataFrame:
    """Convert Anndata instance into Dataframe instance.
    
    Parameters
    ----------
    adata
        Annotated data matrix.
    var
        Any key or key set in anndata.obs corresponding to defined clusters or groups.
        If specified, add adata.var.loc[var] to dataframe.
    layer
        Any key in adata.layers.
        If provided, use adata.layers[layer] for expression values instead of adata.X.
    is_log
        Boolean value specifying if the counts are logarithmized.
        If value parameter is `True`, perform an exponential transformation.
        If counts are still logarithmized but user want to keep logarithmized counts,
        please specify `False` to the value parameter.
    
    Returns
    -------
    Dataframe providing information about counts and optionnaly other additionnal chosen information.
    """

    if layer and issparse(adata.layers[layer]):
        counts_df = pd.DataFrame(adata.layers[layer].toarray(), index=adata.obs.index, columns = adata.var.index)
    elif layer:
         counts_df = pd.DataFrame(adata.layers[layer], index=adata.obs.index, columns = adata.var.index)
    elif issparse(adata.layers[layer]):
        counts_df = pd.DataFrame(adata.X.toarray(), index=adata.obs.index, columns = adata.var.index)
    else:
        counts_df = pd.DataFrame(adata.X, index=adata.obs.index, columns = adata.var.index)
    
    if is_log:
        if "log1p" in adata.uns_keys() and adata.uns["log1p"].get('base') is not None:
            counts_df = np.expm1(counts_df * np.log(adata.uns['log1p']['base']))
        else:
            counts_df = np.expm1(counts_df)
    
    if obs is not None:
        counts_df.loc[:,obs] = adata.obs[[obs]] if isinstance (obs, str) else adata.obs[obs]
    
    return counts_df

@adata_arg_checking
def extract_rank_genes_groups(
    adata: ad.AnnData,
    logfc_keeping: Optional[bool] = None
) -> pd.DataFrame:
    """Extracts information in adata.uns['rank_genes_groups'] in a comprehensible way.
    
    Parameters
    ----------
    adata
        Annotated data matrix.
    keep_logfoldchanges
        Specify if dataframe columns contain log2_fold_changes computed with Scanpy.
        Since these values are inconsistent (<https://www.biostars.org/p/453129/>),
        one does prefer recompute consistent log2_fold_changes.
    
    Returns
    -------
    Dataframe with information related to gene rankings. Need to use `scanpy.tl.rank_genes_groups` function
    on anndata object before.
    """

    if "rank_genes_groups" in adata.uns.keys():
        markers_uns = adata.uns["rank_genes_groups"]
    else:
        raise ValueError("adata.uns does not contain key 'rank_genes_groups'.\
            Please use `scanpy.tl.rank_genes_groups` function before, aborting")
    
    groupby = markers_uns["params"]["groupby"]

    markers_d = {key: list() for key in ["genes", "clusters", "pvals", "adj_pvals", "scores", "log_fc"]}

    for cluster in sorted(adata.obs[groupby].unique()):
        markers_d["genes"].extend(markers_uns["names"][cluster])
        markers_d["clusters"].extend([cluster] * adata.n_vars)
        markers_d["pvals"].extend(markers_uns["pvals"][cluster])
        markers_d["adj_pvals"].extend(markers_uns["pvals_adj"][cluster])
        markers_d["scores"].extend(markers_uns["scores"][cluster])
        if logfc_keeping is True:
            markers_d["log_fc"].extend(markers_uns["logfoldchanges"][cluster])
        else:
            markers_d["log_fc"].extend([float("nan")] * adata.n_vars)

    return pd.DataFrame.from_dict(markers_d, orient="columns")

@adata_arg_checking
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
    (module Scanpy) functions. As mentionned, results derived from Scanpy are inconsistent.
    This current function `log_fold_changes` computes it in the right way, with identical
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

    def compute_logfc(mean_in, mean_out, cluster):

        __df = pd.DataFrame(np.log2(mean_in) - np.log2(mean_out), columns=["log_fc"])
        __df.reset_index(names="genes", inplace=True)
        __df.insert(0, "clusters", cluster)
        return __df
    
    logfc_df = pd.DataFrame(columns=["clusters","genes","log_fc"])
    counts_df = anndata_to_dataframe(adata, obs=groupby, layer=layer, is_log=is_log)

    if cluster_rebalancing:
        mean_counts_df = counts_df.groupby(by=groupby, sort=True).mean()
        for cluster in sorted(pd.unique(adata.obs[groupby])):
            _mean_in = mean_counts_df.loc[cluster]
            _mean_out = mean_counts_df.drop(index=cluster, inplace=False).mean()
            _logfc_df = compute_logfc(_mean_in, _mean_out, cluster)
            logfc_df = pd.concat([logfc_df, _logfc_df.copy()])
    else:
        for cluster in sorted(pd.unique(adata.obs[groupby])):
            _mean_in = counts_df.loc[counts_df[groupby] == cluster, counts_df.columns != groupby].mean()
            _mean_out = counts_df.loc[counts_df[groupby] != cluster, counts_df.columns != groupby].mean()
            _logfc_df = compute_logfc(_mean_in, _mean_out, cluster)
            logfc_df = pd.concat([logfc_df, _logfc_df.copy()])
            del _logfc_df

    return logfc_df.reset_index(drop=True)

def update_logfoldchanges(
    df: pd.DataFrame,
    adata: ad.AnnData,
    groupby: str,
    layer: str,
    is_log: Optional[bool] = True,
    cluster_rebalancing: Optional[bool] = False,
    threshold: Optional[float] = None
) -> pd.DataFrame:

    logfc_df = log_fold_changes(
        adata,
        groupby=groupby,
        layer=layer,
        is_log=is_log,
        cluster_rebalancing=cluster_rebalancing
    )
    df = df.loc[:, df.columns != "log_fc"]
    if threshold:
        logfc_df = logfc_df.loc[logfc_df["log_fc"] > threshold]
    df = pd.merge(
        df,
        logfc_df,
        left_on=["genes", "clusters"],
        right_on=["genes", "clusters"],
        how="inner"
    )
    return df

def hypergeometric_test(
    adata: ad.AnnData,
    signature: Sequence[str],
    markers: Sequence[str],
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
    
    return hypergeom.sf(k = k, M = N, n = K, N = n, loc = 1)

@adata_arg_checking
def multiple_hypergeometric_test(
    adata: ad.AnnData,
    signatures: dict,
    markers: pd.DataFrame,
    cluster: str,
) -> dict:

    _markers = markers[markers["clusters"] == cluster]["genes"]
    return {cell_type: hypergeometric_test(adata, signature, _markers) for cell_type, signature in signatures.items()}

@adata_arg_checking
def get_info(
    adata: ad.AnnData,
    signatures: dict,
    markers: pd.DataFrame,
    groupby: str = "cluster",
    by: Optional[Any] = None,
) -> dict:

    columns = ["genes", "clusters", "pvals", "adj_pvals", "scores", "log_fc"]
    for idx, column in enumerate(columns):
        if not column == markers.columns[idx]:
            raise ValueError("`markers` dataframe must contain specific rows with the specific order\
                `genes`, `clusters`, `pvals`, `adj_pvals`, `scores`, `log_fc`")

    if by:
        group_ad = adata[adata.obs[groupby] == by]
        group_info_d = dict()
        group_info_d["n_cells"] = group_ad.n_obs
        group_info_d["proportion_cells"] = round(group_ad.n_obs / adata.n_obs, ndigits=6)
        proportion_phases = group_ad.obs["pypairs_max_class"].value_counts() / group_ad.n_obs
        group_info_d.update({phase: round(proportion_phases[phase], ndigits=6) for phase in sorted(proportion_phases.index)})
        group_info_d["median_expressed_genes"] = group_ad.obs["n_genes_by_counts"].median()
        group_info_d["median_total_counts"] = group_ad.obs["total_counts"].median()
        group_info_d["median_proportion_mito"] = f"{group_ad.obs['pct_counts_mitochondrion'].median():.4f}%"
        pvalues_d = multiple_hypergeometric_test(group_ad, signatures, markers, cluster=by)
        group_info_d.update({cell_type: round(pvalue, ndigits=6) for cell_type, pvalue in pvalues_d.items()})
        return group_info_d
    else:
        return {group: get_info(adata, signatures, markers, groupby=groupby, by=group) for group in sorted(adata.obs[groupby].unique())}

@adata_arg_checking
def _shared_nearest_neighbors_graph(
    adata: ad.AnnData,
    cluster_key: str,
    prune_snn: float
) -> csr_matrix:

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

@adata_arg_checking
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
        colors: Union[Sequence[Sequence[str]], cycle, Colormap] = None,
        n_components: Optional[int] = 2,
        **kwargs
    ):

        if obs not in adata.obs:
            raise ValueError(f"adata.obs[{obs}] does not exist, aborting")
        if obsm not in adata.obsm:
            raise ValueError(f"adata.obsm[{obsm}] does not exist, aborting")

        fig, ax = plot(
            adata,
            obs,
            obsm,
            colors,
            n_components,
            **kwargs
        )

        if "xlabel" in kwargs:
            ax.set_xlabel("" if kwargs["xlabel"] is None else kwargs["xlabel"])
        if "ylabel" in kwargs:
            ax.set_ylabel("" if kwargs["ylabel"] is None else kwargs["ylabel"])
        if "zlabel" in kwargs and n_components > 2:
            ax.set_zlabel("" if kwargs["zlabel"] is None else kwargs["zlabel"])
        
        if "tick_params" in kwargs:
            ax.tick_params(**kwargs["tick_params"])
        else:
            if "xtick_params" in kwargs:
                ax.tick_params(axis="x", **kwargs["xtick_params"])
            if "ytick_params" in kwargs:
                ax.tick_params(axis="y", **kwargs["ytick_params"])
            if n_components ==3 and "ztick_params" in kwargs:
                ax.tick_params(axis="z", **kwargs["ztick_params"])

        plt.sca(ax)
        ax.xaxis.set_major_formatter(kwargs["formatter"]) if "formatter" in kwargs else ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
        ax.yaxis.set_major_formatter(kwargs["formatter"]) if "formatter" in kwargs else ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
        if n_components == 3:
            ax.zaxis.set_major_formatter(kwargs["formatter"]) if "formatter" in kwargs else ax.zaxis.set_major_formatter(FormatStrFormatter("%g"))

        if n_components == 3 and "background_visible" in kwargs:
            if kwargs["background_visible"] is False:
                ax.xaxis.pane.fill = False
                ax.yaxis.pane.fill = False
                ax.zaxis.pane.fill = False
                ax.xaxis.pane.set_edgecolor("w")
                ax.yaxis.pane.set_edgecolor("w")
                ax.zaxis.pane.set_edgecolor("w")

        return fig, ax
    
    return wrapper

@__default_plot
def __scatterplot_discrete(
    adata: ad.AnnData,
    obs: str,
    obsm: str,
    colors: Optional[Union[Sequence[Sequence[str]], cycle]] = None,
    n_components: Optional[int] = 2,
    **kwargs
):

    if len(adata.obs[obs].unique()) < 2:
        raise ValueError(f"adata.obs[{obs}] specifies only one category, aborting")
    elif "add_legend" in kwargs:
        add_legend = kwargs["add_legend"]
    elif len(adata.obs[obs].unique()) == 2:
        add_legend = True
    else:
        add_legend = False
    
    if not colors:
        colors = cycle(COLORS)
    
    fig = plt.figure()
    ax = plt.axes(projection = "rectilinear" if n_components == 2 else "3d")
    fig.set_figheight(kwargs["figheight"] if "figheight" in kwargs else 5)
    fig.set_figwidth(kwargs["figwidth"] if "figwidth" in kwargs else 5 if n_components == 2 else 6)
        
    for _cluster, _color in zip(sorted(adata.obs[obs].unique()), colors):
        idx = np.where(adata.obs[obs] == _cluster)[0]
        if n_components==2:
            ax.scatter(
                adata.obsm[obsm][idx,0],
                adata.obsm[obsm][idx,1],
                s=kwargs["s"] if "s" in kwargs else 3,
                facecolors=_color,
                edgecolors="none",
                alpha=1,
                label=_cluster
            )
        elif n_components==3:
            ax.scatter3D(
                adata.obsm[obsm][idx,0],
                adata.obsm[obsm][idx,1],
                adata.obsm[obsm][idx,2],
                s=kwargs["s"] if "s" in kwargs else 3,
                facecolors=_color,
                edgecolors="none",
                alpha=1,
                label=_cluster
            )

    if add_legend:
        fig.set_figwidth(kwargs["figwidth"]*1.25 if "figwidth" in kwargs else 6.25)
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width*0.8, box.height])
        if "legend_params" in kwargs:
            kwargs["lgd_params"] = kwargs["legend_params"]
        if "lgd_params" in kwargs:
            if "loc" not in kwargs["lgd_params"] and "bbox_to_anchor" not in kwargs["lgd_params"]:
                if n_components == 3:
                    fig.tight_layout()
                    fig.subplots_adjust(right=0.8)
                ax.legend(
                    loc="center left",
                    bbox_to_anchor=(1.04, 0.5) if n_components == 2 else (1.09, 0.5),
                    **kwargs["lgd_params"]
                )
            else:
                ax.legend(**kwargs["lgd_params"])
        else:
            ax.legend(
                loc="center left",
                bbox_to_anchor=(1.04, 0.5),
            )
    
    return fig, ax

@__default_plot
def __scatterplot_continuous(
    adata: ad.AnnData,
    obs: str,
    obsm: str,
    colors: Optional[Colormap] = None,
    n_components: Optional[int] = 2,
    **kwargs
):

    if colors:
        _cmap = colors.name
    else:
        _cmap="autumn"

    fig = plt.figure()
    ax = plt.axes(projection = "rectilinear" if n_components == 2 else "3d")
    fig.set_figheight(kwargs["figheight"] if "figheight" in kwargs else 5)
    fig.set_figwidth(kwargs["figwidth"] if "figwidth" in kwargs else 5 if n_components == 2 else 6)
    
    if n_components == 2:
        sc = ax.scatter(
            adata.obsm[obsm][:,0],
            adata.obsm[obsm][:,1],
            s=kwargs["s"] if "s" in kwargs else 3,
            c=adata.obs[obs],
            cmap=_cmap,
            edgecolors="none",
            alpha=1
        )
        fig.colorbar(sc)
    elif n_components==3:
        ax.scatter3D(
            adata.obsm[obsm][:,0],
            adata.obsm[obsm][:,1],
            adata.obsm[obsm][:,2],
            s=kwargs["s"] if "s" in kwargs else 3,
            c=adata.obs[obs],
            cmap=_cmap,
            edgecolors="none",
            alpha=1,
        )

    return fig, ax

@adata_arg_checking
def __graph_to_plot(
    adata: ad.AnnData,
    ax: Optional[Axes] = None,
    dim: Optional[int] = 2,
    **kwargs
    ):

    if ax is None:
        ax = plt.gca()

    epg = adata.uns["epg"]
    flat_tree = adata.uns["flat_tree"]
    epg_node_pos = nx.get_node_attributes(epg,"pos")

    traces = set()
    for node in flat_tree:
        for trace in flat_tree.adj[node].values():
            traces.add(tuple(trace["nodes"]))

    edge_curves = list()
    for trace in traces:
        _edge_curve = list()
        for node in trace:
            _edge_curve.append(np.array([epg_node_pos[node]]))
        edge_curves.append(np.concatenate(_edge_curve))

    for edge_curve in edge_curves:
        if dim == 2:
            x, y = edge_curve[:,0], edge_curve[:, 1]
            line = plt.Line2D(xdata=x, ydata=y, color=colour.black, **kwargs)
        elif dim == 3:
            x, y, z = edge_curve[:,0], edge_curve[:, 1], edge_curve[:, 2]
            line = mplot3d.art3d.Line3D(xs=x, ys=y, zs=z, color=colour.black, **kwargs)
        ax.add_line(line)

@adata_arg_checking
def __text_to_plot(
    adata: ad.AnnData,
    ax: Optional[Axes] = None,
    dim: Optional[int] = 2,
    **kwargs
    ):

    if ax is None:
        ax = plt.gca()

    flat_tree = adata.uns["flat_tree"]
    flat_tree_node_label = nx.get_node_attributes(flat_tree, "label")
    flat_tree_node_pos = nx.get_node_attributes(flat_tree, "pos")

    if dim == 2:
        for node in flat_tree.nodes:
            plt.text(
                x=flat_tree_node_pos[node][0],
                y=flat_tree_node_pos[node][1],
                s=flat_tree_node_label[node],
                **kwargs
            )
    elif dim == 3:
        for node in flat_tree.nodes:
            ax.text(
                x=flat_tree_node_pos[node][0],
                y=flat_tree_node_pos[node][1],
                z=flat_tree_node_pos[node][2],
                s=flat_tree_node_label[node],
                **kwargs
            )

@adata_arg_checking
def scatterplot(
    adata: ad.AnnData,
    obs: str,
    obsm: str,
    colors: Optional[Colormap] = None,
    n_components: Optional[int] = 2,
    outfile: Optional[Path] = None,
    add_graph: Optional[bool] = None,
    add_text: Optional[bool] = None,
    default_parameters: Optional[types.FunctionType] = None,
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
        The data points are retrieved by the first columns in .obsm[`obsm`].
    colors
        Visualization of the mapping from a list of color values.
    n_components
        Number of plotted dimensions (default: 2)
    outfile
        If specified, save the figure.
    add_graph
        plot elastic principal graph.
    add_text
        add node labels of elastic principal graph.
    default_parameters
        function specifying default figure parameters.
    **kwargs
        Supplemental features for figure plotting:
        - figheight[float]: specify the figure height.
        - figwidth[float]: specify the figure width.
        - xlabel[str]: set the label for the x-axis.
        - ylabel[str]: set the label for the y-axis.
        - zlabel[str]: set the label for the z-axis.
        - formatter[matplotlib.ticker.FormatStrFormatter]: specify the major formatter on x-, y- and z-axis.
        - add_legend[bool]: when .obs[`obs`] are discrete values, specify whether to draw legend.
        - lgd_params[dict]: when add_legend is True, modify legend following the syntax of matplotlib.pyplot.legend.
        - tick_params[dict]: change the appearance of ticks, tick labels, and gridlines following the syntax of matplotlib.axes.Axes.tick_params.
        - xtick_params[dict]: change the appearance of ticks, tick labels, and gridlines on x-axis following the syntax of matplotlib.axes.Axes.tick_params.
        - ytick_params[dict]: change the appearance of ticks, tick labels, and gridlines on y-axis following the syntax of matplotlib.axes.Axes.tick_params.
        - ztick_params[dict]: change the appearance of ticks, tick labels, and gridlines on z-axis following the syntax of matplotlib.axes.Axes.tick_params.
        - text[dict]: change the appearance of text in figure following the syntax of matplotlib.text.
        - background_visible[bool]: specify if background color is visible or not in case of 3D plotting.

    Returns
    -------
    Depending on `outfile`, save figure or create a current figure.
    """

    if n_components not in [2,3]:
        raise ValueError(f"`n_components` parameter value is {n_components}, please set it to 2 or 3, aborting.")
    elif n_components == 3 and adata.obsm[obsm].shape[1] < 3:
        raise ValueError(f"incoherence value: `n_components` parameter value is {n_components} while number of dimension in .obsm[{obsm}] is {adata.obsm[obsm].shape[1]}, aborting.")

    if pd.api.types.is_float_dtype(adata.obs[obs]):
        fig, ax = __scatterplot_continuous(
            adata,
            obs,
            obsm,
            colors,
            n_components,
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
            colors,
            n_components,
            **kwargs
        )
    
    if add_graph:
        ax = plt.gca()
        __graph_to_plot(adata, ax=ax, dim=n_components)
    
    if add_text:
        ax = plt.gca()
        if "text" not in kwargs:
            kwargs["text"] = dict()
            kwargs["text"]["verticalalignment"] = "bottom" if add_graph else "center"
        elif "verticalalignment" not in kwargs["text"]:
            kwargs["text"]["verticalalignment"] = "bottom" if add_graph else "center"
        else:
            pass
        __text_to_plot(
            adata,
            ax,
            dim=n_components,
            **kwargs["text"]
        )
    
    if default_parameters:
        default_parameters()
    
    if outfile:
        plt.savefig(outfile, bbox_inches="tight")
        plt.close()
        return None
    else:
        return fig, ax

if __name__ == "__main__":
    sys.exit()