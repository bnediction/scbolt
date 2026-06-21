#!/usr/bin/env python

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import argparse
import csv
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

import cli

Field = tuple[str, str]
script_name = Path(__file__).name


@dataclass
class Operation:
    inputs: list[Path]
    outputs: list[Path] = field(default_factory=list)
    requires: dict[int, set[Field]] = field(default_factory=dict)
    provides: set[Field] = field(default_factory=set)
    preserve_from: int | None = 0


def field(group: str, name: str | None) -> set[Field]:
    return {(group, name)} if name else set()


def fields(group: str, names: list[str] | None) -> set[Field]:
    return {(group, name) for name in names or []}


def option(tokens: list[str], name: str) -> str | None:
    try:
        return tokens[tokens.index(name) + 1]
    except (ValueError, IndexError):
        return None


def option_values(tokens: list[str], name: str) -> list[str]:
    try:
        i = tokens.index(name) + 1
    except ValueError:
        return []
    values = []
    while i < len(tokens) and not tokens[i].startswith("-"):
        values.append(tokens[i])
        i += 1
    return values


def h5ad(path: str | None) -> Path | None:
    if path and path.endswith(".h5ad"):
        return Path(path).resolve()
    return None


def logical_commands(lines: list[str]) -> list[str]:
    commands, current = [], ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
        else:
            commands.append(current + line)
            current = ""
    if current:
        commands.append(current)
    return commands


def command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def script_token(tokens: list[str]) -> str | None:
    for token in tokens:
        if token.endswith(".py") or token.endswith(".R"):
            return token
    return None


def positional_after_script(tokens: list[str], script: str) -> list[str]:
    args = tokens[tokens.index(script) + 1 :]
    return [arg for arg in args if not arg.startswith("-")]


def embedding_key(tokens: list[str]) -> str:
    embedding = option(tokens, "--embedding") or "umap"
    return "X_tsne" if embedding == "tsne" else "X_umap"


def clustering_embeddings() -> set[Field]:
    return {
        ("obsm", "X_umap"),
        ("obsm", "X_tsne"),
        ("obsm", "X_se"),
    }


def hvg_layer(tokens: list[str]) -> set[Field]:
    flavor = option(tokens, "--flavor")
    if "--only-hvg" not in tokens:
        return set()
    return field("layers", "counts" if flavor == "seurat_v3" else "log-norm")


