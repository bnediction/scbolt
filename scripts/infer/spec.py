#!/usr/bin/env python

import argparse
import os
from pathlib import Path

import bonesis
import bonesistools as bt
import pandas as pd
import yaml
from utils import (
    get_cfg,
    load_bonesis_code,
    load_prior_network,
    remove_forbidden_nodes,
)

from scbolt import cli, console

bonesis.settings["quiet"] = True
script_name = Path(__file__).name


parser = argparse.ArgumentParser(
    prog="spec",
    description="""Check whether BoNesis properties are well defined and
convert model specifications (format: yml) and binarized macrostates
(format: csv) into five files:
    - model (txt): dynamical Boolean properties
    - metastates (csv): partially binarized metastates
    - important-nodes (txt): nodes prioritized to appear in Boolean network solutions
    - mandatory-nodes (txt): nodes forced to appear in Boolean network solutions
    - forbidden-nodes (txt): nodes excluded from Boolean network solutions

The model specification file (format: yml) recognizes four sections:
    - constraints (required list of dynamical Boolean properties in BoNesis
      syntax)
    - important_nodes (list of nodes prioritized to appear in Boolean network solutions)
    - mandatory_nodes (list of nodes forced to appear in Boolean network solutions)
    - forbidden_nodes (list of nodes excluded from Boolean network solutions)

The legacy dynamical_constraints section remains accepted as an alias for
constraints.
""",
    usage=(
        f"python {script_name} <FILE> <FILE> --model <FILE> --metastates <FILE> "
        "--mandatory-nodes <FILE> --important-nodes <FILE> "
        "--forbidden-nodes <FILE> [<args>]"
    ),
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    dest="model_specification",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing model specifications for BoNesis (format: yml)",
)

parser.add_argument(
    "macrostates",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing partially binarized macrostates (format: csv)",
)

parser.add_argument(
    "--model",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    required=True,
    help="output file storing dynamical Boolean properties (format: txt)",
)

parser.add_argument(
    "--metastates",
    dest="metastates",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing partially binarized metastates (format: csv)",
)

parser.add_argument(
    "--important-nodes",
    dest="important_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help=(
        "output file storing important nodes prioritized to appear (format: json or "
        "txt)"
    ),
)

parser.add_argument(
    "--mandatory-nodes",
    dest="mandatory_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="output file storing mandatory nodes forced to appear (format: json or txt)",
)

parser.add_argument(
    "--forbidden-nodes",
    dest="forbidden_nodes",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing nodes excluded from the inferred networks (format: txt)",
)

parser.add_argument(
    "--domain",
    dest="domain",
    action=cli.Bonesis_domain,
    required=False,
    default="collectri",
)

parser.add_argument(
    "--sep",
    dest="sep",
    type=str,
    required=False,
    default=",",
    metavar="CHAR",
    help="field delimiter for csv format (default: ',')",
)

parser.add_argument(
    "--organism",
    dest="organism",
    action=cli.Store_organism,
    default="mouse",
    required=False,
)

parser.add_argument(
    "--dorothea-levels",
    dest="dorothea_levels",
    nargs="+",
    choices=["A", "B", "C", "D"],
    default=None,
    metavar="[A | B | C | D]",
    help=(
        "DoRothEA confidence levels used when --domain dorothea "
        "(default: A B C for modern API; A B C D for legacy API)"
    ),
)

parser.add_argument(
    "--geneinfo-version",
    dest="geneinfo_version",
    action=cli.Store_version,
    allow_current=False,
    allow_bundled=True,
    allow_date=False,
    allow_path=True,
    required=False,
    default="bundled",
    help="NCBI gene_info source used for gene name standardization (default: bundled)",
)

parser.add_argument(
    "--omnipath-version",
    dest="omnipath_version",
    action=cli.Store_version,
    allow_current=False,
    required=False,
    default="latest",
    help=(
        "OmniPath resource version used when --domain is collectri or dorothea "
        "(default: latest)"
    ),
)

parser.add_argument(
    "--hcop-version",
    dest="hcop_version",
    type=str,
    required=False,
    default="bundled",
    help=(
        "HCOP orthology version used when --domain is collectri or dorothea (default: "
        "bundled)"
    ),
)

parser.add_argument(
    "--dorothea-api",
    dest="dorothea_api",
    choices=["modern", "legacy"],
    required=False,
    default="modern",
    help="DoRothEA API flavor used when --domain dorothea (default: modern)",
)

parser.add_argument(
    "--dorothea-compatibility",
    dest="dorothea_compatibility",
    action=cli.Store_boolean,
    required=False,
    default=True,
    help="reproduce decoupler DoRothEA duplicated-pair handling (default: true)",
)

args = parser.parse_args()

for outfile in [
    args.macrostates,
    args.model,
    args.mandatory_nodes,
    args.important_nodes,
    args.forbidden_nodes,
]:
    if not Path(os.path.dirname(outfile)).exists():
        os.makedirs(Path(os.path.dirname(outfile)))

identifiers = bt.resources.ncbi.identifiers(
    organism=args.organism,
    version=args.geneinfo_version,
)

model_specification_path = console.format_path(args.model_specification)
console.print_task(f"loading model specification (file={model_specification_path})")

with open(args.model_specification, "r") as file:
    specification = yaml.safe_load(file) or {}

if not isinstance(specification, dict):
    parser.error("model specification must be a YAML mapping")

