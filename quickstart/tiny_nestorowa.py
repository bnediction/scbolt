#!/usr/bin/env python

from pathlib import Path

import numpy as np
import scanpy as sc
from sklearn.decomposition import PCA

import bonesistools as bt


quickstart_dir = Path(__file__).resolve().parent
data_dir = quickstart_dir / "data"
annotation_dir = quickstart_dir / "project" / "omics" / "annot"
counts_file = data_dir / "counts.h5ad"
annotation_file = annotation_dir / "annot.h5ad"

data_dir.mkdir(parents=True, exist_ok=True)
annotation_dir.mkdir(parents=True, exist_ok=True)

adata = bt.sct.datasets.nestorowa()
adata.obs["label"] = adata.obs["label"].astype("category")
adata.obs["cluster"] = adata.obs["label"].copy()
adata.layers["counts"] = adata.X.copy()

adata.layers["norm"] = adata.X.copy()
sc.pp.normalize_total(adata, target_sum=1e4, layer="norm", copy=False)

adata.layers["log-norm"] = adata.layers["norm"].copy()
sc.pp.log1p(adata, base=np.exp(1), layer="log-norm", copy=False)

adata.layers["scale"] = adata.layers["log-norm"].copy()
sc.pp.scale(adata, layer="scale", copy=False)
adata.layers["correct"] = adata.layers["scale"].copy()

sc.pp.highly_variable_genes(
    adata,
    layer="counts",
    flavor="seurat_v3",
    n_top_genes=500,
    inplace=True,
)

hvg_mask = np.asarray(adata.var["highly_variable"], dtype=bool)
X = np.asarray(adata.layers["scale"][:, hvg_mask], dtype=float)
adata.obsm["X_pca"] = PCA(
    n_components=30,
    svd_solver="arpack",
    random_state=10,
).fit_transform(X)
adata.obsm["top_pcs"] = adata.obsm["X_pca"].copy()

bt.sct.tl.embedding(
    adata,
    method="spectral",
    use_rep="X_pca",
    n_components=4,
    n_neighbors=15,
    seed=10,
    key_added="X_se",
)

adata.uns["scbolt"] = {
    "input_source": "bonesistools.datasets.nestorowa",
    "matrix_type": "quickstart_count_matrix",
    "analysis_hvg_top": 500,
    "inference_hvg_top": 50,
}

adata.write_h5ad(counts_file, compression="gzip")
adata.write_h5ad(annotation_file, compression="gzip")

print(f"wrote {counts_file}")
print(f"wrote {annotation_file}")
