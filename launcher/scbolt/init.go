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
	remove       bool
	show         bool
	params       string
	positionals  []string
	overrides    []initOverride
	backend      string
	backendGiven bool
}

var initVariablePattern = regexp.MustCompile(`^[A-Z_][A-Z0-9_]*$`)

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
		case argument == "--params" || strings.HasPrefix(argument, "--params="):
			value, valueErr := valueFor("--params")
			if valueErr != nil {
				return request, valueErr
			}
			request.params = value
		case strings.HasPrefix(argument, "PARAMS="):
			request.params = strings.TrimPrefix(argument, "PARAMS=")
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

	if request.params != "" {
		if len(request.positionals) > 0 {
			return request, errors.New(
				"Use either '--params=<file>' or a positional parameter file, not both",
			)
		}
		request.positionals = []string{request.params}
	}
	if request.remove && request.show {
		return request, errors.New("Use either '--remove' or '--show', not both")
	}
	if request.remove && len(request.positionals) > 0 {
		return request, errors.New("Use either '--remove' or a parameter file, not both")
	}
	if request.show && len(request.positionals) > 0 {
		return request, errors.New("Use either '--show' or a parameter file, not both")
	}
	if (request.remove || request.show) && len(request.overrides) > 0 {
		return request, errors.New(
			"Use parameter initializers only when creating a parameter file",
		)
	}
	if len(request.positionals) > 1 {
		return request, errors.New("Usage: scbolt init <params.mk>")
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
	fmt.Println("usage: scbolt init [<params.mk>] [options]")
	fmt.Println()
	fmt.Println("Create, update, or remove the project configuration used by scBOLT.")
	fmt.Println()
	fmt.Println("Parameters")
	fmt.Printf("  %-31s %s\n", "<params.mk>", "parameter file to use")
	fmt.Printf("  %-31s %s\n", "--remove", "remove active project configuration")
	fmt.Printf("  %-31s %s\n", "--show", "display active parameter file")
	fmt.Printf("  %-31s %s\n", "--<parameter>=<value>", "initialize a new parameter file")
	fmt.Printf("  %-31s %s\n", "<parameter>=<value>", "initialize a new parameter file")
	fmt.Printf("  %-31s %s\n", "--help", "display this help")
}

func removeProjectConfiguration() error {
	projectFile := findProjectFileFromCwd()
	if projectFile == "" {
		fmt.Println("Project file not found.")
		printWarning("scBOLT project unchanged.")
		return nil
	}
	params := readProjectParams(projectFile)
	fmt.Printf("Project file: %s\n", projectFile)
	if params != "" {
		fmt.Printf("Parameter file: %s\n", params)
	}
	if err := os.Remove(projectFile); err != nil {
		return errors.New("scBOLT project removal failed")
	}
	printSuccess("scBOLT project configuration removed.")
	return nil
}

func showProjectConfiguration() error {
	params := resolveProjectParams()
	if params == "" {
		return errors.New("No parameter file found")
	}
	fmt.Printf("Parameter file: %s\n", params)
	return nil
}

func initializeProject(request initRequest) error {
	workingDirectory, err := os.Getwd()
	if err != nil {
		return err
	}
	projectFile := filepath.Join(workingDirectory, ".scbolt")
	previousParams := ""
	if exists(projectFile) {
		previousParams = readProjectParams(projectFile)
	}
	failure := "scBOLT project initialization failed."
	if previousParams != "" {
		failure = "scBOLT project update failed."
	}

	params := ""
	if len(request.positionals) == 1 {
		params = request.positionals[0]
	}
	if params == "" {
		defaultParams := previousParams
		if defaultParams == "" && exists(filepath.Join(workingDirectory, "params.mk")) {
			defaultParams = "params.mk"
		}
		prompt := "Select parameter file: "
		if defaultParams != "" {
			prompt = "Select parameter file [" + defaultParams + "]: "
		}
		params = promptValue(prompt)
		if params == "" {
			params = defaultParams
		}
	}
	if params == "" {
		return reportInitFailure("No parameter file specified.", failure)
	}

	paramsPath := params
	if !filepath.IsAbs(paramsPath) {
		paramsPath = filepath.Join(workingDirectory, paramsPath)
	}
	paramsPath, _ = filepath.Abs(paramsPath)
	created := !exists(paramsPath)
	if filepath.Ext(params) != ".mk" {
		message := "Parameter file must have a .mk extension: " + params
		if created {
			message = "Parameter file not found: " + params
		}
		return reportInitFailure(message, failure)
	}
	if created {
		parent := filepath.Dir(paramsPath)
		if info, statErr := os.Stat(parent); statErr != nil || !info.IsDir() {
			return reportInitFailure(
				"Parameter file directory not found: "+filepath.Dir(params),
				failure,
			)
		}
		content := minimalParamsContent(request.overrides)
		if writeErr := os.WriteFile(paramsPath, []byte(content), 0o644); writeErr != nil {
			return reportInitFailure(writeErr.Error(), failure)
		}
	} else if len(request.overrides) > 0 {
		printWarning("Parameter initializers ignored: parameter file already exists.")
	}

	stored := params
	if filepath.IsAbs(params) {
		if relative, relativeErr := filepath.Rel(workingDirectory, paramsPath); relativeErr == nil {
			stored = relative
		} else {
			stored = paramsPath
		}
	}
	if writeErr := os.WriteFile(projectFile, []byte("PARAMS="+stored+"\n"), 0o644); writeErr != nil {
		return reportInitFailure(writeErr.Error(), failure)
	}
	if !request.backendGiven {
		fmt.Printf("Backend: %s\n", request.backend)
	}

	if previousParams != "" {
		switch {
		case previousParams == stored && created:
			fmt.Printf("Parameter file: %s (created)\n", stored)
			printSuccess("scBOLT project updated.")
		case previousParams == stored:
			fmt.Printf("Parameter file: %s\n", stored)
			printWarning("scBOLT project unchanged.")
		case created:
			fmt.Printf("Parameter file: %s -> %s (created)\n", previousParams, stored)
			printSuccess("scBOLT project updated.")
		default:
			fmt.Printf("Parameter file: %s -> %s\n", previousParams, stored)
			printSuccess("scBOLT project updated.")
		}
	} else {
		if created {
			fmt.Printf("Parameter file: %s (created)\n", stored)
		} else {
			fmt.Printf("Parameter file: %s\n", stored)
		}
		printSuccess("scBOLT project initialized.")
	}
	return nil
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
