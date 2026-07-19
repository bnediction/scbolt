"""AnnData, composition, and plotting helpers for scBOLT omics scripts."""

from ._anndata import drop_expression_matrices, write_h5ad
from ._composition import (
    check_exported_composition,
    check_proportion_sums,
    composition_rows,
    compute_condition_composition,
)
from ._plotting import (
    axis_label,
    crop_pdf,
    plain_text_label,
    plot_categorical_embedding,
    plot_continuous_embedding,
    set_default_plot_params,
    use_latex_rendering,
)

__all__ = [
    "axis_label",
    "check_exported_composition",
    "check_proportion_sums",
    "composition_rows",
    "compute_condition_composition",
    "crop_pdf",
    "drop_expression_matrices",
    "plain_text_label",
    "plot_categorical_embedding",
    "plot_continuous_embedding",
    "set_default_plot_params",
    "use_latex_rendering",
    "write_h5ad",
]
