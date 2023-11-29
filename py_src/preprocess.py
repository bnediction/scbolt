import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import scanpy as sc

path_to_data = Path(f"../data").resolve()
_inpath = Path(f"{path_to_data}/raw/merge").resolve()
_infile = Path(f"{_inpath}/barcode_gene_RNA_PLZF_RARA_RA.h5ad").resolve()
_outpath = Path(f"{path_to_data}/results/preprocess").resolve()
_outfile = Path(f"{_outpath}/barcode_gene_RNA_PLZF_RARA_RA.h5ad")

if not _outpath.exists():
    _outpath.mkdir()

adata = sc.read_h5ad(_infile)
adata.obs_names_make_unique(); adata.var_names_make_unique()

#### Filtering ####

print(f"Filtering genes and cells...\n")

sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True)
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)

#### Normalizing ####

print(f"Normalizing counts and keeping only HVG...\n")

sc.pp.normalize_total(adata, target_sum=1e6)    # Normalize gene expression with respect to library depth
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
adata = adata[:, adata.var.highly_variable]
sc.pp.scale(adata, max_value=10)                # Scale gene values to unit variance

#### Saving ####

print(f"Saving files...\n")

if str(_outfile).split(".")[-1] == "h5ad":
    adata.write_h5ad(filename=_outfile, compression="gzip")
else:
    adata.write_csvs(dirname=_outpath, skip_data=False, sep="\t")
