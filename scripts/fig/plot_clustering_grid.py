#!/usr/bin/python3

from __future__ import annotations

import argparse
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Optional, Sequence
import warnings

import anndata as ad
import bonesistools as bt
import matplotlib.pyplot as plt
import numpy as np
import scanpy as sc
from anndata import AnnData


@contextmanager
def filter_scanpy_hvg_warnings():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"The default of observed=False is deprecated.*",
            category=FutureWarning,
            module=r"scanpy\.preprocessing\._highly_variable_genes",
        )
        warnings.filterwarnings(
            "ignore",
            message=(
                r"The behavior of DataFrame concatenation with empty or all-NA "
                r"entries is deprecated.*"
            ),
            category=FutureWarning,
            module=r"scanpy\.preprocessing\._highly_variable_genes",
        )
        warnings.filterwarnings(
            "ignore",
            message=(
                r"The provided callable .* is currently using "
                r"SeriesGroupBy\.(mean|sum).*"
            ),
            category=FutureWarning,
            module=r"scanpy\.preprocessing\._highly_variable_genes",
        )
        yield


def decimal_range(spec: str) -> list[Decimal]:
    fields = spec.split(":")
    if len(fields) != 3:
        return [Decimal(value) for value in spec.split(",") if value]

    start, stop, step = (Decimal(value) for value in fields)
    values = []
    value = start
    while value <= stop:
        values.append(value)
        value += step
    return values


def integer_range(spec: str) -> list[int]:
    fields = spec.split(":")
    if len(fields) != 3:
        return [int(value) for value in spec.split(",") if value]

    start, stop, step = (int(value) for value in fields)
    return list(range(start, stop + 1, step))


def clean_adata(
    adata: AnnData,
    obs: Optional[Sequence[str]] = None,
    var: Optional[Sequence[str]] = None,
    copy: bool = False,
) -> Optional[AnnData]:
    adata = adata.copy() if copy else adata

    if obs:
        for key in obs:
            if key in adata.obs.columns:
                del adata.obs[key]
    if var:
        for key in var:
            if key in adata.var.columns:
                del adata.var[key]
    for key in ("pca", "neighbors", "shared_neighbors", "cluster", "tsne", "umap"):
        if key in adata.uns:
            del adata.uns[key]
    del adata.obsm, adata.obsp, adata.varm, adata.varp

    return adata if copy else None


def namespace_obs_names(adata: AnnData, condition: str, sep: str = ":") -> None:
    barcodes = adata.obs_names.astype(str)
    adata.obs["barcode"] = barcodes
    adata.obs["condition"] = condition
    adata.obs_names = [f"{condition}{sep}{barcode}" for barcode in barcodes]


def load_integrated_base(args: argparse.Namespace) -> AnnData:
    adatas = []
    for condition in args.conditions:
        infile = args.project_dir / condition / "prep" / "norm" / "counts.h5ad"
        print(f"loading {condition}: {infile}", flush=True)
        adata = ad.read_h5ad(infile)
        namespace_obs_names(adata, condition)
        adata.X = adata.layers[args.layer].copy()
        clean_adata(adata)
        adatas.append(adata)

    print("concatenating datasets", flush=True)
    merged = ad.concat(
        adatas=adatas,
        join="inner",
        label="condition",
        keys=args.conditions,
        merge="same",
        uns_merge="same",
    )

    print("estimating HVGs", flush=True)
    with filter_scanpy_hvg_warnings():
        sc.pp.highly_variable_genes(
            merged,
            layer="counts" if args.hvg_flavor == "seurat_v3" else "log-norm",
            flavor=args.hvg_flavor,
            span=args.hvg_span,
            n_bins=args.hvg_bins,
            n_top_genes=args.top_hvg,
            batch_key="condition",
            inplace=True,
        )

    print("computing PCA", flush=True)
    sc.tl.pca(
        merged,
        n_comps=args.pca_dimension,
        zero_center=True,
        use_highly_variable=True,
        random_state=np.random.RandomState(args.seed),
        copy=False,
    )

    return merged


def cluster_colors(labels_by_resolution: dict[str, np.ndarray]) -> dict[str, object]:
    labels = sorted(
        {label for labels in labels_by_resolution.values() for label in labels},
        key=lambda value: int(value) if str(value).isdigit() else str(value),
    )
    if len(labels) <= 20:
        colormap = plt.get_cmap("tab20")
        values = [colormap(i) for i in range(len(labels))]
    else:
        colormap = plt.get_cmap("turbo")
        values = [colormap(i / max(len(labels) - 1, 1)) for i in range(len(labels))]
    return dict(zip(labels, values))


