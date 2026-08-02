"""Validate scBOLT project YAML and expose its internal settings."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

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
    shared: bool = False
    effective_variable: str = ""


def _condition_suffix(condition: str) -> str:
    return condition.upper().replace("-", "_")


def _parameters() -> dict[str, Parameter]:
    parameters: dict[str, Parameter] = {}

    def add(key: str, variable: str, kind: str = STRING) -> None:
        parameters[key] = Parameter(variable=variable, kind=kind)

    def conditional(
        key: str,
        variable: str,
        kind: str,
        *,
        shared: bool = False,
        effective_variable: str = "",
    ) -> None:
        parameters[key] = Parameter(
            variable=variable,
            kind=kind,
            conditional=True,
            shared=shared,
            effective_variable=effective_variable,
        )

    add("backend", "BACKEND")
    add("container-image", "SCBOLT_IMAGE")
    add("container-engine", "SCBOLT_CONTAINER_ENGINE")
    add("container-args", "SCBOLT_CONTAINER_ARGS", STRING_OR_LIST)
    add("container-mounts", "SCBOLT_CONTAINER_MOUNTS", STRING_LIST)
    add("project-dir", "PROJECT_DIR")
    add("inference-dir", "INFERENCE_DIR")
    add("resources-dir", "RESOURCES_DIR")
    add("memory", "MEMORY", SCALAR)
    add("jobs", "JOBS", INTEGER)
    add("seed", "SEED", INTEGER)
    add("logging", "LOGGING", BOOLEAN)
    add("openblas-core-type", "OPENBLAS_CORETYPE")
    add("organism", "ORGANISM")
    add("conditions", "CONDITIONS", STRING_LIST)
    add("references", "REFERENCES", STRING_LIST)
    conditional("gsm", "GSM", STRING)
    conditional("sra", "SRA", STRING_OR_LIST)
    conditional(
        "count-file",
        "COUNT_FILE",
        STRING,
        effective_variable="COUNT_FILES",
    )
    conditional(
        "macrostate-file",
        "MACROSTATE_FILE",
        STRING,
        shared=True,
        effective_variable="MACROSTATE_FILES",
    )
    add("binarization-file", "BINARIZATION_FILE")
    add("representation", "REPRESENTATION")
    add("label-column", "LABEL_COL")
    add("old-files", "OLD_FILES", STRING_LIST)
    add("labels", "LABEL", STRING_LIST)
    add("spec-file", "SPEC_FILE")
    add("genome-url", "genome_url")
    add("repeat-masker-url", "repeat_msk_url")
    add("gene-ontology-url", "go_organism_url")

    add("alignment-tool", "ALIGNMENT_TOOL")
    add("star-barcode-length", "STAR_CB_LEN", INTEGER)
    add("star-umi-length", "STAR_UMI_LEN", INTEGER)
    add("star-whitelist", "STAR_WHITELIST")
    add("star-barcode-filter", "STAR_BARCODE_FILTER")
    add("star-min-umi", "STAR_MIN_UMI", INTEGER)
    add("star-top-barcodes", "STAR_TOP_BARCODES", INTEGER)

    add("gene-dropout", "GENE_DROPOUT", NUMBER)
    add("gene-expression", "GENE_EXPRESSION", SCALAR_LIST)
    add("gene-counts", "GENE_COUNTS", SCALAR_LIST)
    add("cell-dropout", "CELL_DROPOUT", NUMBER)
    add("cell-expression", "CELL_EXPRESSION", SCALAR_LIST)
    add("cell-reads", "CELL_READS", SCALAR_LIST)
    add("mad-deviation", "MAD_DEVIATION", SCALAR_LIST)
    add("consistent-mad", "CONSISTENT_MAD", BOOLEAN)
    add("mitochondrial-fraction", "MT", NUMBER)
    add("cell-cycle-correction", "CC_CORRECTION", BOOLEAN)

    add("omics-hvg-method", "OMICS_HVG_METHOD")
    add("omics-hvg-top", "OMICS_HVG_TOP", INTEGER)
    add("omics-hvg-span", "OMICS_HVG_SPAN", NUMBER)
    add("omics-hvg-bins", "OMICS_HVG_BINS", INTEGER)
    add("bin-hvg-method", "BIN_HVG_METHOD")
    add("bin-hvg-top", "BIN_HVG_TOP", INTEGER)
    add("bin-hvg-span", "BIN_HVG_SPAN", NUMBER)
    add("bin-hvg-bins", "BIN_HVG_BINS", INTEGER)
    add("bin-include-nodes", "BIN_INCLUDE_NODES", STRING_LIST)

    add("integration", "INTEGRATION")
    add("pca-dimensions", "DIM_PCA", INTEGER)
    add("embedding-dimensions", "DIM_EMBEDDING", INTEGER)
    add("centered-pca", "CENTERED_PCA", BOOLEAN)
    add("pca-only-hvg", "PCA_ONLY_HVG", BOOLEAN)
    add("neighbors", "NEIGHBORS", INTEGER)
    add("metric", "METRIC")
    add("resolution", "RESOLUTION", NUMBER)
    add("umap-min-dist", "MIN_DIST", NUMBER)
    add("umap-spread", "SPREAD", NUMBER)
    add("embedding-iterations", "EMBEDDING_N_ITER", INTEGER)

    add("dea-method", "DEA_METHOD")
    add("logfc", "LOGFC", NUMBER)
    add("correction", "CORRECTION")
    add("alpha", "ALPHA", NUMBER)
    add("moment-dimensions", "DIM_MOMENT", INTEGER)
    add("velocity-only-hvg", "VELOCITY_ONLY_HVG", BOOLEAN)
    add("velocity-mode", "SMM_MODE")
    add("potency-batch-size", "BATCH_SIZE", INTEGER)
    add("potency-smoothing-batch-size", "SMOOTH_BATCH_SIZE", INTEGER)

    add("macrostate-size", "MACROSTATE_SIZE", INTEGER)
    add("macrostate-method", "MACROSTATE_METHOD")
    add("cotan-method", "COTAN_METHOD")
    add("cotan-only-hvg", "COTAN_ONLY_HVG", BOOLEAN)
    add("cotan-max-iterations", "MAX_ITER", INTEGER)
    add("cellrank-method", "CELLRANK_METHOD")
    add("cellrank-states", "STATES", INTEGER)
    add("cellrank-initial-states", "INITIAL_STATES", INTEGER)
    add("cellrank-terminal-states", "TERMINAL_STATES", INTEGER)
    add("cellrank-stability", "CELLRANK_STABILITY", NUMBER)
    add("cellrank-alpha", "CELLRANK_ALPHA", NUMBER)

    add("stream-clustering-method", "CLUSTERING_METHOD")
    add("stream-cluster-number", "CLUSTER_NUMBER", INTEGER)
    add("stream-alpha", "ALPHA_EPG", NUMBER)
    add("stream-mu", "MU_EPG", NUMBER)
    add("stream-lambda", "LAMBDA_EPG", NUMBER)
    add("stream-extend", "EXTEND_EPG", BOOLEAN)
    add("stream-extend-mode", "EXTEND_MODE")
    add("stream-extend-parameter", "EXTEND_PARAMETER", NUMBER)
    add("stream-prune", "PRUNE_EPG", BOOLEAN)
    add("stream-collapse-parameter", "COLLAPSE_PARAMETER", BOOLEAN_OR_NUMBER)

    add("knnsc-embedding", "KNNSC_EMBEDDING")
    add("knnsc-dimensions", "KNNSC_DIMENSION", SCALAR_LIST)
    add("knnsc-neighbors", "KNNSC_NEIGHBORS", INTEGER)
    add("knnsc-min-cluster-size", "KNNSC_MIN_CLUSTER_SIZE", INTEGER)
    conditional("knnsc-centrality", "KNNSC_CENTRALITY", STRING_LIST)
    conditional("knnsc-periphery", "KNNSC_PERIPHERY", STRING_LIST)

    add("binarization-method", "BIN_METHOD")
    add("scboolseq-only-hvg", "BIN_SCBOOLSEQ_ONLY_HVG", BOOLEAN)
    add("scboolseq-openblas-threads", "SCBOOLSEQ_OPENBLAS_THREADS", SCALAR)
    add("scboolseq-omp-threads", "SCBOOLSEQ_OMP_THREADS", SCALAR)
    add("unimodal-quantile", "UNIMODAL_QUANTILE", NUMBER)
    add("zeroes-are-zeroes", "ZEROES_ARE_ZEROES", BOOLEAN)
    add("undefined-threshold", "NANS_THRESHOLD", NUMBER)
    add("bimodal-threshold", "BIMODAL_THRESHOLD", NUMBER)
    add("zero-inflated-threshold", "ZEROINF_THRESHOLD", NUMBER)
    add("unimodal-threshold", "UNIMODAL_THRESHOLD", NUMBER)
    add("binarization-dea-only-hvg", "BIN_DEA_ONLY_HVG", BOOLEAN)
    add("binarization-logfc", "BIN_LOGFC", NUMBER)
    add("binarization-correction", "BIN_CORRECTION")
    add("binarization-alpha", "BIN_ALPHA", NUMBER)

    add("prior-knowledge", "PRIOR_KNOWLEDGE")
    add("geneinfo-version", "GENEINFO_VERSION")
    add("omnipath-version", "OMNIPATH_VERSION")
    add("hcop-version", "HCOP_VERSION")
    add("dorothea-api", "DOROTHEA_API")
    add("dorothea-compatibility", "DOROTHEA_COMPATIBILITY", BOOLEAN)
    add("dorothea-levels", "DOROTHEA_LEVELS", STRING_LIST)
    add("max-clauses", "MAX_CLAUSES", INTEGER)
    add("bounded-nonreach", "BOUNDED_NONREACH", INTEGER)
    add("clause-continuation-soft", "CLAUSE_CONTINUATION_SOFT", BOOLEAN)
    add("clause-continuation-relaxed", "CLAUSE_CONTINUATION_RELAXED", BOOLEAN)
    add("clause-continuation-seed", "CLAUSE_CONTINUATION_SEED", BOOLEAN)
    add("clause-continuation-lock", "CLAUSE_CONTINUATION_LOCK", BOOLEAN)
    add("clause-bound-patience", "PATIENCE_CLAUSE_BOUND", SCALAR)
    add("domain-continuation-soft", "DOMAIN_CONTINUATION_SOFT", BOOLEAN)
    add("domain-continuation-relaxed", "DOMAIN_CONTINUATION_RELAXED", BOOLEAN)
    add("domain-continuation-seed", "DOMAIN_CONTINUATION_SEED", BOOLEAN)
    add("domain-continuation-lock", "DOMAIN_CONTINUATION_LOCK", BOOLEAN)
    add("domain-wave-patience", "PATIENCE_DOMAIN_WAVE", SCALAR)
    add("domain-wave-patience-lock", "PATIENCE_DOMAIN_WAVE_LOCK", SCALAR)
    add("minimum-domain-yield", "MIN_DOMAIN_YIELD", NUMBER)
    add("maximum-domain-refreshes", "MAX_DOMAIN_REFRESHES", INTEGER)
    add("clingo-threads", "CLINGO_THREADS", INTEGER)

    for stage in ("soft", "consts", "relaxed", "seed", "lock"):
        suffix = stage.upper()
        add(f"clingo-config-{stage}", f"CLINGO_CONFIG_{suffix}")
        add(f"clingo-mode-{stage}", f"CLINGO_MODE_{suffix}")
        add(f"clingo-strategy-{stage}", f"CLINGO_STRATEGY_{suffix}")
        add(f"timeout-{stage}", f"TIMEOUT_{suffix}", SCALAR)
    add("clingo-mode-min", "CLINGO_MODE_MIN")
    add("minimize-self-loops-constants", "MIN_SELF_LOOP_CONSTS", BOOLEAN)
    add("minimize-self-loops-inference", "MIN_SELF_LOOP_INFER", BOOLEAN)
    add("configuration-formats", "CONFIG_FORMATS", STRING_LIST)
    add("graph-formats", "GRAPH_FORMATS", STRING_LIST)
    add("inference-limit", "INFER_LIMIT", INTEGER)
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
        prefix = candidate + "-"
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
            mapping = MappingNode(
                "tag:yaml.org,2002:map",
                [(condition_node, value_node)],
            )
            conditionals.append((base, parameter, mapping))
            continue
        assert parameter is not None
        if parameter.conditional and isinstance(value_node, MappingNode):
            conditionals.append((key, parameter, value_node))
            continue
        if (
            parameter.conditional
            and not parameter.shared
            and value_node.tag != "tag:yaml.org,2002:null"
        ):
            unnamed.append((key, value_node))
        if key == "conditions":
            conditions_explicit = True
            raw = _value(path, key, value_node, STRING_LIST)
            conditions = raw.split() if raw else []
        direct.append((key, parameter, value_node))

    shared_conditionals = {
        key: node
        for key, parameter, node in direct
        if parameter.conditional
        and parameter.shared
        and node.tag != "tag:yaml.org,2002:null"
    }
    for key, _, mapping in conditionals:
        if key in shared_conditionals:
            node = mapping.value[0][0] if mapping.value else shared_conditionals[key]
            raise _error(
                path,
                node,
                f"configuration key {key!r} cannot combine a shared file "
                "with condition-specific files",
            )

    known: dict[str, str] = {}
    internal_conditions: dict[str, str] = {}
    for condition in conditions:
        _validate_condition(path, None, condition)
        folded = condition.lower()
        if folded in known:
            raise ConfigurationError(f"{path}: duplicate conditions {known[folded]!r} and {condition!r}")
        known[folded] = condition
        suffix = _condition_suffix(condition)
        if suffix in internal_conditions:
            raise ConfigurationError(
                f"{path}: condition names {internal_conditions[suffix]!r} and "
                f"{condition!r} resolve to the same internal name"
            )
        internal_conditions[suffix] = condition
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
                suffix = _condition_suffix(condition)
                if suffix in internal_conditions:
                    raise _error(
                        path,
                        condition_node,
                        f"condition names {internal_conditions[suffix]!r} and "
                        f"{condition!r} resolve to the same internal name",
                    )
                internal_conditions[suffix] = condition
                conditions.append(condition)
    if conditions and unnamed:
        key, node = unnamed[0]
        raise _error(
            path,
            node,
            f"configuration key {key!r} must be indexed by condition "
            "when named conditions are used",
        )

    settings: dict[str, str] = {}
    for key, parameter, node in direct:
        value = _value(path, key, node, parameter.kind)
        settings[parameter.variable] = value
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
                raise _error(
                    path,
                    condition_node,
                    f"duplicate condition {condition!r} in {key} "
                    f"(first defined at line {first})",
                )
            local_seen[folded] = condition_node
            value = _value(path, f"{key}.{condition}", value_node, parameter.kind)
            variable = f"{parameter.variable}_{_condition_suffix(condition)}"
            if variable in definitions:
                previous, previous_node = definitions[variable]
                if previous != value:
                    first = previous_node.start_mark.line + 1
                    raise _error(
                        path,
                        condition_node,
                        f"conflicting values for condition {condition!r} "
                        f"in {key} (first defined at line {first})",
                    )
                continue
            definitions[variable] = (value, condition_node)
            settings[variable] = value
    return settings, conditions


def public_key(variable: str) -> str:
    for key, parameter in PARAMETERS.items():
        if parameter.variable == variable:
            return key
    for key, parameter in PARAMETERS.items():
        if parameter.effective_variable == variable:
            return key
    for key, parameter in PARAMETERS.items():
        prefix = parameter.variable + "_"
        if parameter.conditional and variable.startswith(prefix):
            suffix = variable[len(prefix) :].lower().replace("_", "-")
            return f"{key}-{suffix}"
    return variable.lower().replace("_", "-")


def _initializer_parameter(name: str) -> tuple[str, str, Parameter]:
    normalized = name.lstrip("-")
    public = normalized.lower()
    for key, parameter in PARAMETERS.items():
        if public == key or (
            parameter.variable
            and normalized == normalized.upper()
            and normalized == parameter.variable
        ):
            return key, "", parameter
    upper = normalized.upper()
    for key, parameter in PARAMETERS.items():
        prefix = parameter.variable + "_"
        if parameter.conditional and upper.startswith(prefix) and len(upper) > len(prefix):
            return key, normalized[len(prefix) :].lower(), parameter
    conditional = _conditional_parameter(public)
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
    values: dict[str, object] = {
        "organism": None,
        "conditions": None,
        "sra": None,
        "gsm": None,
        "count-file": None,
        "macrostate-file": None,
        "binarization-file": None,
        "labels": [],
        "spec-file": "spec.yml",
    }
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
            "Experimental conditions (for example, [control, perturbation]).",
            "Leave null for an unlabeled single-condition project.",
        ],
        "sra": [
            "Input sources are mutually exclusive. Define one route below.",
            "Named conditions use mappings, for example:",
            "sra: {control: [SRR_control_1, SRR_control_2],",
            "      perturbation: [SRR_perturbation_1, SRR_perturbation_2]}",
        ],
        "count-file": [
            "One count AnnData file per condition.",
            "count-file: {control: control.h5ad, perturbation: perturbation.h5ad}",
        ],
        "macrostate-file": [
            "One multi-condition macrostate AnnData file, or one per condition.",
        ],
        "labels": [
            "Biological labels assigned to clusters in numerical order.",
            "Required by the annotation module.",
        ],
        "spec-file": ["Boolean inference constraints and node contracts."],
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
    print("important-nodes: []")
    print()
    print("# Nodes retained in every selected domain.")
    print("mandatory-nodes: []")
    print()
    print("# Nodes removed before gene selection.")
    print("forbidden-nodes: []")


def _mapping_lines(conditions: Iterable[str]) -> Iterable[tuple[str, str]]:
    variables: set[str] = set()
    for parameter in PARAMETERS.values():
        if parameter.variable:
            variables.add(parameter.variable)
        if parameter.effective_variable:
            variables.add(parameter.effective_variable)
        if parameter.conditional:
            variables.update(
                f"{parameter.variable}_{_condition_suffix(condition)}"
                for condition in conditions
            )
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
