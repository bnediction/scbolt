
from pathlib import Path

import bonesistools as bt

quickstart_dir = Path(__file__).resolve().parent
annotation_dir = quickstart_dir / "project" / "omics" / "annot"
annotation_file = annotation_dir / "annot.h5ad"

annotation_dir.mkdir(parents=True, exist_ok=True)

adata = bt.omics.io.load("nestorowa")

bt.omics.pp.log1p(
    adata,
    expression="norm",
    key_added="log-norm",
    copy=False,
)

bt.omics.pp.scale(
    adata,
    expression="log-norm",
    key_added="scale",
    copy=False,
)

adata.layers["correct"] = adata.layers["scale"].copy()

bt.omics.pp.hvg(adata, expression="counts", n_features=2000)

bt.omics.tl.pca(
    adata,
    n_components=30,
    layer="scale",
    var_subset="highly_variable",
    svd_solver="arpack",
    seed=10,
    copy=False,
)

bt.omics.tl.neighbors(
    adata,
    representation="X_pca",
    n_neighbors=15,
    connectivity_method="binary",
    key_added="se_neighbors",
    seed=0,
    n_jobs=4,
    copy=False,
)

bt.omics.tl.spectral(
    adata,
    n_components=4,
    neighbors_key="se_neighbors",
    key_added="X_se",
    seed=10,
    n_jobs=4,
    copy=False,
)

bt.omics.pl.embedding(
    adata,
    obs="label",
    representation="X_se",
    n_components=3,
    s=5,
    legend={
        "markerscale": 5,
    },
    outfile=annotation_dir / "se.pdf",
)

adata.uns["scbolt"] = {
    "input_source": 'bonesistools.datasets.load("nestorowa")',
    "matrix_type": "quickstart_count_matrix",
}

adata.write_h5ad(annotation_file, compression="gzip")

print(f"wrote {annotation_file}")
