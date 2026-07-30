#!/usr/bin/env python3
"""Validate scBOLT project YAML and expose its internal settings."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterable

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode


STRING = "string"
BOOLEAN = "boolean"
INTEGER = "integer"
NUMBER = "number"
SCALAR = "scalar"
STRING_LIST = "string-list"
SCALAR_LIST = "scalar-list"
STRING_OR_LIST = "string-or-list"
BOOLEAN_OR_NUMBER = "boolean-or-number"


@dataclass(frozen=True)
class Parameter:
    variable: str = ""
    kind: str = STRING
    conditional: bool = False
    fanout: tuple[str, ...] = ()


def _parameters() -> dict[str, Parameter]:
    parameters: dict[str, Parameter] = {}

    def add(key: str, variable: str, kind: str = STRING) -> None:
        parameters[key] = Parameter(variable=variable, kind=kind)

    def conditional(key: str, variable: str, kind: str) -> None:
        parameters[key] = Parameter(
            variable=variable,
            kind=kind,
            conditional=True,
        )

    def fanout(key: str, kind: str, *variables: str) -> None:
        parameters[key] = Parameter(kind=kind, fanout=variables)

    add("backend", "BACKEND")
    add("container_image", "SCBOLT_IMAGE")
    add("container_engine", "SCBOLT_CONTAINER_ENGINE")
    add("container_args", "SCBOLT_CONTAINER_ARGS", STRING_OR_LIST)
    add("container_mounts", "SCBOLT_CONTAINER_MOUNTS", STRING_LIST)
    add("project_dir", "PROJECT_DIR")
    add("inference_dir", "INFERENCE_DIR")
    add("resources_dir", "RESOURCES_DIR")
    add("memory", "MEMORY", SCALAR)
    add("jobs", "JOBS", INTEGER)
    add("seed", "SEED", INTEGER)
    add("logging", "LOGGING", BOOLEAN)
    add("openblas_core_type", "OPENBLAS_CORETYPE")
    add("organism", "ORGANISM")
    add("conditions", "CONDITIONS", STRING_LIST)
    add("references", "REFERENCES", STRING_LIST)
    conditional("gsm", "GSM", STRING)
    conditional("sra", "SRA", STRING_OR_LIST)
    add("count_files", "COUNT_FILES", STRING_LIST)
    add("macrostate_files", "MACROSTATE_FILES", STRING_LIST)
    add("binarization_file", "BINARIZATION_FILE")
    add("representation", "REPRESENTATION")
    add("label_column", "LABEL_COL")
    add("old_files", "OLD_FILES", STRING_LIST)
    add("labels", "LABEL", STRING_LIST)
    add("spec_file", "SPEC_FILE")
    add("genome_url", "genome_url")
    add("repeat_masker_url", "repeat_msk_url")
    add("gene_ontology_url", "go_organism_url")

    add("alignment_tool", "ALIGNMENT_TOOL")
    add("star_barcode_length", "STAR_CB_LEN", INTEGER)
    add("star_umi_length", "STAR_UMI_LEN", INTEGER)
    add("star_whitelist", "STAR_WHITELIST")
    add("star_barcode_filter", "STAR_BARCODE_FILTER")
    add("star_min_umi", "STAR_MIN_UMI", INTEGER)
    add("star_top_barcodes", "STAR_TOP_BARCODES", INTEGER)

    add("gene_dropout", "GENE_DROPOUT", NUMBER)
    add("gene_expression", "GENE_EXPRESSION", SCALAR_LIST)
    add("gene_counts", "GENE_COUNTS", SCALAR_LIST)
    add("cell_dropout", "CELL_DROPOUT", NUMBER)
    add("cell_expression", "CELL_EXPRESSION", SCALAR_LIST)
    add("cell_reads", "CELL_READS", SCALAR_LIST)
    add("mad_deviation", "MAD_DEVIATION", SCALAR_LIST)
    add("consistent_mad", "CONSISTENT_MAD", BOOLEAN)
    add("mitochondrial_fraction", "MT", NUMBER)
    add("cell_cycle_correction", "CC_CORRECTION", BOOLEAN)

    fanout("hvg_method", STRING, "ANALYSIS_HVG_METHOD", "BIN_HVG_METHOD")
    fanout("hvg_top", INTEGER, "ANALYSIS_HVG_TOP", "BIN_HVG_TOP")
    fanout("hvg_span", NUMBER, "ANALYSIS_HVG_SPAN", "BIN_HVG_SPAN")
    fanout("hvg_bins", INTEGER, "ANALYSIS_HVG_BINS", "BIN_HVG_BINS")
    add("analysis_hvg_method", "ANALYSIS_HVG_METHOD")
    add("analysis_hvg_top", "ANALYSIS_HVG_TOP", INTEGER)
    add("analysis_hvg_span", "ANALYSIS_HVG_SPAN", NUMBER)
    add("analysis_hvg_bins", "ANALYSIS_HVG_BINS", INTEGER)
    add("binarization_hvg_method", "BIN_HVG_METHOD")
    add("binarization_hvg_top", "BIN_HVG_TOP", INTEGER)
    add("binarization_hvg_span", "BIN_HVG_SPAN", NUMBER)
    add("binarization_hvg_bins", "BIN_HVG_BINS", INTEGER)
    add("binarization_include_nodes", "BIN_INCLUDE_NODES", STRING_LIST)

    add("integration", "INTEGRATION")
    add("pca_dimensions", "DIM_PCA", INTEGER)
    add("embedding_dimensions", "DIM_EMBEDDING", INTEGER)
    add("centered_pca", "CENTERED_PCA", BOOLEAN)
    add("pca_only_hvg", "PCA_ONLY_HVG", BOOLEAN)
    add("neighbors", "NEIGHBORS", INTEGER)
    add("metric", "METRIC")
    add("resolution", "RESOLUTION", NUMBER)
    add("umap_min_dist", "MIN_DIST", NUMBER)
    add("umap_spread", "SPREAD", NUMBER)
    add("embedding_iterations", "EMBEDDING_N_ITER", INTEGER)

    add("dea_method", "DEA_METHOD")
    add("logfc", "LOGFC", NUMBER)
    add("correction", "CORRECTION")
    add("alpha", "ALPHA", NUMBER)
    add("moment_dimensions", "DIM_MOMENT", INTEGER)
    add("velocity_only_hvg", "VELOCITY_ONLY_HVG", BOOLEAN)
    add("velocity_mode", "SMM_MODE")
    add("potency_batch_size", "BATCH_SIZE", INTEGER)
    add("potency_smoothing_batch_size", "SMOOTH_BATCH_SIZE", INTEGER)

    add("macrostate_size", "MACROSTATE_SIZE", INTEGER)
    add("macrostate_method", "MACROSTATE_METHOD")
    add("cotan_method", "COTAN_METHOD")
    add("cotan_only_hvg", "COTAN_ONLY_HVG", BOOLEAN)
    add("cotan_max_iterations", "MAX_ITER", INTEGER)
    add("cellrank_method", "CELLRANK_METHOD")
    add("cellrank_states", "STATES", INTEGER)
    add("cellrank_initial_states", "INITIAL_STATES", INTEGER)
    add("cellrank_terminal_states", "TERMINAL_STATES", INTEGER)
    add("cellrank_stability", "CELLRANK_STABILITY", NUMBER)
    add("cellrank_alpha", "CELLRANK_ALPHA", NUMBER)

    add("stream_clustering_method", "CLUSTERING_METHOD")
    add("stream_cluster_number", "CLUSTER_NUMBER", INTEGER)
    add("stream_alpha", "ALPHA_EPG", NUMBER)
    add("stream_mu", "MU_EPG", NUMBER)
    add("stream_lambda", "LAMBDA_EPG", NUMBER)
    add("stream_extend", "EXTEND_EPG", BOOLEAN)
    add("stream_extend_mode", "EXTEND_MODE")
    add("stream_extend_parameter", "EXTEND_PARAMETER", NUMBER)
    add("stream_prune", "PRUNE_EPG", BOOLEAN)
    add("stream_collapse_parameter", "COLLAPSE_PARAMETER", BOOLEAN_OR_NUMBER)

    add("knnsc_embedding", "KNNSC_EMBEDDING")
    add("knnsc_dimensions", "KNNSC_DIMENSION", SCALAR_LIST)
    add("knnsc_neighbors", "KNNSC_NEIGHBORS", INTEGER)
    add("knnsc_min_cluster_size", "KNNSC_MIN_CLUSTER_SIZE", INTEGER)
    conditional("knnsc_centrality", "KNNSC_CENTRALITY", STRING_LIST)
    conditional("knnsc_periphery", "KNNSC_PERIPHERY", STRING_LIST)

    add("binarization_method", "BIN_METHOD")
    add("scboolseq_only_hvg", "BIN_SCBOOLSEQ_ONLY_HVG", BOOLEAN)
    add("scboolseq_openblas_threads", "SCBOOLSEQ_OPENBLAS_THREADS", SCALAR)
    add("scboolseq_omp_threads", "SCBOOLSEQ_OMP_THREADS", SCALAR)
    add("unimodal_quantile", "UNIMODAL_QUANTILE", NUMBER)
    add("zeroes_are_zeroes", "ZEROES_ARE_ZEROES", BOOLEAN)
    add("undefined_threshold", "NANS_THRESHOLD", NUMBER)
    add("bimodal_threshold", "BIMODAL_THRESHOLD", NUMBER)
    add("zero_inflated_threshold", "ZEROINF_THRESHOLD", NUMBER)
    add("unimodal_threshold", "UNIMODAL_THRESHOLD", NUMBER)
    add("binarization_dea_only_hvg", "BIN_DEA_ONLY_HVG", BOOLEAN)
    add("binarization_logfc", "BIN_LOGFC", NUMBER)
    add("binarization_correction", "BIN_CORRECTION")
    add("binarization_alpha", "BIN_ALPHA", NUMBER)

    add("prior_knowledge", "PRIOR_KNOWLEDGE")
    add("geneinfo_version", "GENEINFO_VERSION")
    add("omnipath_version", "OMNIPATH_VERSION")
    add("hcop_version", "HCOP_VERSION")
    add("dorothea_api", "DOROTHEA_API")
    add("dorothea_compatibility", "DOROTHEA_COMPATIBILITY", BOOLEAN)
    add("dorothea_levels", "DOROTHEA_LEVELS", STRING_LIST)
    add("max_clauses", "MAX_CLAUSES", INTEGER)
    add("clause_continuation_soft", "CLAUSE_CONTINUATION_SOFT", BOOLEAN)
    add("clause_continuation_relaxed", "CLAUSE_CONTINUATION_RELAXED", BOOLEAN)
    add("clause_continuation_seed", "CLAUSE_CONTINUATION_SEED", BOOLEAN)
    add("clause_continuation_lock", "CLAUSE_CONTINUATION_LOCK", BOOLEAN)
    add("clause_bound_patience", "PATIENCE_CLAUSE_BOUND", SCALAR)
    add("domain_continuation_soft", "DOMAIN_CONTINUATION_SOFT", BOOLEAN)
    add("domain_continuation_relaxed", "DOMAIN_CONTINUATION_RELAXED", BOOLEAN)
    add("domain_continuation_seed", "DOMAIN_CONTINUATION_SEED", BOOLEAN)
    add("domain_continuation_lock", "DOMAIN_CONTINUATION_LOCK", BOOLEAN)
    add("domain_wave_patience", "PATIENCE_DOMAIN_WAVE", SCALAR)
    add("minimum_domain_yield", "MIN_DOMAIN_YIELD", NUMBER)
    add("maximum_domain_refreshes", "MAX_DOMAIN_REFRESHES", INTEGER)
    add("clingo_threads", "CLINGO_THREADS", INTEGER)

    for stage in ("soft", "consts", "relaxed", "seed", "lock"):
        suffix = stage.upper()
        add(f"clingo_config_{stage}", f"CLINGO_CONFIG_{suffix}")
        add(f"clingo_mode_{stage}", f"CLINGO_MODE_{suffix}")
        add(f"clingo_strategy_{stage}", f"CLINGO_STRATEGY_{suffix}")
        add(f"timeout_{stage}", f"TIMEOUT_{suffix}", SCALAR)
    add("clingo_mode_min", "CLINGO_MODE_MIN")
    add("minimize_self_loops_constants", "MIN_SELF_LOOP_CONSTS", BOOLEAN)
    add("minimize_self_loops_inference", "MIN_SELF_LOOP_INFER", BOOLEAN)
    add("configuration_formats", "CONFIG_FORMATS", STRING_LIST)
    add("graph_formats", "GRAPH_FORMATS", STRING_LIST)
    add("inference_limit", "INFER_LIMIT", INTEGER)
    return parameters


PARAMETERS = _parameters()
CONDITION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class ConfigurationError(ValueError):
    pass


def _error(path: Path, node: Node | None, message: str) -> ConfigurationError:
    location = str(path)
    if node is not None:
        location += f":{node.start_mark.line + 1}:{node.start_mark.column + 1}"
    return ConfigurationError(f"{location}: {message}")


def _scalar(path: Path, key: str, node: Node) -> str:
    if not isinstance(node, ScalarNode):
        raise _error(path, node, f"configuration key {key!r} must be a scalar")
    if any(character in node.value for character in "\r\n\0\t"):
        raise _error(path, node, f"configuration value {key!r} must be a single line")
    return node.value


def _value(path: Path, key: str, node: Node, kind: str) -> str:
    if node.tag == "tag:yaml.org,2002:null":
        return ""
    expected = {
        STRING: "a string",
        BOOLEAN: "a boolean",
        INTEGER: "an integer or null",
        NUMBER: "a number or null",
        SCALAR: "a string or number",
        STRING_LIST: "a list of strings or null",
        SCALAR_LIST: "a list of strings or numbers or null",
        STRING_OR_LIST: "a string, list of strings, or null",
        BOOLEAN_OR_NUMBER: "a boolean, number, or null",
    }[kind]
    string_tags = {"tag:yaml.org,2002:str", "tag:yaml.org,2002:timestamp"}
    number_tags = {"tag:yaml.org,2002:int", "tag:yaml.org,2002:float"}
    valid = False
    if kind == STRING:
        valid = isinstance(node, ScalarNode) and node.tag in string_tags
    elif kind == BOOLEAN:
        valid = isinstance(node, ScalarNode) and node.tag == "tag:yaml.org,2002:bool"
    elif kind == INTEGER:
        valid = isinstance(node, ScalarNode) and node.tag == "tag:yaml.org,2002:int"
    elif kind == NUMBER:
        valid = isinstance(node, ScalarNode) and node.tag in number_tags
    elif kind == SCALAR:
        valid = isinstance(node, ScalarNode) and node.tag in string_tags | number_tags
    elif kind == BOOLEAN_OR_NUMBER:
        valid = isinstance(node, ScalarNode) and node.tag in number_tags | {"tag:yaml.org,2002:bool"}
    elif kind == STRING_OR_LIST and isinstance(node, ScalarNode):
        valid = node.tag in string_tags
    elif kind in {STRING_LIST, SCALAR_LIST, STRING_OR_LIST}:
        valid = isinstance(node, SequenceNode)
        if valid:
            item_tags = string_tags if kind in {STRING_LIST, STRING_OR_LIST} else string_tags | number_tags
            valid = all(isinstance(item, ScalarNode) and item.tag in item_tags for item in node.value)
    if not valid:
        raise _error(path, node, f"configuration key {key!r} must be {expected}")
    if isinstance(node, SequenceNode):
        return " ".join(_scalar(path, key, item) for item in node.value)
    value = _scalar(path, key, node)
    if node.tag == "tag:yaml.org,2002:bool":
        return value.lower()
    return value


def _conditional_parameter(key: str) -> tuple[str, str, Parameter] | None:
    matches: list[tuple[str, str, Parameter]] = []
    for candidate, parameter in PARAMETERS.items():
        prefix = candidate + "_"
        if parameter.conditional and key.startswith(prefix) and len(key) > len(prefix):
            matches.append((candidate, key[len(prefix) :], parameter))
    return max(matches, key=lambda item: len(item[0]), default=None)


def _validate_condition(path: Path, node: Node | None, condition: str) -> None:
    if not CONDITION_PATTERN.fullmatch(condition):
        raise _error(path, node, f"invalid condition name {condition!r}")
    if condition.lower() in {"integrated", "unique"}:
        raise _error(path, node, f"reserved condition name {condition!r}")


def load(path: Path) -> tuple[dict[str, str], list[str]]:
    try:
        documents = list(yaml.compose_all(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(f"{path}: {error}") from error
    if len(documents) > 1:
        raise _error(path, documents[1], "multiple YAML documents are not supported")
    root = documents[0] if documents else None
    if root is None or root.tag == "tag:yaml.org,2002:null":
        return {}, []
    if not isinstance(root, MappingNode):
        raise _error(path, root, "configuration must be a YAML mapping")

    seen: dict[str, Node] = {}
    direct: list[tuple[str, Parameter, Node]] = []
    conditionals: list[tuple[str, Parameter, MappingNode]] = []
    unnamed: list[tuple[str, Node]] = []
    conditions: list[str] = []
    conditions_explicit = False
    for key_node, value_node in root.value:
        if not isinstance(key_node, ScalarNode) or key_node.tag != "tag:yaml.org,2002:str":
            raise _error(path, key_node, "configuration keys must be strings")
        key = key_node.value
        if key in seen:
            first = seen[key].start_mark.line + 1
            raise _error(path, key_node, f"duplicate configuration key {key!r} (first defined at line {first})")
        seen[key] = key_node
        parameter = PARAMETERS.get(key)
        flattened = None if parameter is not None else _conditional_parameter(key)
        if parameter is None and flattened is None:
            raise _error(path, key_node, f"unknown configuration key {key!r}")
        if flattened is not None:
            base, condition, parameter = flattened
            condition_node = ScalarNode("tag:yaml.org,2002:str", condition)
            condition_node.start_mark = key_node.start_mark
            condition_node.end_mark = key_node.end_mark
            conditionals.append((base, parameter, MappingNode("tag:yaml.org,2002:map", [(condition_node, value_node)])))
            continue
        assert parameter is not None
        if parameter.conditional and isinstance(value_node, MappingNode):
            conditionals.append((key, parameter, value_node))
            continue
        if parameter.conditional and value_node.tag != "tag:yaml.org,2002:null":
            unnamed.append((key, value_node))
        if key == "conditions":
            conditions_explicit = True
            raw = _value(path, key, value_node, STRING_LIST)
            conditions = raw.split() if raw else []
        direct.append((key, parameter, value_node))

    known: dict[str, str] = {}
    for condition in conditions:
        _validate_condition(path, None, condition)
        folded = condition.lower()
        if folded in known:
            raise ConfigurationError(f"{path}: duplicate conditions {known[folded]!r} and {condition!r}")
        known[folded] = condition
    for key, _, mapping in conditionals:
        for condition_node, _ in mapping.value:
            if not isinstance(condition_node, ScalarNode) or condition_node.tag != "tag:yaml.org,2002:str":
                raise _error(path, condition_node, f"{key} condition names must be strings")
            condition = condition_node.value
            _validate_condition(path, condition_node, condition)
            if condition.lower() not in known:
                if conditions_explicit:
                    raise _error(path, condition_node, f"condition {condition!r} in {key} is not listed in conditions")
                known[condition.lower()] = condition
                conditions.append(condition)
    if conditions and unnamed:
        key, node = unnamed[0]
        raise _error(path, node, f"configuration key {key!r} must be indexed by condition when named conditions are used")

    settings: dict[str, str] = {}
    shared: list[tuple[str, str]] = []
    specific: set[str] = set()
    for key, parameter, node in direct:
        value = _value(path, key, node, parameter.kind)
        if parameter.fanout:
            shared.extend((variable, value) for variable in parameter.fanout)
        else:
            settings[parameter.variable] = value
            specific.add(parameter.variable)
    for variable, value in shared:
        if variable not in specific:
            settings[variable] = value
    if not conditions_explicit and conditions:
        settings["CONDITIONS"] = " ".join(conditions)

    definitions: dict[str, tuple[str, Node]] = {}
    for key, parameter, mapping in conditionals:
        local_seen: dict[str, Node] = {}
        for condition_node, value_node in mapping.value:
            condition = condition_node.value
            folded = condition.lower()
            if folded in local_seen:
                first = local_seen[folded].start_mark.line + 1
                raise _error(path, condition_node, f"duplicate condition {condition!r} in {key} (first defined at line {first})")
            local_seen[folded] = condition_node
            value = _value(path, f"{key}.{condition}", value_node, parameter.kind)
            variable = f"{parameter.variable}_{condition.upper()}"
            if variable in definitions:
                previous, previous_node = definitions[variable]
                if previous != value:
                    first = previous_node.start_mark.line + 1
                    raise _error(path, condition_node, f"conflicting values for condition {condition!r} in {key} (first defined at line {first})")
                continue
            definitions[variable] = (value, condition_node)
            settings[variable] = value
    return settings, conditions


def public_key(variable: str) -> str:
    direct = sorted(
        (
            (key, parameter)
            for key, parameter in PARAMETERS.items()
            if parameter.variable == variable
        ),
        key=lambda item: ("_hvg_" not in item[0], item[0]),
    )
    if direct:
        return direct[0][0]
    for key, parameter in PARAMETERS.items():
        prefix = parameter.variable + "_"
        if parameter.conditional and variable.startswith(prefix):
            return f"{key}.{variable[len(prefix):].lower()}"
    for key, parameter in PARAMETERS.items():
        if variable in parameter.fanout:
            return key
    return variable.lower()


def internal_variable(key: str) -> str:
    normalized = key.lower().replace("-", "_")
    parameter = PARAMETERS.get(normalized)
    if parameter is not None:
        if parameter.variable:
            return parameter.variable
        if len(parameter.fanout) == 1:
            return parameter.fanout[0]
    for candidate, conditional in PARAMETERS.items():
        if not conditional.conditional:
            continue
        for separator in (".", "_"):
            prefix = candidate + separator
            if normalized.startswith(prefix) and len(normalized) > len(prefix):
                return conditional.variable + "_" + normalized[len(prefix) :].upper()
    return normalized.replace(".", "_").upper()


def _initializer_parameter(name: str) -> tuple[str, str, Parameter]:
    normalized = name.lstrip("-").replace("-", "_")
    for key, parameter in PARAMETERS.items():
        if normalized.lower() == key or (
            parameter.variable and normalized.upper() == parameter.variable
        ):
            return key, "", parameter
    upper = normalized.upper()
    for key, parameter in PARAMETERS.items():
        prefix = parameter.variable + "_"
        if parameter.conditional and upper.startswith(prefix) and len(upper) > len(prefix):
            return key, normalized[len(prefix) :].lower(), parameter
    conditional = _conditional_parameter(normalized.lower())
    if conditional is not None:
        key, condition, parameter = conditional
        return key, condition.lower(), parameter
    raise ConfigurationError(f"unknown configuration initializer {normalized.lower()!r}")


def _initializer_value(value: str, kind: str):
    if value == "":
        return None
    if kind == BOOLEAN:
        lowered = value.lower()
        if lowered not in {"true", "false"}:
            raise ConfigurationError("expected true or false")
        return lowered == "true"
    if kind == INTEGER:
        try:
            return int(value)
        except ValueError as error:
            raise ConfigurationError("expected an integer") from error
    if kind == NUMBER:
        try:
            return float(value)
        except ValueError as error:
            raise ConfigurationError("expected a number") from error
    if kind == BOOLEAN_OR_NUMBER:
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        try:
            return float(value)
        except ValueError as error:
            raise ConfigurationError("expected a boolean or number") from error
    if kind in {STRING_LIST, SCALAR_LIST}:
        return value.split()
    return value


def _yaml_inline(value) -> str:
    return yaml.safe_dump(
        value,
        default_flow_style=True,
        sort_keys=False,
    ).strip().removesuffix("...").rstrip()


def scaffold(overrides: list[str]) -> None:
    values: dict[str, object] = dict(
        (
            ("organism", None),
            ("conditions", None),
            ("sra", None),
            ("gsm", None),
            ("count_files", None),
            ("macrostate_files", None),
            ("binarization_file", None),
            ("labels", []),
            ("spec_file", "spec.yml"),
        )
    )
    for assignment in overrides:
        if "=" not in assignment:
            raise ConfigurationError(f"invalid configuration initializer {assignment!r}")
        name, raw_value = assignment.split("=", 1)
        key, condition, parameter = _initializer_parameter(name)
        try:
            value = _initializer_value(raw_value, parameter.kind)
        except ConfigurationError as error:
            raise ConfigurationError(f"invalid initializer {name.lower()}: {error}") from error
        if condition:
            mapping = values.get(key)
            if not isinstance(mapping, dict):
                mapping = {}
                values[key] = mapping
            mapping[condition] = value
        else:
            values[key] = value

    comments = {
        "organism": ["Organism used for gene resources (for example, mouse or human)."],
        "conditions": [
            "Experimental conditions (for example, [ctrl, treated]).",
            "Leave null for an unlabeled single-condition project.",
        ],
        "sra": [
            "Input sources are mutually exclusive. Define one route below.",
            "Named conditions use mappings, for example:",
            "sra: {ctrl: [SRR1], treated: [SRR2]}",
        ],
        "labels": [
            "Biological labels assigned to clusters in numerical order.",
            "Required by the annotation module.",
        ],
        "spec_file": ["Boolean inference constraints and node contracts."],
    }
    print("# scBOLT project configuration")
    for index, (key, value) in enumerate(values.items()):
        if index and key in comments:
            print()
        for comment in comments.get(key, []):
            print(f"# {comment}")
        print(f"{key}: {_yaml_inline(value)}")


def specification() -> None:
    print("# scBOLT Boolean inference specification")
    print("# BoNesis observations and dynamical constraints.")
    print("constraints: []")
    print()
    print("# Nodes prioritized during gene selection.")
    print("important_nodes: []")
    print()
    print("# Nodes retained in every selected domain.")
    print("mandatory_nodes: []")
    print()
    print("# Nodes removed before gene selection.")
    print("forbidden_nodes: []")


def _mapping_lines(conditions: Iterable[str]) -> Iterable[tuple[str, str]]:
    variables: set[str] = set()
    for parameter in PARAMETERS.values():
        if parameter.variable:
            variables.add(parameter.variable)
        variables.update(parameter.fanout)
        if parameter.conditional:
            variables.update(f"{parameter.variable}_{condition.upper()}" for condition in conditions)
    for variable in sorted(variables):
        yield f"SCBOLT_PUBLIC_PARAMETER_{variable}", public_key(variable)


def export(path: Path) -> None:
    settings, conditions = load(path)
    for name, value in sorted(settings.items()):
        print(f"{name}\t{value}")
    for name, value in _mapping_lines(conditions):
        print(f"{name}\t{value}")


def print_value(path: Path, variable: str) -> None:
    settings, _ = load(path)
    print(settings.get(variable, ""))


def lookup_value(path: Path, variable: str) -> int:
    settings, _ = load(path)
    if variable not in settings:
        return 3
    print(settings[variable])
    return 0


def mappings() -> None:
    for key, parameter in sorted(PARAMETERS.items()):
        if parameter.variable:
            suffix = "\tcondition" if parameter.conditional else ""
            print(f"{key}\t{parameter.variable}{suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("path", type=Path)
    internal_parser = subparsers.add_parser("internal")
    internal_parser.add_argument("key")
    value_parser = subparsers.add_parser("value")
    value_parser.add_argument("path", type=Path)
    value_parser.add_argument("variable")
    lookup_parser = subparsers.add_parser("lookup")
    lookup_parser.add_argument("path", type=Path)
    lookup_parser.add_argument("variable")
    subparsers.add_parser("mappings")
    scaffold_parser = subparsers.add_parser("scaffold")
    scaffold_parser.add_argument("overrides", nargs="*")
    subparsers.add_parser("specification")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "export":
            export(args.path)
        elif args.command == "value":
            print_value(args.path, args.variable)
        elif args.command == "lookup":
            return lookup_value(args.path, args.variable)
        elif args.command == "internal":
            print(internal_variable(args.key))
        elif args.command == "scaffold":
            scaffold(args.overrides)
        elif args.command == "specification":
            specification()
        else:
            mappings()
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
