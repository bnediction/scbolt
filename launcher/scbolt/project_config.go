package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"gopkg.in/yaml.v3"
)

type configurationFormat string

const (
	configurationNone   configurationFormat = ""
	configurationYAML   configurationFormat = "yaml"
	configurationLegacy configurationFormat = "make"
)

type yamlValueKind int

const (
	yamlString yamlValueKind = iota
	yamlBoolean
	yamlInteger
	yamlNumber
	yamlScalar
	yamlStringList
	yamlScalarList
	yamlStringOrList
	yamlBooleanOrNumber
)

type yamlParameter struct {
	makeVariable string
	kind         yamlValueKind
	condition    bool
	fanout       []string
}

type makeSetting struct {
	name  string
	value string
}

type conditionalSetting struct {
	key       string
	parameter yamlParameter
	node      *yaml.Node
}

type conditionalDefinition struct {
	value string
	node  *yaml.Node
}

type projectConfiguration struct {
	path       string
	settings   []makeSetting
	values     map[string]string
	conditions []string
}

var conditionNamePattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]*$`)

var yamlParameters = buildYAMLParameters()

func buildYAMLParameters() map[string]yamlParameter {
	parameters := make(map[string]yamlParameter)
	add := func(key string, variable string, kind yamlValueKind) {
		parameters[key] = yamlParameter{makeVariable: variable, kind: kind}
	}
	addCondition := func(key string, variable string, kind yamlValueKind) {
		parameters[key] = yamlParameter{
			makeVariable: variable,
			kind:         kind,
			condition:    true,
		}
	}
	addFanout := func(key string, kind yamlValueKind, variables ...string) {
		parameters[key] = yamlParameter{kind: kind, fanout: variables}
	}

	add("backend", "BACKEND", yamlString)
	add("container_image", "SCBOLT_IMAGE", yamlString)
	add("container_engine", "SCBOLT_CONTAINER_ENGINE", yamlString)
	add("container_args", "SCBOLT_CONTAINER_ARGS", yamlStringOrList)
	add("container_mounts", "SCBOLT_CONTAINER_MOUNTS", yamlStringList)
	add("project_dir", "PROJECT_DIR", yamlString)
	add("inference_dir", "INFERENCE_DIR", yamlString)
	add("resources_dir", "RESOURCES_DIR", yamlString)
	add("memory", "MEMORY", yamlScalar)
	add("jobs", "JOBS", yamlInteger)
	add("seed", "SEED", yamlInteger)
	add("logging", "LOGGING", yamlBoolean)
	add("openblas_core_type", "OPENBLAS_CORETYPE", yamlString)
	add("organism", "ORGANISM", yamlString)
	add("conditions", "CONDITIONS", yamlStringList)
	add("references", "REFERENCES", yamlStringList)
	addCondition("gsm", "GSM", yamlString)
	addCondition("sra", "SRA", yamlStringOrList)
	add("count_files", "COUNT_FILES", yamlStringList)
	add("macrostate_files", "MACROSTATE_FILES", yamlStringList)
	add("binarization_file", "BINARIZATION_FILE", yamlString)
	add("representation", "REPRESENTATION", yamlString)
	add("label_column", "LABEL_COL", yamlString)
	add("old_files", "OLD_FILES", yamlStringList)
	add("labels", "LABEL", yamlStringList)
	add("spec_file", "SPEC_FILE", yamlString)
	add("genome_url", "genome_url", yamlString)
	add("repeat_masker_url", "repeat_msk_url", yamlString)
	add("gene_ontology_url", "go_organism_url", yamlString)

	add("alignment_tool", "ALIGNMENT_TOOL", yamlString)
	add("star_barcode_length", "STAR_CB_LEN", yamlInteger)
	add("star_umi_length", "STAR_UMI_LEN", yamlInteger)
	add("star_whitelist", "STAR_WHITELIST", yamlString)
	add("star_barcode_filter", "STAR_BARCODE_FILTER", yamlString)
	add("star_min_umi", "STAR_MIN_UMI", yamlInteger)
	add("star_top_barcodes", "STAR_TOP_BARCODES", yamlInteger)

	add("gene_dropout", "GENE_DROPOUT", yamlNumber)
	add("gene_expression", "GENE_EXPRESSION", yamlScalarList)
	add("gene_counts", "GENE_COUNTS", yamlScalarList)
	add("cell_dropout", "CELL_DROPOUT", yamlNumber)
	add("cell_expression", "CELL_EXPRESSION", yamlScalarList)
	add("cell_reads", "CELL_READS", yamlScalarList)
	add("mad_deviation", "MAD_DEVIATION", yamlScalarList)
	add("consistent_mad", "CONSISTENT_MAD", yamlBoolean)
	add("mitochondrial_fraction", "MT", yamlNumber)
	add("cell_cycle_correction", "CC_CORRECTION", yamlBoolean)

	addFanout("hvg_method", yamlString, "ANALYSIS_HVG_METHOD", "BIN_HVG_METHOD")
	addFanout("hvg_top", yamlInteger, "ANALYSIS_HVG_TOP", "BIN_HVG_TOP")
	addFanout("hvg_span", yamlNumber, "ANALYSIS_HVG_SPAN", "BIN_HVG_SPAN")
	addFanout("hvg_bins", yamlInteger, "ANALYSIS_HVG_BINS", "BIN_HVG_BINS")
	add("analysis_hvg_method", "ANALYSIS_HVG_METHOD", yamlString)
	add("analysis_hvg_top", "ANALYSIS_HVG_TOP", yamlInteger)
	add("analysis_hvg_span", "ANALYSIS_HVG_SPAN", yamlNumber)
	add("analysis_hvg_bins", "ANALYSIS_HVG_BINS", yamlInteger)
	add("binarization_hvg_method", "BIN_HVG_METHOD", yamlString)
	add("binarization_hvg_top", "BIN_HVG_TOP", yamlInteger)
	add("binarization_hvg_span", "BIN_HVG_SPAN", yamlNumber)
	add("binarization_hvg_bins", "BIN_HVG_BINS", yamlInteger)
	add("binarization_include_nodes", "BIN_INCLUDE_NODES", yamlStringList)

	add("integration", "INTEGRATION", yamlString)
	add("pca_dimensions", "DIM_PCA", yamlInteger)
	add("embedding_dimensions", "DIM_EMBEDDING", yamlInteger)
	add("centered_pca", "CENTERED_PCA", yamlBoolean)
	add("pca_only_hvg", "PCA_ONLY_HVG", yamlBoolean)
	add("neighbors", "NEIGHBORS", yamlInteger)
	add("metric", "METRIC", yamlString)
	add("resolution", "RESOLUTION", yamlNumber)
	add("umap_min_dist", "MIN_DIST", yamlNumber)
	add("umap_spread", "SPREAD", yamlNumber)
	add("embedding_iterations", "EMBEDDING_N_ITER", yamlInteger)

	add("dea_method", "DEA_METHOD", yamlString)
	add("logfc", "LOGFC", yamlNumber)
	add("correction", "CORRECTION", yamlString)
	add("alpha", "ALPHA", yamlNumber)
	add("moment_dimensions", "DIM_MOMENT", yamlInteger)
	add("velocity_only_hvg", "VELOCITY_ONLY_HVG", yamlBoolean)
	add("velocity_mode", "SMM_MODE", yamlString)
	add("potency_batch_size", "BATCH_SIZE", yamlInteger)
	add("potency_smoothing_batch_size", "SMOOTH_BATCH_SIZE", yamlInteger)

	add("macrostate_size", "MACROSTATE_SIZE", yamlInteger)
	add("macrostate_method", "MACROSTATE_METHOD", yamlString)
	add("cotan_method", "COTAN_METHOD", yamlString)
	add("cotan_only_hvg", "COTAN_ONLY_HVG", yamlBoolean)
	add("cotan_max_iterations", "MAX_ITER", yamlInteger)
	add("cellrank_method", "CELLRANK_METHOD", yamlString)
	add("cellrank_states", "STATES", yamlInteger)
	add("cellrank_initial_states", "INITIAL_STATES", yamlInteger)
	add("cellrank_terminal_states", "TERMINAL_STATES", yamlInteger)
	add("cellrank_stability", "CELLRANK_STABILITY", yamlNumber)
	add("cellrank_alpha", "CELLRANK_ALPHA", yamlNumber)

	add("stream_clustering_method", "CLUSTERING_METHOD", yamlString)
	add("stream_cluster_number", "CLUSTER_NUMBER", yamlInteger)
	add("stream_alpha", "ALPHA_EPG", yamlNumber)
	add("stream_mu", "MU_EPG", yamlNumber)
	add("stream_lambda", "LAMBDA_EPG", yamlNumber)
	add("stream_extend", "EXTEND_EPG", yamlBoolean)
	add("stream_extend_mode", "EXTEND_MODE", yamlString)
	add("stream_extend_parameter", "EXTEND_PARAMETER", yamlNumber)
	add("stream_prune", "PRUNE_EPG", yamlBoolean)
	add("stream_collapse_parameter", "COLLAPSE_PARAMETER", yamlBooleanOrNumber)

	add("knnsc_embedding", "KNNSC_EMBEDDING", yamlString)
	add("knnsc_dimensions", "KNNSC_DIMENSION", yamlScalarList)
	add("knnsc_neighbors", "KNNSC_NEIGHBORS", yamlInteger)
	add("knnsc_min_cluster_size", "KNNSC_MIN_CLUSTER_SIZE", yamlInteger)
	addCondition("knnsc_centrality", "KNNSC_CENTRALITY", yamlStringList)
	addCondition("knnsc_periphery", "KNNSC_PERIPHERY", yamlStringList)

	add("binarization_method", "BIN_METHOD", yamlString)
	add("scboolseq_only_hvg", "BIN_SCBOOLSEQ_ONLY_HVG", yamlBoolean)
	add("scboolseq_openblas_threads", "SCBOOLSEQ_OPENBLAS_THREADS", yamlScalar)
	add("scboolseq_omp_threads", "SCBOOLSEQ_OMP_THREADS", yamlScalar)
	add("unimodal_quantile", "UNIMODAL_QUANTILE", yamlNumber)
	add("zeroes_are_zeroes", "ZEROES_ARE_ZEROES", yamlBoolean)
	add("undefined_threshold", "NANS_THRESHOLD", yamlNumber)
	add("bimodal_threshold", "BIMODAL_THRESHOLD", yamlNumber)
	add("zero_inflated_threshold", "ZEROINF_THRESHOLD", yamlNumber)
	add("unimodal_threshold", "UNIMODAL_THRESHOLD", yamlNumber)
	add("binarization_dea_only_hvg", "BIN_DEA_ONLY_HVG", yamlBoolean)
	add("binarization_logfc", "BIN_LOGFC", yamlNumber)
	add("binarization_correction", "BIN_CORRECTION", yamlString)
	add("binarization_alpha", "BIN_ALPHA", yamlNumber)

	add("prior_knowledge", "PRIOR_KNOWLEDGE", yamlString)
	add("geneinfo_version", "GENEINFO_VERSION", yamlString)
	add("omnipath_version", "OMNIPATH_VERSION", yamlString)
	add("hcop_version", "HCOP_VERSION", yamlString)
	add("dorothea_api", "DOROTHEA_API", yamlString)
	add("dorothea_compatibility", "DOROTHEA_COMPATIBILITY", yamlBoolean)
	add("dorothea_levels", "DOROTHEA_LEVELS", yamlStringList)
	add("max_clauses", "MAX_CLAUSES", yamlInteger)
	add("clause_continuation_soft", "CLAUSE_CONTINUATION_SOFT", yamlBoolean)
	add("clause_continuation_relaxed", "CLAUSE_CONTINUATION_RELAXED", yamlBoolean)
	add("clause_continuation_seed", "CLAUSE_CONTINUATION_SEED", yamlBoolean)
	add("clause_continuation_lock", "CLAUSE_CONTINUATION_LOCK", yamlBoolean)
	add("clause_bound_patience", "PATIENCE_CLAUSE_BOUND", yamlScalar)
	add("domain_continuation_soft", "DOMAIN_CONTINUATION_SOFT", yamlBoolean)
	add("domain_continuation_relaxed", "DOMAIN_CONTINUATION_RELAXED", yamlBoolean)
	add("domain_continuation_seed", "DOMAIN_CONTINUATION_SEED", yamlBoolean)
	add("domain_continuation_lock", "DOMAIN_CONTINUATION_LOCK", yamlBoolean)
	add("domain_wave_patience", "PATIENCE_DOMAIN_WAVE", yamlScalar)
	add("minimum_domain_yield", "MIN_DOMAIN_YIELD", yamlNumber)
	add("maximum_domain_refreshes", "MAX_DOMAIN_REFRESHES", yamlInteger)
	add("clingo_threads", "CLINGO_THREADS", yamlInteger)

	for _, stage := range []string{"soft", "consts", "relaxed", "seed", "lock"} {
		upper := strings.ToUpper(stage)
		add("clingo_config_"+stage, "CLINGO_CONFIG_"+upper, yamlString)
		add("clingo_mode_"+stage, "CLINGO_MODE_"+upper, yamlString)
		add("clingo_strategy_"+stage, "CLINGO_STRATEGY_"+upper, yamlString)
		add("timeout_"+stage, "TIMEOUT_"+upper, yamlScalar)
	}
	add("clingo_mode_min", "CLINGO_MODE_MIN", yamlString)
	add("minimize_self_loops_constants", "MIN_SELF_LOOP_CONSTS", yamlBoolean)
	add("minimize_self_loops_inference", "MIN_SELF_LOOP_INFER", yamlBoolean)
	add("configuration_formats", "CONFIG_FORMATS", yamlStringList)
	add("graph_formats", "GRAPH_FORMATS", yamlStringList)
	add("inference_limit", "INFER_LIMIT", yamlInteger)
	return parameters
}

func configurationFormatForPath(path string) configurationFormat {
	switch strings.ToLower(filepath.Ext(path)) {
	case ".yml", ".yaml":
		return configurationYAML
	case ".mk":
		return configurationLegacy
	default:
		return configurationNone
	}
}

func publicConfigurationKey(variable string) string {
	for key, parameter := range yamlParameters {
		if parameter.makeVariable == variable {
			return key
		}
	}
	for key, parameter := range yamlParameters {
		if !parameter.condition {
			continue
		}
		prefix := parameter.makeVariable + "_"
		if strings.HasPrefix(variable, prefix) {
			return key + "." + strings.ToLower(strings.TrimPrefix(variable, prefix))
		}
	}
	for key, parameter := range yamlParameters {
		if containsString(parameter.fanout, variable) {
			return key
		}
	}
	return strings.ToLower(variable)
}

func internalConfigurationVariable(publicName string) string {
	key := strings.ToLower(strings.ReplaceAll(publicName, "-", "_"))
	if parameter, found := yamlParameters[key]; found {
		if parameter.makeVariable != "" {
			return parameter.makeVariable
		}
		if len(parameter.fanout) == 1 {
			return parameter.fanout[0]
		}
	}
	for candidate, parameter := range yamlParameters {
		if !parameter.condition {
			continue
		}
		for _, separator := range []string{".", "_"} {
			prefix := candidate + separator
			if strings.HasPrefix(key, prefix) {
				condition := strings.TrimPrefix(key, prefix)
				return parameter.makeVariable + "_" + strings.ToUpper(condition)
			}
		}
	}
	return strings.ToUpper(strings.ReplaceAll(key, ".", "_"))
}

func loadProjectConfiguration(path string) (*projectConfiguration, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	decoder := yaml.NewDecoder(file)
	var document yaml.Node
	if err := decoder.Decode(&document); err != nil {
		return nil, configurationError(path, nil, err.Error())
	}
	var extra yaml.Node
	if err := decoder.Decode(&extra); err != io.EOF {
		if err == nil {
			return nil, configurationError(path, &extra, "multiple YAML documents are not supported")
		}
		return nil, configurationError(path, &extra, err.Error())
	}

	configuration := &projectConfiguration{
		path:   path,
		values: make(map[string]string),
	}
	if len(document.Content) == 0 || document.Content[0].Tag == "!!null" {
		return configuration, nil
	}
	root := document.Content[0]
	if root.Kind != yaml.MappingNode {
		return nil, configurationError(path, root, "configuration must be a YAML mapping")
	}

	seen := make(map[string]*yaml.Node)
	conditionals := make([]conditionalSetting, 0)
	unnamedConditionValues := make([]conditionalSetting, 0)
	specificVariables := make(map[string]bool)
	sharedSettings := make([]makeSetting, 0)
	directSettings := make([]makeSetting, 0)
	conditionsExplicit := false
	for index := 0; index < len(root.Content); index += 2 {
		keyNode := root.Content[index]
		valueNode := root.Content[index+1]
		if keyNode.Kind != yaml.ScalarNode || keyNode.Tag != "!!str" {
			return nil, configurationError(path, keyNode, "configuration keys must be strings")
		}
		key := keyNode.Value
		if previous, found := seen[key]; found {
			return nil, configurationError(
				path,
				keyNode,
				fmt.Sprintf("duplicate configuration key %q (first defined at line %d)", key, previous.Line),
			)
		}
		seen[key] = keyNode

		parameter, found := yamlParameters[key]
		conditionalKey := ""
		condition := ""
		if !found {
			conditionalKey, condition, parameter, found = conditionalParameterForKey(key)
		}
		if !found {
			return nil, configurationError(path, keyNode, fmt.Sprintf("unknown configuration key %q", key))
		}
		if condition != "" {
			conditionNode := &yaml.Node{
				Kind:   yaml.ScalarNode,
				Tag:    "!!str",
				Value:  condition,
				Line:   keyNode.Line,
				Column: keyNode.Column + len(conditionalKey) + 1,
			}
			conditionals = append(conditionals, conditionalSetting{
				key:       conditionalKey,
				parameter: parameter,
				node: &yaml.Node{
					Kind:    yaml.MappingNode,
					Tag:     "!!map",
					Content: []*yaml.Node{conditionNode, valueNode},
				},
			})
			continue
		}
		if parameter.condition && valueNode.Kind == yaml.MappingNode {
			conditionals = append(conditionals, conditionalSetting{key, parameter, valueNode})
			continue
		}
		if parameter.condition && valueNode.Tag != "!!null" {
			unnamedConditionValues = append(
				unnamedConditionValues,
				conditionalSetting{key, parameter, valueNode},
			)
		}
		value, err := yamlMakeValue(path, key, valueNode, parameter.kind)
		if err != nil {
			return nil, err
		}
		if key == "conditions" {
			conditionsExplicit = true
			configuration.conditions, err = yamlStringValues(path, key, valueNode)
			if err != nil {
				return nil, err
			}
		}
		if len(parameter.fanout) > 0 {
			for _, variable := range parameter.fanout {
				sharedSettings = append(sharedSettings, makeSetting{variable, value})
			}
			continue
		}
		specificVariables[parameter.makeVariable] = true
		directSettings = append(directSettings, makeSetting{parameter.makeVariable, value})
	}

	if err := configuration.validateConditions(path, conditionals, conditionsExplicit); err != nil {
		return nil, err
	}
	if len(configuration.conditions) > 0 && len(unnamedConditionValues) > 0 {
		setting := unnamedConditionValues[0]
		return nil, configurationError(
			path,
			setting.node,
			fmt.Sprintf(
				"configuration key %q must be indexed by condition when named conditions are used",
				setting.key,
			),
		)
	}
	for _, setting := range sharedSettings {
		if !specificVariables[setting.name] {
			configuration.add(setting.name, setting.value)
		}
	}
	for _, setting := range directSettings {
		configuration.add(setting.name, setting.value)
	}
	conditionalDefinitions := make(map[string]conditionalDefinition)
	for _, conditional := range conditionals {
		if err := configuration.addConditional(
			path,
			conditional,
			conditionalDefinitions,
		); err != nil {
			return nil, err
		}
	}
	return configuration, nil
}

func conditionalParameterForKey(
	key string,
) (string, string, yamlParameter, bool) {
	matchedKey := ""
	condition := ""
	parameter := yamlParameter{}
	for candidate, candidateParameter := range yamlParameters {
		if !candidateParameter.condition {
			continue
		}
		prefix := candidate + "_"
		if !strings.HasPrefix(key, prefix) || len(candidate) <= len(matchedKey) {
			continue
		}
		candidateCondition := strings.TrimPrefix(key, prefix)
		if candidateCondition == "" {
			continue
		}
		matchedKey = candidate
		condition = candidateCondition
		parameter = candidateParameter
	}
	return matchedKey, condition, parameter, matchedKey != ""
}

func configurationConditionNames(
	path string,
	format configurationFormat,
	configuration *projectConfiguration,
) []string {
	if configuration != nil {
		return append([]string{}, configuration.conditions...)
	}
	if format == configurationLegacy && path != "" {
		return strings.Fields(readConfigVariable(path, "CONDITIONS"))
	}
	return nil
}

func specificationKeys() []string {
	return []string{
		"constraints",
		"important_nodes",
		"mandatory_nodes",
		"forbidden_nodes",
	}
}

func (configuration *projectConfiguration) validateConditions(
	path string,
	conditionals []conditionalSetting,
	explicit bool,
) error {
	known := make(map[string]string)
	for _, condition := range configuration.conditions {
		if err := validateConditionName(path, nil, condition); err != nil {
			return err
		}
		folded := strings.ToLower(condition)
		if previous, found := known[folded]; found {
			return fmt.Errorf(
				"%s: duplicate conditions %q and %q",
				path,
				previous,
				condition,
			)
		}
		known[folded] = condition
	}

	for _, conditional := range conditionals {
		for index := 0; index < len(conditional.node.Content); index += 2 {
			conditionNode := conditional.node.Content[index]
			if conditionNode.Kind != yaml.ScalarNode || conditionNode.Tag != "!!str" {
				return configurationError(path, conditionNode, conditional.key+" condition names must be strings")
			}
			condition := conditionNode.Value
			if err := validateConditionName(path, conditionNode, condition); err != nil {
				return err
			}
			folded := strings.ToLower(condition)
			if _, found := known[folded]; found {
				continue
			}
			if explicit {
				return configurationError(
					path,
					conditionNode,
					fmt.Sprintf("condition %q in %s is not listed in conditions", condition, conditional.key),
				)
			}
			known[folded] = condition
			configuration.conditions = append(configuration.conditions, condition)
		}
	}
	if !explicit && len(configuration.conditions) > 0 {
		configuration.add("CONDITIONS", strings.Join(configuration.conditions, " "))
	}
	return nil
}

func validateConditionName(path string, node *yaml.Node, condition string) error {
	if !conditionNamePattern.MatchString(condition) {
		return configurationError(path, node, fmt.Sprintf("invalid condition name %q", condition))
	}
	switch strings.ToLower(condition) {
	case "integrated", "unique":
		return configurationError(path, node, fmt.Sprintf("reserved condition name %q", condition))
	default:
		return nil
	}
}

func (configuration *projectConfiguration) addConditional(
	path string,
	conditional conditionalSetting,
	definitions map[string]conditionalDefinition,
) error {
	seen := make(map[string]*yaml.Node)
	for index := 0; index < len(conditional.node.Content); index += 2 {
		conditionNode := conditional.node.Content[index]
		valueNode := conditional.node.Content[index+1]
		condition := conditionNode.Value
		folded := strings.ToLower(condition)
		if previous, found := seen[folded]; found {
			return configurationError(
				path,
				conditionNode,
				fmt.Sprintf("duplicate condition %q in %s (first defined at line %d)", condition, conditional.key, previous.Line),
			)
		}
		seen[folded] = conditionNode
		value, err := yamlMakeValue(path, conditional.key+"."+condition, valueNode, conditional.parameter.kind)
		if err != nil {
			return err
		}
		variable := conditional.parameter.makeVariable + "_" + strings.ToUpper(condition)
		if previous, found := definitions[variable]; found {
			if previous.value != value {
				return configurationError(
					path,
					conditionNode,
					fmt.Sprintf(
						"conflicting values for condition %q in %s (first defined at line %d)",
						condition,
						conditional.key,
						previous.node.Line,
					),
				)
			}
			continue
		}
		definitions[variable] = conditionalDefinition{
			value: value,
			node:  conditionNode,
		}
		configuration.add(variable, value)
	}
	return nil
}

func (configuration *projectConfiguration) add(name string, value string) {
	for index := range configuration.settings {
		if configuration.settings[index].name == name {
			configuration.settings[index].value = value
			configuration.values[name] = value
			return
		}
	}
	configuration.settings = append(configuration.settings, makeSetting{name, value})
	configuration.values[name] = value
}

func (configuration *projectConfiguration) Value(name string) string {
	if configuration == nil {
		return ""
	}
	return configuration.values[name]
}

func (configuration *projectConfiguration) Lookup(name string) (string, bool) {
	if configuration == nil {
		return "", false
	}
	value, found := configuration.values[name]
	return value, found
}

func (configuration *projectConfiguration) Environment() []makeSetting {
	if configuration == nil {
		return nil
	}
	settings := append([]makeSetting{}, configuration.settings...)
	sort.SliceStable(settings, func(left int, right int) bool {
		return settings[left].name < settings[right].name
	})
	return settings
}

func yamlMakeValue(path string, key string, node *yaml.Node, kind yamlValueKind) (string, error) {
	if node.Tag == "!!null" {
		return "", nil
	}
	switch kind {
	case yamlString:
		if !isYAMLString(node) {
			return "", yamlTypeError(path, key, node, "a string")
		}
		return validateMakeScalar(path, key, node)
	case yamlBoolean:
		if node.Kind != yaml.ScalarNode || node.Tag != "!!bool" {
			return "", yamlTypeError(path, key, node, "a boolean")
		}
		value, _ := strconv.ParseBool(node.Value)
		return strconv.FormatBool(value), nil
	case yamlInteger:
		if node.Kind != yaml.ScalarNode || node.Tag != "!!int" {
			return "", yamlTypeError(path, key, node, "an integer or null")
		}
		return node.Value, nil
	case yamlNumber:
		if node.Kind != yaml.ScalarNode || (node.Tag != "!!int" && node.Tag != "!!float") {
			return "", yamlTypeError(path, key, node, "a number or null")
		}
		return node.Value, nil
	case yamlScalar:
		if node.Kind != yaml.ScalarNode || node.Tag == "!!bool" {
			return "", yamlTypeError(path, key, node, "a string or number")
		}
		return validateMakeScalar(path, key, node)
	case yamlStringList, yamlScalarList:
		return yamlListValue(path, key, node, kind)
	case yamlStringOrList:
		if node.Kind == yaml.SequenceNode {
			return yamlListValue(path, key, node, yamlStringList)
		}
		if !isYAMLString(node) {
			return "", yamlTypeError(path, key, node, "a string, list of strings, or null")
		}
		return validateMakeScalar(path, key, node)
	case yamlBooleanOrNumber:
		if node.Kind != yaml.ScalarNode ||
			(node.Tag != "!!bool" && node.Tag != "!!int" && node.Tag != "!!float") {
			return "", yamlTypeError(path, key, node, "a boolean, number, or null")
		}
		if node.Tag == "!!bool" {
			value, _ := strconv.ParseBool(node.Value)
			return strconv.FormatBool(value), nil
		}
		return node.Value, nil
	default:
		return "", errors.New("unsupported YAML parameter type")
	}
}

func yamlListValue(path string, key string, node *yaml.Node, kind yamlValueKind) (string, error) {
	if node.Tag == "!!null" {
		return "", nil
	}
	if node.Kind != yaml.SequenceNode {
		return "", yamlTypeError(path, key, node, "a list or null")
	}
	values := make([]string, 0, len(node.Content))
	for _, item := range node.Content {
		if kind == yamlStringList || kind == yamlString {
			if !isYAMLString(item) {
				return "", yamlTypeError(path, key, item, "a list containing only strings")
			}
		} else if item.Kind != yaml.ScalarNode || item.Tag == "!!bool" || item.Tag == "!!null" {
			return "", yamlTypeError(path, key, item, "a list containing only strings or numbers")
		}
		value, err := validateMakeScalar(path, key, item)
		if err != nil {
			return "", err
		}
		values = append(values, value)
	}
	return strings.Join(values, " "), nil
}

func yamlStringValues(path string, key string, node *yaml.Node) ([]string, error) {
	if node.Tag == "!!null" {
		return nil, nil
	}
	if node.Kind != yaml.SequenceNode {
		return nil, yamlTypeError(path, key, node, "a list of strings or null")
	}
	values := make([]string, 0, len(node.Content))
	for _, item := range node.Content {
		if !isYAMLString(item) {
			return nil, yamlTypeError(path, key, item, "a list containing only strings")
		}
		value, err := validateMakeScalar(path, key, item)
		if err != nil {
			return nil, err
		}
		values = append(values, value)
	}
	return values, nil
}

func isYAMLString(node *yaml.Node) bool {
	return node.Kind == yaml.ScalarNode && (node.Tag == "!!str" || node.Tag == "!!timestamp")
}

func validateMakeScalar(path string, key string, node *yaml.Node) (string, error) {
	if strings.ContainsAny(node.Value, "\r\n\x00") {
		return "", configurationError(path, node, fmt.Sprintf("configuration value %q must be a single line", key))
	}
	return node.Value, nil
}

func yamlTypeError(path string, key string, node *yaml.Node, expected string) error {
	return configurationError(path, node, fmt.Sprintf("configuration key %q must be %s", key, expected))
}

func configurationError(path string, node *yaml.Node, message string) error {
	location := path
	if node != nil && node.Line > 0 {
		location += fmt.Sprintf(":%d:%d", node.Line, node.Column)
	}
	return fmt.Errorf("%s: %s", location, message)
}

func minimalYAMLContent(overrides []initOverride) (string, error) {
	root := &yaml.Node{Kind: yaml.MappingNode, Tag: "!!map"}
	null := func() *yaml.Node {
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!null", Value: "null"}
	}
	list := func() *yaml.Node {
		return &yaml.Node{Kind: yaml.SequenceNode, Tag: "!!seq"}
	}
	text := func(value string) *yaml.Node {
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!str", Value: value}
	}

	setYAMLMappingValue(root, "organism", null())
	setYAMLMappingComment(
		root,
		"organism",
		"Organism used for gene resources (for example, mouse or human).",
	)
	setYAMLMappingValue(root, "conditions", null())
	setYAMLMappingComment(
		root,
		"conditions",
		"Experimental conditions (for example, [ctrl, treated]).\n"+
			"Leave null for an unlabeled single-condition project.",
	)

	setYAMLMappingValue(root, "sra", null())
	setYAMLMappingComment(
		root,
		"sra",
		"Input sources are mutually exclusive. Define one route below.\n"+
			"Named conditions use mappings, for example sra: {ctrl: [SRR1], treated: [SRR2]}.",
	)
	setYAMLMappingValue(root, "gsm", null())
	setYAMLMappingValue(root, "count_files", null())
	setYAMLMappingValue(root, "macrostate_files", null())
	setYAMLMappingValue(root, "binarization_file", null())

	setYAMLMappingValue(root, "labels", list())
	setYAMLMappingComment(
		root,
		"labels",
		"Biological labels assigned to clusters in numerical order.\n"+
			"Required by the annotation module.",
	)
	setYAMLMappingValue(root, "spec_file", text("spec.yml"))
	setYAMLMappingComment(
		root,
		"spec_file",
		"Boolean inference constraints and node contracts.",
	)
	conditionMappings := make(map[string]*yaml.Node)
	for _, override := range overrides {
		key, condition, parameter, found := yamlInitializerParameter(override.name)
		if !found {
			return "", fmt.Errorf(
				"unknown configuration initializer %q",
				strings.ToLower(override.name),
			)
		}
		value, err := yamlInitializerNode(override.value, parameter.kind)
		if err != nil {
			return "", fmt.Errorf("invalid initializer %s: %w", strings.ToLower(override.name), err)
		}
		if condition == "" {
			setYAMLMappingValue(root, key, value)
			continue
		}
		mapping := conditionMappings[key]
		if mapping == nil {
			mapping = &yaml.Node{Kind: yaml.MappingNode, Tag: "!!map"}
			conditionMappings[key] = mapping
		}
		setYAMLMappingValue(mapping, strings.ToLower(condition), value)
		setYAMLMappingValue(root, key, mapping)
	}
	encoded, err := yaml.Marshal(root)
	if err != nil {
		return "", err
	}
	return "# scBOLT project configuration\n" + string(encoded), nil
}

func minimalSpecificationContent() (string, error) {
	root := &yaml.Node{Kind: yaml.MappingNode, Tag: "!!map"}
	comments := map[string]string{
		"constraints":     "BoNesis observations and dynamical constraints.",
		"important_nodes": "Nodes prioritized during gene selection.",
		"mandatory_nodes": "Nodes retained in every selected domain.",
		"forbidden_nodes": "Nodes removed before gene selection.",
	}
	for _, key := range specificationKeys() {
		setYAMLMappingValue(
			root,
			key,
			&yaml.Node{Kind: yaml.SequenceNode, Tag: "!!seq"},
		)
		setYAMLMappingComment(root, key, comments[key])
	}
	encoded, err := yaml.Marshal(root)
	if err != nil {
		return "", err
	}
	return "# scBOLT Boolean inference specification\n" + string(encoded), nil
}

func yamlInitializerParameter(
	name string,
) (string, string, yamlParameter, bool) {
	for key, parameter := range yamlParameters {
		if strings.EqualFold(name, key) ||
			(parameter.makeVariable != "" && strings.EqualFold(name, parameter.makeVariable)) {
			return key, "", parameter, true
		}
	}
	for key, parameter := range yamlParameters {
		if !parameter.condition {
			continue
		}
		prefix := parameter.makeVariable + "_"
		if strings.HasPrefix(strings.ToUpper(name), prefix) {
			return key, name[len(prefix):], parameter, true
		}
	}
	return "", "", yamlParameter{}, false
}

func yamlInitializerNode(value string, kind yamlValueKind) (*yaml.Node, error) {
	if value == "" {
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!null", Value: "null"}, nil
	}
	scalar := func(tag string, scalarValue string) *yaml.Node {
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: tag, Value: scalarValue}
	}
	switch kind {
	case yamlBoolean:
		parsed, err := strconv.ParseBool(strings.ToLower(value))
		if err != nil {
			return nil, errors.New("expected true or false")
		}
		return scalar("!!bool", strconv.FormatBool(parsed)), nil
	case yamlInteger:
		if _, err := strconv.ParseInt(value, 10, 64); err != nil {
			return nil, errors.New("expected an integer")
		}
		return scalar("!!int", value), nil
	case yamlNumber:
		if _, err := strconv.ParseFloat(value, 64); err != nil {
			return nil, errors.New("expected a number")
		}
		return scalar("!!float", value), nil
	case yamlBooleanOrNumber:
		if parsed, err := strconv.ParseBool(strings.ToLower(value)); err == nil {
			return scalar("!!bool", strconv.FormatBool(parsed)), nil
		}
		if _, err := strconv.ParseFloat(value, 64); err != nil {
			return nil, errors.New("expected a boolean or number")
		}
		return scalar("!!float", value), nil
	case yamlStringList, yamlScalarList:
		sequence := &yaml.Node{Kind: yaml.SequenceNode, Tag: "!!seq"}
		for _, item := range strings.Fields(value) {
			sequence.Content = append(sequence.Content, scalar("!!str", item))
		}
		return sequence, nil
	case yamlStringOrList:
		return scalar("!!str", value), nil
	default:
		return scalar("!!str", value), nil
	}
}

func setYAMLMappingValue(mapping *yaml.Node, key string, value *yaml.Node) {
	for index := 0; index < len(mapping.Content); index += 2 {
		if mapping.Content[index].Value == key {
			mapping.Content[index+1] = value
			return
		}
	}
	mapping.Content = append(
		mapping.Content,
		&yaml.Node{Kind: yaml.ScalarNode, Tag: "!!str", Value: key},
		value,
	)
}

func setYAMLMappingComment(mapping *yaml.Node, key string, comment string) {
	for index := 0; index < len(mapping.Content); index += 2 {
		if mapping.Content[index].Value == key {
			mapping.Content[index].HeadComment = comment
			return
		}
	}
}
