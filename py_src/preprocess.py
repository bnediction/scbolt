import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import scanpy as sc
import numpy as np
import matplotlib.pyplot as plt

args = {
    "hvg":False,
    "scale":False,
    "relative_deviation_from_mad":2,
    "mitochondrial_filter":1,
    "expressed_cells_number_threshold":10,
    "fig_path":Path(f"../data/fig")
}

def median_absolute_deviation(x):
    return np.median(np.absolute(x - np.median(x)))

path_to_data = Path(f"../data").resolve()
_inpath = Path(f"{path_to_data}/raw/merge").resolve()
_infile = Path(f"{_inpath}/barcode_gene_RNA_PLZF_RARA_RA.h5ad").resolve()
_outpath = Path(f"{path_to_data}/results/preprocess").resolve()
_outfile = Path(f"{_outpath}/barcode_gene_RNA_PLZF_RARA_RA.csv")

if not _outpath.exists():
    _outpath.mkdir()

#### Loading ####

adata = sc.read_h5ad(_infile)
adata.obs_names_make_unique(); adata.var_names_make_unique()

print(f"\nCompute violin plot before filtering...\n")

sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True)

sc.pl.violin(
    adata=adata,
    keys=["n_genes_by_counts", "total_counts"],
    groupby="label",
    jitter=0.4,
    multi_panel=True,
    show=False,
    save=False
)
plt.savefig(f"{args['fig_path']}/violin_plot_before_filtering.png")

# Compute mitochondrial and ribosomal proportions before filtering
adata.var["mito"] = adata.var_names.str.startswith("mt-")                   # annotate the group of mitochondrial genes
adata.var["ribo"] = adata.var_names.str.startswith(("Rps","Rpl","Mrp"))     # annotate the group of ribosomal genes
sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True, qc_vars=['mito','ribo'])

#### Filtering ####

print(f"\nFiltering low-quality cells...\n")

threshold_min_counts = np.exp(np.median(np.log(adata.obs.total_counts)) - args["relative_deviation_from_mad"]*median_absolute_deviation(np.log(adata.obs.total_counts)))
threshold_max_counts = np.exp(np.median(np.log(adata.obs.total_counts)) + args["relative_deviation_from_mad"]*median_absolute_deviation(np.log(adata.obs.total_counts)))
sc.pp.filter_cells(adata, min_counts=threshold_min_counts)
sc.pp.filter_cells(adata, max_counts=threshold_max_counts)
adata[adata.obs.pct_counts_mito < args["mitochondrial_filter"], :]

print(f"Filtering low-quality genes...\n")

sc.pp.filter_genes(adata, min_cells=args["expressed_cells_number_threshold"])
adata[:, adata.var.mito == False]
adata.var.drop(["mito"], axis=1, inplace=True)

print(f"Compute violin plot after filtering...\n")

sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True)

sc.pl.violin(
    adata=adata,
    keys=["n_genes_by_counts", "total_counts"],
    groupby="label",
    jitter=0.4,
    multi_panel=True,
    show=False,
    save=False
)
plt.savefig(f"{args['fig_path']}/violin_plot_after_filtering.png")

#### Normalizing ####

print(f"Normalizing counts...\n")

sc.pp.normalize_total(adata, target_sum=1e6)    # Normalize gene expression with respect to library depth
sc.pp.log1p(adata)
if args["hvg"]:
    sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
    adata = adata[:, adata.var.highly_variable]
if args["scale"]:
    sc.pp.scale(adata, max_value=10)            # Scale gene values to unit variance

#### Saving ####

print(f"Saving files...\n")

if str(_outfile).split(".")[-1] == "h5ad":
    adata.write_h5ad(filename=_outfile, compression="gzip")
else:
    adata.write_csvs(dirname=_outpath, skip_data=False, sep="\t")
