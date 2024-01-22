#!/usr/bin/python3

import warnings
warnings.filterwarnings("ignore")

import os, sys, contextlib
from pathlib import Path

import anndata as ad, stream as st

@contextlib.contextmanager
def disable_print():
    with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
        yield

class arguments:
    def __init__(
        self,
        infile=Path("data/scRNA/integration/tables/bbknn.h5ad"),
        outpath=Path("data/scRNA/stream"),
        hvg=False,
        epg_alpha=0.01,
        epg_mu=0.05,
        epg_lambda=0.05,
        jobs=6,
        verbose=True
    ):
        self.infile = infile
        self.outpath = outpath
        self.hvg = hvg
        self.epg_alpha = epg_alpha
        self.epg_mu = epg_mu
        self.epg_lambda = epg_lambda
        self.jobs = jobs
        self.verbose = verbose

args = arguments()

data_outpath = Path(f"{args.outpath}/tables")
fig_outpath = Path(f"{args.outpath}/figures")

if not data_outpath.exists():
    os.makedirs(data_outpath)
if not fig_outpath.exists():
    os.makedirs(fig_outpath)

print(f"Loading data...")

adata = ad.read_h5ad(args.infile)
adata.obs_names_make_unique()
adata.uns["workdir"] = args.outpath

layer = "correct"
adata.X = adata.layers[layer]

if args.hvg:
    print("Selecting higly variable genes (HVG)...")
    with disable_print():
        st.select_variable_genes(adata,loess_frac=0.02)

print("Running principal component analysis (PCA)...")
with disable_print():
    if args.hvg:
        st.select_top_principal_components(
            adata,
            first_pc=True,
            n_pc=15,
            feature="var_genes"
        )
    else:
        st.select_top_principal_components(
            adata,
            first_pc=True,
            n_pc=15
        )

print(f"Integration using mlle...")
with disable_print():
    st.dimension_reduction(
        adata,
        method="mlle",
        feature="top_pcs",
        n_components=4,
        n_neighbors=50,
        n_jobs=args.jobs
    )

print("Computing elastic principal graph...")
with disable_print():
    st.seed_elastic_principal_graph(
        adata,
        n_clusters=10
    )
    st.elastic_principal_graph(
        adata,
        epg_alpha=args.epg_alpha,
        epg_mu=args.epg_mu,
        epg_lambda=args.epg_lambda
    )
    st.extend_elastic_principal_graph(
        adata,
        epg_ext_mode='WeigthedCentroid',
        epg_ext_par=0.8
    )

st.plot_stream(
    adata,
    root="S1",
    color=['S1_pseudotime'],
    log_scale=False,
    factor_zoomin=200,
    save_fig=True,
    fig_path=Path(f"{args.outpath}/stream"),
    fig_format="png"
)

#st.add_cell_labels(adata, file_name=conditionCells)
#st.add_cell_colors(adata, file_name=conditionColors)