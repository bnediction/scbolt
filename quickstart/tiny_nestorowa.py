#!/usr/bin/env python

from pathlib import Path

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

bt.sct.pp.normalize(
    adata,
    target_sum=1e4,
    key_added="norm",
    copy=False,
)
bt.sct.pp.log1p(
    adata,
    expression="norm",
    key_added="log-norm",
    copy=False,
)
bt.sct.pp.scale(
    adata,
    expression="log-norm",
    key_added="scale",
    copy=False,
)
adata.layers["correct"] = adata.layers["scale"].copy()

adata.var["highly_variable"] = True

bt.sct.tl.pca(
    adata,
    n_components=30,
    layer="scale",
    var_subset="highly_variable",
    svd_solver="arpack",
    seed=10,
    copy=False,
)

bt.sct.tl.neighbors(
    adata,
    representation="X_pca",
    n_neighbors=15,
    seed=10,
)
bt.sct.tl.spectral(
    adata,
    n_components=4,
    key_added="X_se",
    seed=10,
)

bt.sct.pl.embedding(
    adata,
    obs="label",
    representation="X_se",
    outfile=data_dir / "se.pdf",
)

adata.uns["scbolt"] = {
    "input_source": "bonesistools.datasets.nestorowa",
    "matrix_type": "quickstart_count_matrix",
    "analysis_hvg": "all_genes",
    "inference_hvg_top": 50,
}

adata.write_h5ad(counts_file, compression="gzip")
adata.write_h5ad(annotation_file, compression="gzip")

print(f"wrote {counts_file}")
print(f"wrote {annotation_file}")
