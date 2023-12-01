import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import os
import math
import stream as st
import pandas as pd
import matplotlib.pyplot as plt

args = {
    "inpath":Path(f"../../data/scRNA/preprocess/results"),
    "uns":True,
    "outpath":Path(f"../../data/scRNA/cluster/stream"),
    "non_expressed_genes_removed":False,
    "min_proportion_cell_expressed":0.01,
    "n_dimensions":15,
    "first_pc":False
}

def csv_to_anndata(inpath, file_count, file_barcode=None, file_gene=None, uns=False):
    adata = st.read(file_name=Path(f"{inpath}/{file_count}")).transpose()
    if file_barcode:
        adata.obs = pd.read_csv(Path(f"{inpath}/{file_barcode}"), delimiter="\t").set_index("barcode")
    if file_gene:
        adata.var = pd.read_csv(Path(f"{inpath}/{file_gene}"), delimiter="\t").set_index("gene_name")
    if uns:
        for file in os.listdir(Path(f"{args['inpath']}/uns")):
            adata.uns[file] = pd.read_csv(Path(f"{args['inpath']}/uns/{file}"), delimiter="\t")
    return adata

st.set_figure_params(
    dpi=80,
    style='white',
    figsize=(3,3),
    rc={'image.cmap': 'viridis'}
)

adata = csv_to_anndata(args["inpath"].resolve(), "X.csv", file_barcode="obs.csv", file_gene="var.csv", uns=args["uns"])
st.cal_qc(adata,assay='rna')

outpath = args["outpath"].resolve()
_fig_outpath = Path(f"{outpath}/figures").resolve()

if not outpath.exists():
    os.makedirs(outpath)
if not _fig_outpath.exists():
    _fig_outpath.mkdir()

if not args["non_expressed_genes_removed"]:
    threshold = math.floor(args["min_proportion_cell_expressed"] * adata.n_vars)
    st.filter_cells(adata, min_n_counts=threshold)

##### Filtering and scaling #####

print(f"\nFiltering and scaling data...\n")

st.select_variable_genes(adata,loess_frac=0.02)

#### PCA ####

print(f"Computing Principal Component Analysis (PCA)...\n")

st.select_top_principal_components(adata, first_pc=args["first_pc"], n_pc=args["n_dimensions"], feature='var_genes', save_fig=True, fig_path=_fig_outpath)

##### UMAP #####

print(f"Computing Uniform Manifold Approximation and Projection (UMAP)...\n")

st.dimension_reduction(
    adata, method='umap',
    feature='top_pcs',
    n_components=3,
    n_neighbors=20,
    n_jobs=5
)
st.plot_dimension_reduction(
    adata,
    color=["label"],
    n_components=2,
    show_graph=False,
    show_text=False
)
plt.savefig(f"{_fig_outpath}/umap.png")
