from pathlib import Path

import scanpy as sc

_inpath = Path("../Data/Results/hdf5").resolve()
_infile = Path(f"{_inpath}/barcode_gene_RNA_PLZF_RARA_RA.h5ad")
_outpath = Path("../Data/Results/Cluster/").resolve()

if not _outpath.exists():
    _outpath.mkdir()

sc.settings.set_figure_params(dpi=80, frameon=False, figsize=(3, 3), facecolor='white')

print(f"Reading data from: {_inpath}/{_infile}")
print(f"Saving processed data to: {_outpath}")

adata = sc.read_h5ad(filename=_infile)

##### Preprocessing #####

sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)
sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True)
sc.pp.normalize_total(adata, target_sum=1e4)    # Normalize gene expression with respect to library size
sc.pp.log1p(adata)                              # Logarithmize gene expression
sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
adata.raw = adata
adata = adata[:, adata.var.highly_variable]
sc.pp.scale(adata, max_value=10)                # Scale gene values to unit variance

#sc.pl.violin(
#    adata,
#    ['n_genes_by_counts', 'total_counts'],
#    jitter=0.4,
#    multi_panel=True
#)
#sc.pl.scatter(adata, x='total_counts', y='n_genes_by_counts')

##### Clustering #####

## Principal component analysis ##

sc.tl.pca(adata, svd_solver='arpack', n_comps=50)
sc.pl.pca(adata, color='label')
#sc.pl.pca_variance_ratio(adata, log=False)

## Neighborhood graph ##

sc.pp.neighbors(adata, n_neighbors=50, n_pcs=15)
sc.tl.umap(adata)
sc.pl.umap(adata, color="label")
