#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

import subprocess
import os, std
from pathlib import Path

import numpy as np

import pandas as pd
import anndata as ad
import bonesistools as bt
import stream as st

from networkx.classes.graph import Graph
from rpy2.rinterface import ListSexpVector
from scipy.sparse import csr_matrix

import matplotlib.pyplot as plt

class Options:
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            self.__dict__[k] = v

opt = Options(
    path=Path("nestorowa/unique/clust"),
    loess_frac=0.01,
    hvg=2000,
    pca_dimension=40
)

if not opt.path.exists():
    os.makedirs(opt.path)

std.print_task(f"downloading nestorowa data")

tmpdir = subprocess.check_output("mktemp -d -t nestorowa-XXXXXXXXXX", shell=True, text=True).replace("\n", "")

subprocess.call(["wget", "--quiet", "--show-progress", f"--directory-prefix={tmpdir}", "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE81nnn/GSE81682/suppl/GSE81682_HTSeq_counts.txt.gz"])
subprocess.call(["wget", "--quiet", "--show-progress", f"--directory-prefix={tmpdir}", "http://blood.stemcells.cam.ac.uk/data/normalisedCounts.txt.gz"])
subprocess.call(["wget", "--quiet", "--show-progress", f"--directory-prefix={tmpdir}", "http://blood.stemcells.cam.ac.uk/data/all_cell_types.txt"])
subprocess.call(["wget", "--quiet", "--show-progress", f"--directory-prefix={tmpdir}", "http://blood.stemcells.cam.ac.uk/data/cluster_ids.txt"])

read_counts = pd.read_csv(f"{tmpdir}/GSE81682_HTSeq_counts.txt.gz", index_col=0, sep="\t").transpose()
norm_counts = pd.read_csv(f"{tmpdir}/normalisedCounts.txt.gz", index_col=0, sep=" ").transpose()
cell_types = pd.read_csv(f"{tmpdir}/all_cell_types.txt", index_col=0, sep="\t")
cluster_ids = pd.read_csv(f"{tmpdir}/cluster_ids.txt", header=None, index_col=0, names=["cluster"], sep=" ", dtype="category")["cluster"]

norm_counts = norm_counts.loc[:, norm_counts.columns.str.startswith("ENS")]
read_counts = read_counts.loc[norm_counts.index, norm_counts.columns]
cell_types = cell_types.loc[cluster_ids.index, ]

std.print_task(f"labeling cells")

groups = {
    "HSC":  ["LTHSC_broad", "STHSC_broad", "LTHSC", "STHSC", "ESLAM", "HSC1"],
    "LMPP": ["LMPP_broad", "LMPP"],
    "MPP":  ["MPP_broad", "MPP1_broad", "MPP2_broad", "MPP3_broad", "MPP", "MPP1", "MPP2", "MPP3"],
    "CMP":  ["CMP_broad", "CMP"],
    "MEP":  ["MEP_broad", "MEP"],
    "GMP":  ["GMP_broad", "GMP"]
}

cell_labels = pd.DataFrame(index=cell_types.index)
for k, v in groups.items():
    cell_labels[k] = cell_types[v].sum(axis=1)
cell_labels = cell_labels.applymap(lambda x: 1 if x != 0 else 0)

mapping = {
    "purple": ["HSC"],
    "deeppink": ["MEP"],
    "gold": ['CMP','GMP'],
    "darkturquoise": ["CMP", "MPP", "LMPP"]
}

metadata = pd.DataFrame(columns=["label", "cluster"], index=cell_labels.index)

label_unique, label_multi, label_missing = [[], [], []]
for x in cell_labels.index:
    x_labels = cell_labels.loc[x,] > 0
    n_labels = sum(x_labels)
    if n_labels == 1:
        x_label = cell_labels.columns[x_labels][0]
        metadata.loc[x] = [x_label, cluster_ids[x]]
        label_unique.append(x)
    elif n_labels > 1:
        np.random.seed(2020)
        x_label = np.random.choice(cell_labels.columns[x_labels], 1)[0]
        metadata.loc[x] = [x_label, cluster_ids[x]]
        label_multi.append(x)
    else:
        np.random.seed(2020)
        x_label = np.random.choice(mapping[cluster_ids[x]], 1)[0]
        metadata.loc[x] = [x_label, cluster_ids[x]]
        label_missing.append(x)

std.print_info(f"labels: #unique: {len(label_unique)}; #multiple: {len(label_multi)}; #missing: {len(label_missing)}")

std.print_task("converting read counts into AnnData object")

adata = ad.AnnData(X=norm_counts.to_numpy(), dtype=np.float32)
adata.obs_names = read_counts.index
adata.var_names = read_counts.columns

adata.layers["counts"] = csr_matrix(read_counts)