def parse_script_operation(tokens: list[str], script: str) -> Operation | None:
    args = positional_after_script(tokens, script)
    name = Path(script).name

    if name == "filter.py":
        infile, outfile = map(h5ad, args[:2])
        return Operation(
            [infile],
            [outfile],
            {0: field("layers", "counts")},
            {
                ("obs", "G1_score"),
                ("obs", "S_score"),
                ("obs", "G2M_score"),
                ("obs", "n_genes_by_counts"),
                ("obs", "total_counts"),
            },
        )

    if name == "norm.py":
        infile, outfile = map(h5ad, args[:2])
        required = field("layers", option(tokens, "--expression"))
        required |= fields("obs", option_values(tokens, "--correction"))
        return Operation(
            [infile],
            [outfile],
            {0: required},
            {
                ("layers", "norm"),
                ("layers", "log-norm"),
                ("layers", "scale"),
                ("layers", "correct"),
            },
        )

    if name == "clustering.py":
        infile, outfile = map(h5ad, args[:2])
        required = {("layers", "correct"), ("layers", "counts"), ("layers", "log-norm")}
        return Operation(
            [infile],
            [outfile],
            {0: required},
            {
                ("var", "highly_variable"),
                ("var", "highly_variable_rank"),
                ("obsm", "X_pca"),
                ("obsp", "connectivities"),
                ("obs", "cluster"),
                *clustering_embeddings(),
            },
        )

    if name == "integration.py":
        outfile = h5ad(option(tokens, "--outfile"))
        inputs = [path for path in map(h5ad, args) if path and path != outfile]
        required = {("layers", "counts"), ("layers", "log-norm"), ("layers", "correct")}
        return Operation(
            inputs,
            [outfile],
            {i: set(required) for i in range(len(inputs))},
            {
                ("obs", "condition"),
                ("var", "highly_variable"),
                ("var", "highly_variable_rank"),
                ("obsm", "X_pca"),
                ("obsp", "connectivities"),
                ("obs", "cluster"),
                *clustering_embeddings(),
            },
        )

    if name == "annotation.py":
        infile, outfile = map(h5ad, args[:2])
        new_obs = option(tokens, "--new-obs")
        return Operation(
            [infile],
            [outfile],
            {0: field("obs", option(tokens, "--obs"))},
            (
                {
                    ("obs", new_obs),
                }
                if new_obs
                else set()
            ),
        )

    if name == "pipe_its.py":
        integrated = h5ad(args[0])
        outfiles = [
            path for path in map(h5ad, option_values(tokens, "--outfiles")) if path
        ]
        specifics = [
            path for path in map(h5ad, args[1:]) if path and path not in outfiles
        ]
        requires = {0: field("obs", option(tokens, "--obs-label"))}
        requires[0] |= fields("obs", option_values(tokens, "--obs"))
        requires[0] |= fields("var", option_values(tokens, "--var"))
        provides = fields("obs", option_values(tokens, "--obs"))
        provides |= fields("var", option_values(tokens, "--var"))
        return Operation([integrated, *specifics], outfiles, requires, provides, 1)

    if name == "velocity.py":
        infile, outfile = map(h5ad, args[:2])
        required = {
            ("layers", "counts"),
            ("layers", "spliced"),
            ("layers", "unspliced"),
            ("obsm", "X_pca"),
            ("obsm", "X_umap"),
            ("obsp", "connectivities"),
        }
        required |= field("obs", option(tokens, "--cluster"))
        if "--only-hvg" in tokens:
            required.add(("var", "highly_variable"))
        return Operation(
            [infile],
            [outfile],
            {0: required},
            {
                ("layers", "Ms"),
                ("layers", "Mu"),
                ("layers", "variance_velocity"),
                ("layers", "velocity"),
            },
        )

    if name == "potency.py":
        infile = h5ad(args[0])
        required = field("layers", option(tokens, "--expression"))
        required |= field("obs", option(tokens, "--cluster"))
        required |= field("obsm", option(tokens, "--representation"))
        return Operation([infile], [], {0: required}, set(), None)

    if name == "adata_conversion.py":
        infile = h5ad(args[0])
        required = field("layers", option(tokens, "--expression"))
        if "--only-hvg" in tokens:
            required.add(("var", "highly_variable"))
        return Operation([infile], [], {0: required}, set(), None)

    if name == "load_geo.py":
        outfile = h5ad(args[1])
        return Operation(
            [],
            [outfile],
            {},
            {
                ("layers", "counts"),
            },
            None,
        )

    if name == "add_to_anndata.py":
        infile, outfile = map(h5ad, args[:2])
        csv_files = option_values(tokens, "--csv")
        csv_names = {Path(path).name for path in csv_files}
        provides = set()
        if "potency_scores.csv" in csv_names:
            provides.add(("obs", "cytotrace_score"))
        elif any(name in {"mstates.csv", "mcts.csv"} for name in csv_names):
            provides.add(("obs", "macrostate"))
        return Operation([infile], [outfile], {}, provides)

    if name == "prepare_macrostate_h5ad.py":
        infile, outfile = map(h5ad, args[:2])
        required = {
            ("layers", "log-norm"),
            ("obs", option(tokens, "--macrostate-obs") or "macrostate"),
            ("obsm", option(tokens, "--representation") or "X_umap"),
        }
        required |= field("obs", option(tokens, "--condition-obs"))
        return Operation([infile], [outfile], {0: required}, set())

    if name == "cellrank_mstates.py":
        infile, outfile = map(h5ad, args[:2])
        required = {
            ("layers", option(tokens, "--scvelo-first-moment") or "Ms"),
            ("layers", option(tokens, "--scvelo-velocity") or "velocity"),
            ("obsp", "connectivities"),
            ("obsm", "X_umap"),
        }
        required |= field("obs", option(tokens, "--obs"))
        required |= field("obs", option(tokens, "--cytotrace-score"))
        return Operation([infile], [outfile], {0: required}, {("obs", "macrostate")})

    if name == "stream_mstates.py":
        infile, outfile = map(h5ad, args[:2])
        required = field("obs", option(tokens, "--obs"))
        required |= field("obsm", option(tokens, "--representation"))
        return Operation([infile], [outfile], {0: required}, {("obs", "macrostate")})

    if name == "knnsc_mstates.py":
        infile, outfile = map(h5ad, args[:2])
        required = field("obs", option(tokens, "--obs"))
        required |= field("obsm", option(tokens, "--embedding"))
        return Operation([infile], [outfile], {0: required}, {("obs", "macrostate")})

    if name == "bin_cells_scboolseq.py":
        infile = h5ad(args[0])
        outfile = h5ad(option(tokens, "--outfile"))
        return Operation(
            [infile],
            [outfile],
            {0: field("layers", option(tokens, "--expression"))},
            {
                ("layers", "bin"),
                ("var", "distribution"),
            },
        )

    if name == "bin_clust_scboolseq.py":
        infile = h5ad(args[0])
        required = field("layers", option(tokens, "--expression") or "bin")
        required |= field("var", option(tokens, "--distribution") or "distribution")
        required |= field("obs", option(tokens, "--cluster"))
        required |= field("obs", option(tokens, "--condition"))
        required |= field("obsm", option(tokens, "--representation"))
        return Operation([infile], [], {0: required}, set(), None)

    if name == "bin_dea.py":
        infile = h5ad(args[0])
        required = field("layers", option(tokens, "--expression"))
        required |= field("obs", option(tokens, "--cluster"))
        required |= field("obsm", option(tokens, "--representation"))
        return Operation([infile], [], {0: required}, set(), None)

    if name == "dea.py":
        infile = h5ad(args[0])
        required = field("obs", option(tokens, "--cluster"))
        required |= field("layers", option(tokens, "--expression"))
        return Operation([infile], [], {0: required}, set(), None)

    if name == "scoring.py":
        infile = h5ad(args[0])
        required = {
            ("obs", option(tokens, "--cluster") or "cluster"),
            ("obs", "n_genes_by_counts"),
            ("obs", "total_counts"),
        }
        return Operation([infile], [], {0: required}, set(), None)

    if name == "hvg.py":
        infile = h5ad(args[0])
        return Operation(
            [infile],
            [],
            {0: field("layers", option(tokens, "--expression"))},
            set(),
            None,
        )

    if name == "plot_embedding.py":
        infile = h5ad(option(tokens, "--infile"))
        required = field("obs", option(tokens, "--obs"))
        required |= field("obsm", option(tokens, "--representation"))
        return Operation([infile], [], {0: required}, set(), None)

    if name == "plot_composition.py":
        infile = h5ad(option(tokens, "--infile"))
        required = field("obs", option(tokens, "--obs"))
        required |= field("obs", option(tokens, "--groupby"))
        return Operation([infile], [], {0: required}, set(), None)

    return None


