from pathlib import Path

import os
import scanpy as sc
import pandas as pd
import matplotlib.pyplot as plt

args = {
    "inpath":Path(f"../data/preprocess/results"),
    "uns":True,
    "outpath":Path(f"../data/cluster/scanpy")
}

def csv_to_anndata(inpath, file_count, file_barcode=None, file_gene=None, uns=False):
    adata = sc.read_csv(filename=Path(f"{inpath}/{file_count}"), delimiter="\t")
    if file_barcode:
        adata.obs = pd.read_csv(Path(f"{inpath}/{file_barcode}"), delimiter="\t").set_index("barcode")
    if file_gene:
        adata.var = pd.read_csv(Path(f"{inpath}/{file_gene}"), delimiter="\t").set_index("gene_name")
    if uns:
        for file in os.listdir(Path(f"{args['inpath']}/uns")):
            adata.uns[file] = pd.read_csv(Path(f"{args['inpath']}/uns/{file}"), delimiter="\t")
    return adata

sc.settings.set_figure_params(dpi=80, frameon=False, figsize=(3, 3), facecolor='white')

adata = csv_to_anndata(args["inpath"].resolve(), "X.csv", file_barcode="obs.csv", file_gene="var.csv", uns=args["uns"])

outpath = args["outpath"].resolve()
_fig_outpath = Path(f"{outpath}/figures").resolve()

if not outpath.exists():
    os.makedirs(outpath)
if not _fig_outpath.exists():
    _fig_outpath.mkdir()

##### High variables genes #####

print(f"\nSelecting hvg...\n")

sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
adata.raw = adata
adata = adata[:, adata.var.highly_variable]
sc.pp.scale(adata, max_value=10)                # Scale gene values to unit variance

##### Clustering #####

## Principal component analysis ##

print(f"Computing Principal Component Analysis (PCA)...\n")

sc.tl.pca(adata, svd_solver='arpack', n_comps=15)
sc.pl.pca(adata, color='label', show=False, save=False)
plt.savefig(f"{_fig_outpath}/pca.png")
#sc.pl.pca_variance_ratio(adata, log=False)

## Neighborhood graph ##

print(f"Computing Uniform Manifold Approximation and Projection (UMAP)...\n")

sc.pp.neighbors(adata, n_neighbors=50, n_pcs=15)
sc.tl.umap(adata)
sc.pl.umap(adata, color="label", show=False, save=False)
plt.savefig(f"{_fig_outpath}/umap.png")