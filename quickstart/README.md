# scBOLT Quickstart

This directory contains a minimal scBOLT example based on the built-in
Nestorowa hematopoiesis dataset distributed with BoNesisTools. It is meant as a
small runnable demonstration of the scBOLT interface, not as a manuscript-scale
case study.

The example starts from local AnnData files generated from:

```python
bt.omics.io.load("nestorowa")
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

scbolt init scbolt.yml
scbolt check bn-submin
scbolt bn-submin
```

The preparation script computes a spectral embedding for the built-in dataset.
The scBOLT run follows the hematopoiesis case-study configuration, except that
Boolean-network inference is restricted to the top 40 HVGs to keep the example
small enough for a quick run.

Full manuscript reproductions and larger biological analyses are provided
separately in the scBOLT case-study repository.