def parse_finalized_velocyto(tokens: list[str]) -> Operation | None:
    command = " ".join(tokens)
    if 'adata.layers["counts"]' not in command:
        return None
    h5ads = [path for path in map(h5ad, tokens) if path]
    if len(h5ads) < 2:
        return None
    return Operation(
        [h5ads[-2]],
        [h5ads[-1]],
        {},
        {
            ("layers", "ambiguous"),
            ("layers", "spliced"),
            ("layers", "unspliced"),
            ("layers", "counts"),
        },
    )


def parse_operations(dry_run: Path) -> list[Operation]:
    operations = []
    for command in logical_commands(dry_run.read_text().splitlines()):
        tokens = command_tokens(command)
        script = script_token(tokens)
        operation = parse_script_operation(tokens, script) if script else None
        operation = operation or parse_finalized_velocyto(tokens)
        if operation:
            operation.inputs = [path for path in operation.inputs if path]
            operation.outputs = [path for path in operation.outputs if path]
            operations.append(operation)
    return operations


def boundary_requirements(operations: list[Operation]) -> dict[Path, set[Field]]:
    needed: dict[Path, set[Field]] = defaultdict(set)
    produced = {output for operation in operations for output in operation.outputs}
    for operation in reversed(operations):
        downstream = set()
        for output in operation.outputs:
            downstream |= needed.pop(output, set())
        if operation.preserve_from is not None and operation.inputs:
            index = min(operation.preserve_from, len(operation.inputs) - 1)
            needed[operation.inputs[index]] |= downstream - operation.provides
        for index, fields_ in operation.requires.items():
            if index < len(operation.inputs):
                needed[operation.inputs[index]] |= fields_
    return {
        path: fields_
        for path, fields_ in needed.items()
        if path not in produced and fields_
    }