specification_sections = {
    "constraints",
    "dynamical_constraints",
    "important_nodes",
    "mandatory_nodes",
    "forbidden_nodes",
}
unknown_sections = sorted(set(specification) - specification_sections)
if unknown_sections:
    parser.error(
        "unknown model specification section(s): " + ", ".join(unknown_sections)
    )


def read_specification_list(key: str, *, required: bool = False) -> list[str]:
    if key not in specification:
        if required:
            parser.error(f"missing model specification section: {key}")
        return []

    values = specification[key]
    if values is None:
        return []
    if not isinstance(values, list):
        parser.error(f"model specification section '{key}' must be a list")
    if not all(isinstance(value, str) for value in values):
        parser.error(f"model specification section '{key}' must contain only strings")
    return values


if "constraints" in specification and "dynamical_constraints" in specification:
    parser.error(
        "model specification defines both 'constraints' and the deprecated "
        "'dynamical_constraints' section"
    )

constraint_section = (
    "constraints" if "constraints" in specification else "dynamical_constraints"
)
dynamical_constraints = read_specification_list(constraint_section, required=True)
important_nodes = set(read_specification_list("important_nodes"))
mandatory_nodes = set(read_specification_list("mandatory_nodes"))
forbidden_nodes = set(read_specification_list("forbidden_nodes"))

console.print_task(f"loading CSV table (file={console.format_path(args.macrostates)})")

macrostates_df = identifiers(
    pd.read_csv(args.macrostates, index_col=0, sep=args.sep), axis="columns"
)

console.print_task("getting binarized states")

important_nodes = set(identifiers(important_nodes))
mandatory_nodes = set(identifiers(mandatory_nodes))
forbidden_nodes = set(identifiers(forbidden_nodes))

for section, nodes in (
    ("important_nodes", important_nodes),
    ("mandatory_nodes", mandatory_nodes),
):
    conflicts = forbidden_nodes & nodes
    if conflicts:
        parser.error(
            "model specification sections 'forbidden_nodes' and "
            f"'{section}' overlap: {', '.join(sorted(conflicts))}"
        )

forbidden_in_data = macrostates_df.columns.isin(forbidden_nodes)
if forbidden_in_data.any():
    removed_count = int(forbidden_in_data.sum())
    total_nodes = len(forbidden_in_data)
    kept_nodes = total_nodes - removed_count
    console.print_info(
        "removing forbidden features "
        f"(kept={kept_nodes}/{total_nodes} "
        f"({100 * kept_nodes / total_nodes:.1f}%), "
        f"removed={removed_count})"
    )
    macrostates_df = macrostates_df.loc[:, ~forbidden_in_data]

has_defined_state = macrostates_df.apply(
    lambda values: pd.to_numeric(values, errors="coerce").isin([0, 1]).any(),
    axis=0,
)
removed_nodes = macrostates_df.columns[~has_defined_state]
if len(removed_nodes) > 0:
    kept_nodes = int(has_defined_state.sum())
    total_nodes = len(has_defined_state)
    console.print_info(
        "removing undefined features "
        f"(kept={kept_nodes}/{total_nodes} "
        f"({100 * kept_nodes / total_nodes:.1f}%), "
        f"removed={len(removed_nodes)})"
    )
    macrostates_df = macrostates_df.loc[:, has_defined_state]

macrostates_cfg = get_cfg(macrostates_df, axis="index", identifiers=identifiers)

console.print_info("checking Boolean properties")

grn = load_prior_network(
    args.domain,
    args.organism,
    identifiers,
    args.dorothea_levels,
    args.omnipath_version,
    args.hcop_version,
    args.dorothea_api,
    args.dorothea_compatibility,
)
grn = remove_forbidden_nodes(grn, forbidden_nodes)
pkn_options = {
    "canonic": True,
    "maxclause": 8,
}
pkn = bonesis.domains.InfluenceGraph(grn, **pkn_options)
bo = bonesis.BoNesis(pkn, macrostates_cfg)

namespace = {"bo": bo}

for constraint in dynamical_constraints:
    try:
        load_bonesis_code(
            bo,
            constraint,
            filename=str(args.model_specification),
            namespace=namespace,
        )
    except Exception as error:
        raise RuntimeError(
            f"invalid dynamical Boolean constraint: {constraint}"
        ) from error

model_path = console.format_path(args.model)
console.print_task(f"saving Boolean specification (file={model_path})")

with open(args.model, "w") as file:
    for constraint in dynamical_constraints:
        file.write(f"{constraint}\n")

console.print_task(f"saving CSV table (file={console.format_path(args.metastates)})")

macrostates_df.to_csv(args.metastates, sep=",", index=True)

important_nodes_path = console.format_path(args.important_nodes)
console.print_task(f"saving node list (file={important_nodes_path})")

with open(args.important_nodes, "w") as file:
    for node in sorted(important_nodes):
        file.write(f"{node}\n")

mandatory_nodes_path = console.format_path(args.mandatory_nodes)
console.print_task(f"saving node list (file={mandatory_nodes_path})")

with open(args.mandatory_nodes, "w") as file:
    for node in sorted(mandatory_nodes):
        file.write(f"{node}\n")

forbidden_nodes_path = console.format_path(args.forbidden_nodes)
console.print_task(f"saving node list (file={forbidden_nodes_path})")

with open(args.forbidden_nodes, "w") as file:
    for node in sorted(forbidden_nodes):
        file.write(f"{node}\n")