def plot_grid(
    outfile: Path,
    embeddings_by_min_dist: dict[str, np.ndarray],
    labels_by_resolution: dict[str, np.ndarray],
    min_dist_values: Sequence[Decimal],
    resolution_values: Sequence[Decimal],
    title: str,
) -> None:
    colors = cluster_colors(labels_by_resolution)
    fig, axes = plt.subplots(
        len(resolution_values),
        len(min_dist_values),
        figsize=(2.0 * len(min_dist_values), 1.8 * len(resolution_values)),
        squeeze=False,
    )

    for row, resolution in enumerate(resolution_values):
        resolution_key = str(resolution)
        labels = labels_by_resolution[resolution_key]
        for col, min_dist in enumerate(min_dist_values):
            min_dist_key = str(min_dist)
            ax = axes[row, col]
            coords = embeddings_by_min_dist[min_dist_key]
            for label in sorted(colors):
                mask = labels == label
                if np.any(mask):
                    ax.scatter(
                        coords[mask, 0],
                        coords[mask, 1],
                        s=1.0,
                        color=colors[label],
                        linewidths=0,
                        rasterized=True,
                    )
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_frame_on(False)
            if row == 0:
                ax.set_title(f"min={min_dist_key}", fontsize=7)
            if col == 0:
                ax.set_ylabel(
                    f"res={resolution_key}",
                    fontsize=7,
                    rotation=0,
                    labelpad=24,
                )

    fig.suptitle(title, fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.995), w_pad=0.05, h_pad=0.05)
    fig.savefig(outfile, bbox_inches="tight", dpi=300)
    plt.close(fig)


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plot_clustering_grid",
        description="Plot integrated clustering grids across neighbors, min_dist, and resolution values.",
    )
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, default=None)
    parser.add_argument("--conditions", nargs="+", default=["ctrl", "treated"])
    parser.add_argument("--layer", default="correct")
    parser.add_argument("--neighbors", default="8:12:1")
    parser.add_argument("--min-dist", default="0.3:1.0:0.1")
    parser.add_argument("--resolution", default="0.40:0.55:0.01")
    parser.add_argument("--spread", type=float, default=1.5)
    parser.add_argument("--seed", type=int, default=10)
    parser.add_argument("--pca-dimension", type=int, default=25)
    parser.add_argument("--clustering-dimension", type=int, default=25)
    parser.add_argument("--embedding-dimension", type=int, default=2)
    parser.add_argument("--hvg-flavor", default="seurat_v3")
    parser.add_argument("--top-hvg", type=int, default=2000)
    parser.add_argument("--hvg-span", type=float, default=0.3)
    parser.add_argument("--hvg-bins", type=int, default=20)
    parser.add_argument("--metric", default="euclidean")
    parser.add_argument("--skip-existing", action="store_true")
    return parser


def main() -> None:
    args = parser().parse_args()
    args.project_dir = args.project_dir.resolve()
    args.outdir = (
        args.project_dir / "integrated" / "clust" / "parameter-grid"
        if args.outdir is None
        else args.outdir.resolve()
    )
    neighbors_values = integer_range(args.neighbors)
    min_dist_values = decimal_range(args.min_dist)
    resolution_values = decimal_range(args.resolution)

    bt.sct.pl.set_default_params(tex=False)
    args.outdir.mkdir(parents=True, exist_ok=True)
    base = load_integrated_base(args)

    for neighbors in neighbors_values:
        outfile = args.outdir / f"neighbors_{neighbors}.pdf"
        if args.skip_existing and outfile.exists():
            print(f"neighbors={neighbors}: skipping existing {outfile}", flush=True)
            continue

        print(f"neighbors={neighbors}: building BBKNN graph", flush=True)
        adata = base.copy()
        sc.external.pp.bbknn(
            adata,
            batch_key="condition",
            neighbors_within_batch=neighbors,
            use_rep="X_pca",
            n_pcs=args.clustering_dimension,
            metric=args.metric,
            approx=None,
            use_annoy=None,
            use_faiss=None,
            computation="cKDTree",
            pynndescent_random_state=args.seed,
            copy=False,
        )

        labels_by_resolution = {}
        for resolution in resolution_values:
            key = str(resolution)
            print(f"neighbors={neighbors}: leiden resolution={key}", flush=True)
            sc.tl.leiden(
                adata,
                neighbors_key="neighbors",
                resolution=float(resolution),
                key_added="cluster",
                random_state=args.seed,
                copy=False,
            )
            labels_by_resolution[key] = adata.obs["cluster"].astype(str).to_numpy()

        embeddings_by_min_dist = {}
        for min_dist in min_dist_values:
            key = str(min_dist)
            print(f"neighbors={neighbors}: UMAP min_dist={key}", flush=True)
            sc.tl.umap(
                adata,
                neighbors_key="neighbors",
                n_components=args.embedding_dimension,
                min_dist=float(min_dist),
                spread=args.spread,
                random_state=np.random.RandomState(args.seed),
                copy=False,
            )
            embeddings_by_min_dist[key] = np.asarray(adata.obsm["X_umap"]).copy()

        print(f"neighbors={neighbors}: writing {outfile}", flush=True)
        plot_grid(
            outfile,
            embeddings_by_min_dist=embeddings_by_min_dist,
            labels_by_resolution=labels_by_resolution,
            min_dist_values=min_dist_values,
            resolution_values=resolution_values,
            title=f"Integrated clustering grid (neighbors={neighbors})",
        )

    print(f"done: {args.outdir}", flush=True)


if __name__ == "__main__":
    main()
