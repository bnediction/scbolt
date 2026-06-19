# scBOLT Quickstart

This directory contains a minimal scBOLT example based on the built-in
Nestorowa hematopoiesis dataset distributed with BoNesisTools. It is meant as a
small runnable demonstration of the scBOLT interface, not as a manuscript-scale
case study.

The example starts from local AnnData files generated from:

```python
bt.sct.datasets.nestorowa()
```

No manual data download is required. The preparation script creates a compact
annotation entry point with a spectral embedding (`X_se`) computed in
BoNesisTools, then scBOLT starts from this trusted annotation target.

## Run

From the scBOLT repository root:

```bash
cd quickstart
conda activate scbolt-core
python tiny_nestorowa.py
conda deactivate

scbolt init params.mk
scbolt check bn-submin
scbolt bn-submin
```

The preparation script computes the spectral embedding from the top 500 HVGs
of the built-in dataset. The scBOLT run then restricts Boolean-network
inference to the top 50 HVGs selected with the `seurat_v3` method, so it stays
small enough for a quick run. It uses a compact STREAM macrostate abstraction
inspired by the hematopoiesis case study.

Full manuscript reproductions and larger biological analyses are provided
separately in the scBOLT case-study repository.
