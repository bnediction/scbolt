package main

import (
	"bufio"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

type reportedError struct {
	status int
}

func (err *reportedError) Error() string {
	return "error already reported"
}

type initOverride struct {
	name  string
	value string
}

type initRequest struct {
	remove        bool
	show          bool
	configuration string
	positionals   []string
	overrides     []initOverride
	backend       string
	backendGiven  bool
}

var initVariablePattern = regexp.MustCompile(`^[A-Z_][A-Z0-9_]*$`)

const defaultProjectConfigurationFile = "scbolt.yml"

func runInit(cfg config, arguments []string) error {
	request, err := parseInitRequest(cfg, arguments)
	if err != nil {
		return err
	}
	if request.remove {
		return removeProjectConfiguration()
	}
	if request.show {
		return showProjectConfiguration()
	}
	return initializeProject(request)
}

func parseInitRequest(cfg config, arguments []string) (initRequest, error) {
	request := initRequest{backend: cfg.backend}
	commandIndex := -1
	for index, argument := range arguments {
		if argument == "init" {
			commandIndex = index
			break
		}
	}
	if commandIndex < 0 {
		return request, errors.New("missing init command")
	}
	args := append([]string{}, arguments[:commandIndex]...)
	args = append(args, arguments[commandIndex+1:]...)
	if hasHelpRequest(args) {
		printInitHelp()
		return request, &reportedError{status: 0}
	}

	for index := 0; index < len(args); index++ {
		argument := args[index]
		valueFor := func(option string) (string, error) {
			if strings.HasPrefix(argument, option+"=") {
				return strings.TrimPrefix(argument, option+"="), nil
			}
			if index+1 >= len(args) {
				return "", fmt.Errorf("Missing value for %s", option)
			}
			index++
			return args[index], nil
		}
		switch {
		case argument == "--remove":
			request.remove = true
		case argument == "--show":
			request.show = true
		case strings.HasPrefix(argument, "--remove="):
			return request, errors.New(
				"Unsupported scbolt option with value: --remove; use '--remove' without a value",
			)
		case strings.HasPrefix(argument, "--show="):
			return request, errors.New(
				"Unsupported scbolt option with value: --show; use '--show' without a value",
			)
		case argument == "--config" || strings.HasPrefix(argument, "--config="):
			value, valueErr := valueFor("--config")
			if valueErr != nil {
				return request, valueErr
			}
			request.configuration = value
		case argument == "--params" || strings.HasPrefix(argument, "--params="):
			value, valueErr := valueFor("--params")
			if valueErr != nil {
				return request, valueErr
			}
			request.configuration = value
		case strings.HasPrefix(argument, "CONFIG="):
			request.configuration = strings.TrimPrefix(argument, "CONFIG=")
		case strings.HasPrefix(argument, "PARAMS="):
			request.configuration = strings.TrimPrefix(argument, "PARAMS=")
		case argument == "--references" || strings.HasPrefix(argument, "--references="):
			value, valueErr := valueFor("--references")
			if valueErr != nil {
				return request, valueErr
			}
			request.overrides = append(request.overrides, initOverride{"REFERENCES", value})
		case argument == "--old-file" || strings.HasPrefix(argument, "--old-file="):
			value, valueErr := valueFor("--old-file")
			if valueErr != nil {
				return request, valueErr
			}
			request.overrides = append(request.overrides, initOverride{"OLD_FILES", value})
		case argument == "--backend" || strings.HasPrefix(argument, "--backend="):
			value, valueErr := valueFor("--backend")
			if valueErr != nil {
				return request, valueErr
			}
			if !containsString([]string{"conda", "mamba", "micromamba", "docker"}, value) {
				return request, fmt.Errorf("Unsupported backend: %s", value)
			}
			request.backend = value
			request.backendGiven = true
			request.overrides = append(request.overrides, initOverride{"BACKEND", value})
		case strings.HasPrefix(argument, "--") && strings.Contains(argument, "="):
			name, value, _ := strings.Cut(argument, "=")
			normalized, normalizeErr := normalizeInitVariable(name)
			if normalizeErr != nil {
				return request, normalizeErr
			}
			request.overrides = append(request.overrides, initOverride{normalized, value})
		case strings.HasPrefix(argument, "--"):
			return request, unsupportedOptionError("init", argument)
		case strings.Contains(argument, "="):
			name, value, _ := strings.Cut(argument, "=")
			normalized, normalizeErr := normalizeInitVariable(name)
			if normalizeErr != nil {
				return request, normalizeErr
			}
			request.overrides = append(request.overrides, initOverride{normalized, value})
		default:
			request.positionals = append(request.positionals, argument)
		}
	}

	if request.configuration != "" {
		if len(request.positionals) > 0 {
			return request, errors.New(
				"Use either '--config=<file>' or a positional configuration file, not both",
			)
		}
		request.positionals = []string{request.configuration}
	}
	if request.remove && request.show {
		return request, errors.New("Use either '--remove' or '--show', not both")
	}
	if request.remove && len(request.positionals) > 0 {
		return request, errors.New("Use either '--remove' or a configuration file, not both")
	}
	if request.show && len(request.positionals) > 0 {
		return request, errors.New("Use either '--show' or a configuration file, not both")
	}
	if (request.remove || request.show) && len(request.overrides) > 0 {
		return request, errors.New(
			"Use configuration initializers only when creating a configuration file",
		)
	}
	if len(request.positionals) > 1 {
		return request, errors.New("Usage: scbolt init <scbolt.yml>")
	}
	return request, nil
}

func normalizeInitVariable(value string) (string, error) {
	value = strings.TrimPrefix(value, "--")
	value = strings.ToUpper(strings.ReplaceAll(value, "-", "_"))
	if !initVariablePattern.MatchString(value) {
		return "", fmt.Errorf("Invalid parameter name: %s", value)
	}
	return value, nil
}

func printInitHelp() {
	fmt.Println("usage: scbolt init [<scbolt.yml>] [options]")
	fmt.Println()
	fmt.Println("Create, update, or remove a scBOLT project configuration.")
	fmt.Println("New YAML projects also receive a Boolean inference spec.yml.")
	fmt.Println()
	fmt.Println("Parameters")
	fmt.Printf("  %-31s %s\n", "<scbolt.yml>", "configuration file to use")
	fmt.Printf("  %-31s %s\n", "--remove", "remove active project configuration")
	fmt.Printf("  %-31s %s\n", "--show", "display active configuration file")
	fmt.Printf("  %-31s %s\n", "--<key>=<value>", "initialize a new configuration file")
	fmt.Printf("  %-31s %s\n", "<key>=<value>", "initialize a new configuration file")
	fmt.Printf("  %-31s %s\n", "--help", "display this help")
}

func removeProjectConfiguration() error {
	projectFile := findProjectFileFromCwd()
	if projectFile == "" {
		fmt.Println("Project file not found.")
		printWarning("scBOLT project unchanged.")
		return nil
	}
	configuration := readProjectConfiguration(projectFile)
	fmt.Printf("Project file: %s\n", projectFile)
	if configuration.path != "" {
		fmt.Printf("Configuration file: %s\n", configuration.path)
	}
	if err := os.Remove(projectFile); err != nil {
		return errors.New("scBOLT project removal failed")
	}
	printSuccess("scBOLT project configuration removed.")
	return nil
}

func showProjectConfiguration() error {
	configuration := resolveProjectConfiguration()
	if configuration.path == "" {
		return errors.New("No configuration file found")
	}
	fmt.Printf("Configuration file: %s\n", configuration.path)
	return nil
}

func initializeProject(request initRequest) error {
	workingDirectory, err := os.Getwd()
	if err != nil {
		return err
	}
	projectFile := filepath.Join(workingDirectory, ".scbolt")
	previous := projectConfigurationSelection{}
	if exists(projectFile) {
		previous = readProjectConfiguration(projectFile)
	}
	failure := "scBOLT project initialization failed."
	if previous.path != "" {
		failure = "scBOLT project update failed."
	}

	configuration := ""
	if len(request.positionals) == 1 {
		configuration = request.positionals[0]
	}
	if configuration == "" {
		defaultConfiguration := previous.path
		if defaultConfiguration == "" {
			switch {
			case exists(filepath.Join(workingDirectory, defaultProjectConfigurationFile)):
				defaultConfiguration = defaultProjectConfigurationFile
			case exists(filepath.Join(workingDirectory, "params.mk")):
				defaultConfiguration = "params.mk"
			default:
				defaultConfiguration = defaultProjectConfigurationFile
			}
		}
		configuration = promptValue(
			"Select configuration file [" + defaultConfiguration + "]: ",
		)
		if configuration == "" {
			configuration = defaultConfiguration
		}
	}
	if configuration == "" {
		return reportInitFailure("No configuration file specified.", failure)
	}

	configurationPath := configuration
	if !filepath.IsAbs(configurationPath) {
		configurationPath = filepath.Join(workingDirectory, configurationPath)
	}
	configurationPath, _ = filepath.Abs(configurationPath)
	created := !exists(configurationPath)
	format := configurationFormatForPath(configuration)
	if format == configurationNone {
		message := "Configuration file must have a .yml, .yaml, or .mk extension: " + configuration
		return reportInitFailure(message, failure)
	}
	if created {
		parent := filepath.Dir(configurationPath)
		if info, statErr := os.Stat(parent); statErr != nil || !info.IsDir() {
			return reportInitFailure(
				"Configuration file directory not found: "+filepath.Dir(configuration),
				failure,
			)
		}
		content := minimalParamsContent(request.overrides)
		if format == configurationYAML {
			content, err = minimalYAMLContent(request.overrides)
			if err != nil {
				return reportInitFailure(err.Error(), failure)
			}
		}
		if writeErr := os.WriteFile(configurationPath, []byte(content), 0o644); writeErr != nil {
			return reportInitFailure(writeErr.Error(), failure)
		}
	} else if len(request.overrides) > 0 {
		printWarning("Configuration initializers ignored: configuration file already exists.")
	}
	var specificationPath string
	specificationCreated := false
	if format == configurationYAML {
		projectConfiguration, loadErr := loadProjectConfiguration(configurationPath)
		if loadErr != nil {
			return reportInitFailure(loadErr.Error(), failure)
		}
		specificationPath, specificationCreated, err = ensureProjectSpecification(
			configurationPath,
			projectConfiguration,
		)
		if err != nil {
			return reportInitFailure(err.Error(), failure)
		}
	}

	stored := configuration
	if filepath.IsAbs(configuration) {
		if relative, relativeErr := filepath.Rel(workingDirectory, configurationPath); relativeErr == nil {
			stored = relative
		} else {
			stored = configurationPath
		}
	}
	locatorKey := "CONFIG"
	if format == configurationLegacy {
		locatorKey = "PARAMS"
	}
	if writeErr := os.WriteFile(
		projectFile,
		[]byte(locatorKey+"="+stored+"\n"),
		0o644,
	); writeErr != nil {
		return reportInitFailure(writeErr.Error(), failure)
	}
	if !request.backendGiven {
		fmt.Printf("Backend: %s\n", request.backend)
	}
	if previous.path != "" {
		switch {
		case previous.path == stored && created:
			fmt.Printf("Configuration file: %s (created)\n", stored)
		case previous.path == stored:
			fmt.Printf("Configuration file: %s\n", stored)
		case created:
			fmt.Printf("Configuration file: %s -> %s (created)\n", previous.path, stored)
		default:
			fmt.Printf("Configuration file: %s -> %s\n", previous.path, stored)
		}
	} else {
		if created {
			fmt.Printf("Configuration file: %s (created)\n", stored)
		} else {
			fmt.Printf("Configuration file: %s\n", stored)
		}
	}
	if specificationPath != "" {
		displayPath := specificationPath
		if relative, relativeErr := filepath.Rel(workingDirectory, specificationPath); relativeErr == nil {
			displayPath = relative
		}
		if specificationCreated {
			fmt.Printf("Specification file: %s (created)\n", displayPath)
		} else {
			fmt.Printf("Specification file: %s\n", displayPath)
		}
	}
	if previous.path == "" {
		printSuccess("scBOLT project initialized.")
	} else if previous.path != stored || created || specificationCreated {
		printSuccess("scBOLT project updated.")
	} else {
		printWarning("scBOLT project unchanged.")
	}
	return nil
}

func ensureProjectSpecification(
	configurationPath string,
	configuration *projectConfiguration,
) (string, bool, error) {
	specification, defined := configuration.Lookup("SPEC_FILE")
	if !defined {
		specification = "spec.yml"
	}
	if specification == "" {
		return "", false, nil
	}
	path := specification
	if !filepath.IsAbs(path) {
		path = filepath.Join(filepath.Dir(configurationPath), path)
	}
	path = filepath.Clean(path)
	if exists(path) {
		return path, false, nil
	}
	parent := filepath.Dir(path)
	if info, err := os.Stat(parent); err != nil || !info.IsDir() {
		return "", false, fmt.Errorf("Specification file directory not found: %s", parent)
	}
	content, err := minimalSpecificationContent()
	if err != nil {
		return "", false, err
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		return "", false, err
	}
	return path, true, nil
}

func promptValue(prompt string) string {
	fmt.Fprint(os.Stderr, prompt)
	reader := bufio.NewReader(os.Stdin)
	value, _ := reader.ReadString('\n')
	if !isTerminal(os.Stdin) {
		fmt.Fprintln(os.Stderr)
	}
	return strings.TrimSpace(value)
}

func reportInitFailure(message string, failure string) error {
	fmt.Fprintln(os.Stderr, message)
	printFailure(failure)
	return &reportedError{status: 1}
}

func minimalParamsContent(overrides []initOverride) string {
	values := make(map[string]string)
	lastIndex := make(map[string]int)
	for index, override := range overrides {
		values[override.name] = override.value
		lastIndex[override.name] = index
	}
	value := func(name string) string {
		return values[name]
	}
	assignment := func(name string) string {
		if value(name) == "" {
			return name + " =\n"
		}
		return fmt.Sprintf("%s = %s\n", name, value(name))
	}
	extra := func(section string) string {
		var builder strings.Builder
		wrote := false
		for index, override := range overrides {
			if lastIndex[override.name] != index || isMinimalInitVariable(override.name) ||
				initOverrideSection(override.name) != section {
				continue
			}
			if !wrote {
				builder.WriteByte('\n')
				wrote = true
			}
			builder.WriteString(fmt.Sprintf("%s = %s\n", override.name, override.value))
		}
		return builder.String()
	}

	var builder strings.Builder
	builder.WriteString("########################\n### Project settings ###\n########################\n\n")
	builder.WriteString("# Organism used for gene resources (e.g. mouse or human).\n")
	builder.WriteString(assignment("ORGANISM"))
	builder.WriteByte('\n')
	builder.WriteString("# Experimental conditions (e.g. ctrl treated).\n")
	builder.WriteString("# Leave empty for an unlabeled single-condition project.\n")
	builder.WriteString(assignment("CONDITIONS"))
	builder.WriteString(extra("project"))
	builder.WriteByte('\n')

	builder.WriteString("#####################\n### Input sources ###\n#####################\n\n")
	builder.WriteString("# Input sources are mutually exclusive. Use one family:\n")
	builder.WriteString("# - SRA or SRA_<CONDITION>   : list of SRA run IDs\n")
	builder.WriteString("# - GSM or GSM_<CONDITION>   : GEO sample ID\n")
	builder.WriteString("# - COUNT_FILES              : precomputed count AnnData files\n")
	builder.WriteString("# - MACROSTATE_FILES         : precomputed macrostate files\n")
	builder.WriteString("# - BINARIZATION_FILE        : precomputed binarization file\n\n")
	builder.WriteString("# SRA = SRR12345678 SRR87654321\n")
	builder.WriteString("# SRA_CTRL = SRR12345678\n")
	builder.WriteString("# SRA_TREATED = SRR87654321 SRR87654322\n")
	builder.WriteString(conditionAssignments("SRA", value("CONDITIONS"), values))
	builder.WriteByte('\n')
	builder.WriteString("# GSM = GSM5492245\n")
	builder.WriteString("# GSM_CTRL = GSM5492245\n")
	builder.WriteString("# GSM_TREATED = GSM5492246\n")
	builder.WriteString(conditionAssignments("GSM", value("CONDITIONS"), values))
	builder.WriteByte('\n')
	builder.WriteString(assignment("COUNT_FILES"))
	builder.WriteString(assignment("MACROSTATE_FILES"))
	builder.WriteString(assignment("BINARIZATION_FILE"))
	builder.WriteString(extra("input"))
	builder.WriteByte('\n')

	builder.WriteString("##############################\n### Module-specific inputs ###\n##############################\n\n")
	builder.WriteString("# Required by module 'annotation'.\n")
	builder.WriteString("# Space-separated biological labels assigned to clusters 0..n.\n")
	builder.WriteString("# Labels are matched to clusters in numerical order.\n")
	builder.WriteString("# Example: LABEL = HSC MPP LMPP GMP\n")
	builder.WriteString(assignment("LABEL"))
	builder.WriteByte('\n')
	builder.WriteString("# Required by module 'spec'.\n")
	builder.WriteString("# YAML file defining Boolean-network constraints.\n")
	builder.WriteString("# See case studies for examples or run: scbolt spec help\n")
	builder.WriteString(assignment("SPEC_FILE"))
	builder.WriteString(extra("module"))
	return builder.String()
}

func conditionAssignments(family string, conditions string, values map[string]string) string {
	var builder strings.Builder
	if strings.TrimSpace(conditions) == "" {
		if values[family] == "" {
			builder.WriteString(family)
			builder.WriteString(" =\n")
		} else {
			builder.WriteString(fmt.Sprintf("%s = %s\n", family, values[family]))
		}
		return builder.String()
	}
	for _, condition := range strings.Fields(conditions) {
		name := family + "_" + strings.ToUpper(condition)
		if values[name] == "" {
			builder.WriteString(name)
			builder.WriteString(" =\n")
		} else {
			builder.WriteString(fmt.Sprintf("%s = %s\n", name, values[name]))
		}
	}
	return builder.String()
}

func isMinimalInitVariable(name string) bool {
	if containsString([]string{
		"ORGANISM", "CONDITIONS", "SRA", "GSM", "COUNT_FILES",
		"MACROSTATE_FILES", "BINARIZATION_FILE", "LABEL", "SPEC_FILE",
	}, name) {
		return true
	}
	return strings.HasPrefix(name, "SRA_") || strings.HasPrefix(name, "GSM_")
}

func initOverrideSection(name string) string {
	if containsString([]string{
		"ORGANISM", "CONDITIONS", "PROJECT_DIR", "RESOURCES_DIR", "BACKEND",
		"MEMORY", "JOBS", "SEED", "LOGGING",
	}, name) {
		return "project"
	}
	if name == "SRA" || name == "GSM" || strings.HasPrefix(name, "SRA_") ||
		strings.HasPrefix(name, "GSM_") || containsString([]string{
		"COUNT_FILES", "MACROSTATE_FILES", "BINARIZATION_FILE", "OLD_FILES",
	}, name) {
		return "input"
	}
	return "module"
}
