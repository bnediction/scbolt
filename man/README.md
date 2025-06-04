# Documentation

## Introduction ##

The semi-automatic workflow sc-bridge (pipeline for Boolean network Reconstruction and Inference
from multiple experimental Data in Gene Expression) proposes a general methodology for inferring executable models reproducing the
observed cellular dynamics from multiple biological experiments, using scRNA-seq data.
Its implementation in `make`, in addition to make its use easy and intuitive,
offers a wide range of advanced features for guiding and helping users in
modelling the desired biological processes.
Here we propose an advanced documentation for a proper use of the pipeline,
but user can find a summary documentation using `make help`.

Reconstructing *in-silico* BNs requires many computational steps (see figure below).
To summary the pipeline's tasks, UMI counts are computed from sequencing data,
by distinguishing spliced and unspliced mRNAs. Then data preprocessing is performed,
by filtering out low quality data and regressing-out cell cycle phases.
Once this step finished, condition-related data are integrated by removing batch effects,
and cell profiles are annotated by clustering and analysing cell populations.
Annotations are sometimes not sufficient to deduce transcriptional dynamics,
thus state-change trajectories are inferred. Then binarized meta-states are retrieved,
which combined to dynamic Boolean properties, allows to infer BNs.

<p align="center">
<img src="scbridge-workflow.png" alt="sc-bridge workflow" width="700"/>
<p>