def reference(path: Path, conditions: list[str]) -> str:
    parts = set(path.parts)
    if "integrated" in parts:
        return "integrated"
    return next((condition for condition in conditions if condition in parts), "input")


def has_field(h5ad_file: Any, field_: Field) -> bool:
    group, key = field_
    return group in h5ad_file and key in h5ad_file[group]


def field_label(field_: Field) -> str:
    group, key = field_
    label = "layer" if group == "layers" else group
    return f"{label} '{key}'"


def check_h5ad(
    path: Path, fields_: set[Field], conditions: list[str]
) -> tuple[list[str], list[str]]:
    ref = reference(path, conditions)
    success, failure = [], []
    if not path.is_file():
        return [], [f"required h5ad file not found: {path} (reference: {ref})"]
    try:
        import h5py
    except ImportError:
        return [], ["h5ad metadata checker requires h5py"]
    try:
        h5ad_file = h5py.File(path, "r")
    except OSError as error:
        return [], [f"h5ad metadata invalid: {path} ({error})"]
    with h5ad_file:
        for field_ in sorted(fields_):
            message = f"h5ad metadata: {field_label(field_)}"
            if has_field(h5ad_file, field_):
                success.append(f"{message} found (reference: {ref})")
            else:
                failure.append(f"{message} missing ({path}, reference: {ref})")
    return success, failure


def potency_csv_sources(dry_run: Path) -> list[Path]:
    sources = []
    for command in logical_commands(dry_run.read_text().splitlines()):
        if "awk -F," not in command or 'txt="score"' not in command:
            continue
        tokens = command_tokens(command)
        for token in tokens:
            if token.endswith("potency.csv"):
                sources.append(Path(token).resolve())
    return sources


def produced_potency_csv(operations: list[Operation], dry_run: Path) -> set[Path]:
    produced = set()
    for command in logical_commands(dry_run.read_text().splitlines()):
        tokens = command_tokens(command)
        script = script_token(tokens)
        if script and Path(script).name == "potency.py":
            outdir = Path(positional_after_script(tokens, script)[1]).resolve()
            csv_name = option(tokens, "--csv")
            if csv_name:
                produced.add(outdir / csv_name)
    return produced


def check_csv_score(path: Path) -> tuple[list[str], list[str]]:
    if not path.is_file():
        return [], [f"required file not found: {path}"]
    with path.open(newline="") as file:
        header = next(csv.reader(file), [])
    if "score" in header:
        return [f"file metadata: column 'score' found ({path})"], []
    return [], [f"file metadata invalid: column 'score' missing ({path})"]


def emit(status: str, messages: list[str]) -> None:
    for message in messages:
        print(f"{status}\t{message}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog=script_name,
        formatter_class=cli.HelpFormatter,
    )
    parser.add_argument("--dry-run", type=Path, required=True)
    parser.add_argument("--conditions", nargs="*", default=[])
    args = parser.parse_args()

    operations = parse_operations(args.dry_run)
    failures = []

    for path, fields_ in sorted(boundary_requirements(operations).items()):
        success, failure = check_h5ad(path, fields_, args.conditions)
        emit("success", success)
        emit("failure", failure)
        failures.extend(failure)

    for path in sorted(
        set(potency_csv_sources(args.dry_run))
        - produced_potency_csv(operations, args.dry_run)
    ):
        success, failure = check_csv_score(path)
        emit("success", success)
        emit("failure", failure)
        failures.extend(failure)

    return 0


if __name__ == "__main__":
    sys.exit(main())