adata.obs["label"] = metadata["label"]
adata.obs["clusters"] = cluster_ids.cat.rename_categories({k: i for i, k in enumerate(cluster_ids.cat.categories)})

adata.uns["workdir"] = str(opt.path)

std.print_task("mapping gene Ensembl ids with their official names")

from pybiomart import Server

server = Server(
    host="www.ensembl.org",
    path="/biomart/martservice",
    port=80,
    use_cache=False
)

mart = server["ENSEMBL_MART_ENSEMBL"]
mouse_dataset = mart["mmusculus_gene_ensembl"]
mouse_attributes = ["ensembl_gene_id", "mgi_symbol", "external_gene_name"]

ensembl_df = mouse_dataset.query(attributes=mouse_attributes)
ensembl_df.columns = mouse_attributes
ensembl_df.index = ensembl_df["ensembl_gene_id"]
ensembl_df.index.name = None
ensembl_df.drop_duplicates(["mgi_symbol"], keep="first", inplace=True)
ensembl_df.drop_duplicates(["ensembl_gene_id"], keep="first", inplace=True)
ensembl_df = ensembl_df[ensembl_df["mgi_symbol"] != ""]

adata.var["ensembl"] = adata.var.index.copy()
adata.var["symbol"] = ensembl_df["mgi_symbol"]

adata.var.index = [ensembl_df.loc[x, "external_gene_name"] if (x in ensembl_df.index) else x for x in adata.var_names]

bt.sct.pp.convert_gene_identifiers(
    adata,
    axis=1,
    input_identifier_type="ensembl_id",
    output_identifier_type="official_name",
    copy=False
)

bt.sct.pp.standardize_gene_identifiers(
    adata,
    axis=1,
    copy=False
)

adata.var_names_make_unique()

std.print_task("filtering cells and features")

st.cal_qc(
    adata,
    assay="rna"
)

with std.disable_print():
    st.filter_cells(adata,min_n_features= 100)
    st.filter_features(adata,min_n_cells = 5)

std.print_task(f"normalizing read counts")

std.print_info(f"transforming counts as stream framework (layer: stream)")
st.normalize(adata, method='lib_size')
st.log_transform(adata)

adata.layers["stream"] = adata.X.copy()

import scanpy as sc

std.print_info("standardizing counts (reference=library size, layer=norm)")
adata.layers["norm"] = adata.layers["counts"].copy()
sc.pp.normalize_total(
    adata,
    target_sum=1e4,
    layer="norm",
    copy=False
)

std.print_info(f"performing log-transformation (layer: log-norm)")
adata.layers["log-norm"] = adata.layers["norm"].copy()
sc.pp.log1p(
    adata,
    base=np.exp(1),
    layer="log-norm",
    copy=False
)

std.print_info(f"scaling to unit variance and zero mean (layer: scale)")
adata.layers["scale"] = adata.layers["log-norm"].copy()
sc.pp.scale(
    adata,
    layer="scale",
    copy=False
)

std.print_task(f"computing highly variable genes (top={opt.hvg}, loess_frac={opt.loess_frac})")
adata.X = adata.layers["stream"].copy()
with std.disable_print():
    st.select_variable_genes(
        adata,
        loess_frac=opt.loess_frac,
        n_genes=opt.hvg
    )
    plt.savefig(f"{opt.path}/hvg.pdf", bbox_inches="tight")
    plt.close()

std.print_task(f"computing principal components (dimensions={opt.pca_dimension})")
with std.disable_print():
    st.select_top_principal_components(
        adata,
        feature="var_genes",
        first_pc=True,
        n_pc=opt.pca_dimension
    )
    plt.close()

std.print_task("computing embedding space (method=spectral embedding)")
with std.disable_print():
    st.dimension_reduction(
        adata,
        method="se",
        feature="top_pcs",
        n_components=4,
        n_neighbors=15,
        n_jobs=4
    )

std.print_task("computing embedding space (method=UMAP)")
with std.disable_print():
    st.plot_visualization_2D(
        adata,
        method="umap",
        n_neighbors=50,
        color=["label"],
        use_precomputed=False
    )
    plt.savefig(f"{opt.path}/umap_label.pdf")

std.print_task(f"saving AnnData (file={std.format_path(f'{opt.path}/annot.h5ad')})")
del adata.uns["workdir"]
for key in list(adata.obs.keys()):
    if isinstance (adata.obs[key][0], tuple):
        del adata.obs[key]
for key in list(adata.uns.keys()):
    if isinstance(adata.uns[key], (tuple, Path, Graph, ListSexpVector, pd.Index)):
        del adata.uns[key]
    if key.startswith("stream_S"):
        del adata.uns[key]
for k in ["top_pcs", "trans_se", "vis_trans_umap", "label_color"]:
    del adata.uns[k]
adata.write_h5ad(
    filename=Path(f"{opt.path}/annot.h5ad"),
    compression="gzip"
)
