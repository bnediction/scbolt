package main

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

type DiagnosticStatus string

const (
	DiagnosticOK      DiagnosticStatus = "ok"
	DiagnosticWarning DiagnosticStatus = "warning"
	DiagnosticError   DiagnosticStatus = "error"
)

var diagnosticSectionOrder = []string{
	"scBOLT",
	"Host",
	"Configuration",
	"Backend",
	"Runtime",
	"Numerical reproducibility",
}

type Diagnostic struct {
	Section string
	Name    string
	Value   string
	Status  DiagnosticStatus
	Detail  string
}

type DiagnosticReport struct {
	Diagnostics []Diagnostic
}

func (report *DiagnosticReport) Add(diagnostic Diagnostic) {
	report.Diagnostics = append(report.Diagnostics, diagnostic)
}

func (report DiagnosticReport) Count(status DiagnosticStatus) int {
	count := 0
	for _, diagnostic := range report.Diagnostics {
		if diagnostic.Status == status {
			count++
		}
	}
	return count
}

func (report DiagnosticReport) ExitCode() int {
	if report.Count(DiagnosticError) > 0 {
		return 1
	}
	return 0
}

type CommandRunner interface {
	LookPath(name string) (string, error)
	Run(ctx context.Context, name string, args ...string) ([]byte, error)
}

type execCommandRunner struct{}

func (execCommandRunner) LookPath(name string) (string, error) {
	return exec.LookPath(name)
}

func (execCommandRunner) Run(
	ctx context.Context,
	name string,
	args ...string,
) ([]byte, error) {
	return exec.CommandContext(ctx, name, args...).CombinedOutput()
}

type HostDetector interface {
	Detect(ctx context.Context, runner CommandRunner) HostInfo
}

type diagnosticDependencies struct {
	runner         CommandRunner
	hostDetector   HostDetector
	executable     func() (string, error)
	workingDir     func() (string, error)
	root           func() (string, error)
	getenv         func(string) string
	commandTimeout time.Duration
}

func defaultDiagnosticDependencies() diagnosticDependencies {
	return diagnosticDependencies{
		runner:         execCommandRunner{},
		hostDetector:   nativeHostDetector{},
		executable:     os.Executable,
		workingDir:     os.Getwd,
		root:           scboltRoot,
		getenv:         os.Getenv,
		commandTimeout: 5 * time.Second,
	}
}

type diagnosticConfiguration struct {
	backend         effectiveSetting
	logging         effectiveSetting
	params          effectiveSetting
	projectDir      effectiveSetting
	resourcesDir    effectiveSetting
	seed            effectiveSetting
	openBLASCore    effectiveSetting
	projectSelected bool
}

type diagnosticCollection struct {
	report DiagnosticReport
	host   HostInfo
	config diagnosticConfiguration
	image  *dockerImageInspection
}

const launcherDiagnosticsHelp = `usage: scbolt diagnostics

Report diagnostics for the scBOLT installation, host platform, selected
runtime backend, and numerical reproducibility profile.

This command does not validate pipeline inputs or module-specific
requirements. Use 'scbolt <command> check' for module validation.
`

func runDiagnosticsCommand(
	ctx context.Context,
	cfg config,
	args []string,
	output io.Writer,
	interactive bool,
	dependencies diagnosticDependencies,
) (int, error) {
	if diagnosticsHelpRequested(args) {
		_, _ = io.WriteString(output, launcherDiagnosticsHelp)
		return 0, nil
	}
	if err := validateDiagnosticsArguments(args); err != nil {
		return 2, err
	}
	report := collectDiagnostics(ctx, cfg, dependencies)
	renderDiagnostics(output, report, interactive)
	return report.ExitCode(), nil
}

func diagnosticsHelpRequested(args []string) bool {
	commandFound := false
	for _, argument := range args {
		if argument == "diagnostics" {
			commandFound = true
			continue
		}
		if commandFound && isHelpToken(argument) {
			return true
		}
	}
	return false
}

func validateDiagnosticsArguments(args []string) error {
	commandCount := 0
	for index := 0; index < len(args); index++ {
		argument := args[index]
		if argument == "diagnostics" {
			commandCount++
			continue
		}
		if strings.Contains(argument, "=") {
			continue
		}
		switch argument {
		case "--params", "--backend", "--logging":
			if index+1 >= len(args) || args[index+1] == "diagnostics" {
				return fmt.Errorf("missing value for %s", argument)
			}
			index++
		case "--help", "-h", "help":
			continue
		default:
			return fmt.Errorf(
				"usage: scbolt diagnostics (unexpected argument: %s)",
				argument,
			)
		}
	}
	if commandCount != 1 {
		return fmt.Errorf("usage: scbolt diagnostics")
	}
	return nil
}

func collectDiagnostics(
	ctx context.Context,
	cfg config,
	dependencies diagnosticDependencies,
) DiagnosticReport {
	host := dependencies.hostDetector.Detect(ctx, dependencies.runner)
	configuration := buildDiagnosticConfiguration(cfg, dependencies)
	collection := diagnosticCollection{
		host:   host,
		config: configuration,
	}

	collectScboltDiagnostics(&collection, dependencies)
	collectHostDiagnostics(&collection)
	collectConfigurationDiagnostics(&collection)
	if cfg.backend == "docker" {
		collectDockerDiagnostics(ctx, &collection, cfg, dependencies)
	} else {
		collectLocalDiagnostics(ctx, &collection, cfg, dependencies)
	}
	collectNumericalDiagnostics(&collection, cfg, dependencies)
	return collection.report
}

func buildDiagnosticConfiguration(
	cfg config,
	dependencies diagnosticDependencies,
) diagnosticConfiguration {
	workingDirectory, _ := dependencies.workingDir()
	projectFile := findProjectFile(workingDirectory)
	projectRoot := ""
	if projectFile != "" {
		projectRoot = filepath.Dir(projectFile)
	}
	params := effectiveSetting{value: cfg.paramsPath, source: cfg.paramsSource}
	project := cfg.setting("PROJECT_DIR")
	resources := cfg.setting("RESOURCES_DIR")
	projectSelected := cfg.paramsPath != "" || projectFile != "" || project.source == "cli"

	project.value = resolveDiagnosticPath(
		project.value,
		project.source,
		cfg.paramsPath,
		projectRoot,
		workingDirectory,
		false,
	)
	resources.value = resolveDiagnosticPath(
		resources.value,
		resources.source,
		cfg.paramsPath,
		projectRoot,
		workingDirectory,
		true,
	)
	return diagnosticConfiguration{
		backend:         cfg.setting("BACKEND"),
		logging:         cfg.setting("LOGGING"),
		params:          params,
		projectDir:      project,
		resourcesDir:    resources,
		seed:            cfg.setting("SEED"),
		openBLASCore:    cfg.setting("OPENBLAS_CORETYPE"),
		projectSelected: projectSelected,
	}
}

func (cfg config) setting(name string) effectiveSetting {
	if setting, found := cfg.settings[name]; found {
		return setting
	}
	return effectiveSetting{source: "default"}
}

func resolveDiagnosticPath(
	value string,
	source string,
	paramsPath string,
	projectRoot string,
	workingDirectory string,
	resourcePath bool,
) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return ""
	}
	if filepath.IsAbs(value) {
		return filepath.Clean(value)
	}
	base := workingDirectory
	if source != "cli" {
		if resourcePath && projectRoot != "" {
			base = projectRoot
		} else if paramsPath != "" {
			base = filepath.Dir(paramsPath)
		} else if projectRoot != "" {
			base = projectRoot
		}
	}
	return filepath.Clean(filepath.Join(base, value))
}

func collectScboltDiagnostics(
	collection *diagnosticCollection,
	dependencies diagnosticDependencies,
) {
	root, _ := dependencies.root()
	version := launcherVersion
	if version == "" || version == "dev" {
		if data, err := os.ReadFile(filepath.Join(root, "VERSION")); err == nil {
			version = strings.TrimSpace(string(data))
		}
	}
	if version == "" {
		version = "unknown"
	}
	collection.report.Add(Diagnostic{
		Section: "scBOLT",
		Name:    "version",
		Value:   version,
		Status:  DiagnosticOK,
	})

	executable, err := dependencies.executable()
	if err != nil {
		collection.report.Add(Diagnostic{
			Section: "scBOLT",
			Name:    "executable",
			Value:   "unavailable",
			Status:  DiagnosticWarning,
			Detail:  "The launcher executable path could not be determined.",
		})
	} else {
		if absolute, absoluteErr := filepath.Abs(executable); absoluteErr == nil {
			executable = absolute
		}
		collection.report.Add(Diagnostic{
			Section: "scBOLT",
			Name:    "executable",
			Value:   executable,
			Status:  DiagnosticOK,
		})
	}

	if collection.config.params.value == "" {
		collection.report.Add(Diagnostic{
			Section: "scBOLT",
			Name:    "parameter file",
			Value:   "not selected",
			Status:  DiagnosticOK,
		})
	} else if info, statErr := os.Stat(collection.config.params.value); statErr != nil || info.IsDir() {
		collection.report.Add(Diagnostic{
			Section: "scBOLT",
			Name:    "parameter file",
			Value:   collection.config.params.value,
			Status:  DiagnosticError,
			Detail:  "Select an existing readable .mk parameter file.",
		})
	} else {
		collection.report.Add(Diagnostic{
			Section: "scBOLT",
			Name:    "parameter file",
			Value:   collection.config.params.value,
			Status:  DiagnosticOK,
		})
	}

	if !collection.config.projectSelected {
		collection.report.Add(Diagnostic{
			Section: "scBOLT",
			Name:    "project directory",
			Value:   "not selected",
			Status:  DiagnosticOK,
			Detail:  "No active project is required for installation diagnostics.",
		})
	} else {
		collection.report.Add(directoryDiagnostic(
			"scBOLT",
			"project directory",
			collection.config.projectDir.value,
		))
	}
	collection.report.Add(directoryDiagnostic(
		"scBOLT",
		"resources directory",
		collection.config.resourcesDir.value,
	))
}

func collectConfigurationDiagnostics(collection *diagnosticCollection) {
	addConfigurationDiagnostic(
		&collection.report,
		"backend",
		collection.config.backend,
	)
	logging := strings.TrimSpace(collection.config.logging.value)
	switch strings.ToLower(logging) {
	case "true", "1", "yes", "on":
		logging = "enabled"
	case "false", "0", "no", "off":
		logging = "disabled"
	}
	addConfigurationDiagnostic(
		&collection.report,
		"logging",
		effectiveSetting{
			value:  logging,
			source: collection.config.logging.source,
		},
	)
	addConfigurationDiagnostic(
		&collection.report,
		"parameter file",
		collection.config.params,
	)
	if collection.config.projectSelected {
		addConfigurationDiagnostic(
			&collection.report,
			"project directory",
			collection.config.projectDir,
		)
	}
	addConfigurationDiagnostic(
		&collection.report,
		"resources directory",
		collection.config.resourcesDir,
	)
	addConfigurationDiagnostic(
		&collection.report,
		"random seed",
		collection.config.seed,
	)
	coreType := strings.TrimSpace(collection.config.openBLASCore.value)
	profileSource := collection.config.openBLASCore.source
	if coreType == "" && collection.host.HaswellCompatible() {
		coreType = "Haswell"
		profileSource = "scBOLT automatic numerical profile"
	}
	profile := "openblas-auto"
	if coreType != "" {
		profile = "openblas-" + strings.ToLower(coreType)
	}
	addConfigurationDiagnostic(
		&collection.report,
		"numerical profile",
		effectiveSetting{value: profile, source: profileSource},
	)
}

func addConfigurationDiagnostic(
	report *DiagnosticReport,
	name string,
	setting effectiveSetting,
) {
	value := setting.value
	if strings.TrimSpace(value) == "" {
		value = "not selected"
	}
	detail := ""
	if setting.source != "" {
		detail = "source: " + displayConfigurationSource(setting.source)
	}
	report.Add(Diagnostic{
		Section: "Configuration",
		Name:    name,
		Value:   value,
		Status:  DiagnosticOK,
		Detail:  detail,
	})
}

func displayConfigurationSource(source string) string {
	switch source {
	case "cli":
		return "CLI override"
	case "params":
		return "project configuration"
	case "user-config":
		return "global configuration"
	case "install":
		return "installed backend configuration"
	case "environment":
		return "process environment"
	case "default_params.mk", "default":
		return "default"
	default:
		return source
	}
}

func collectNumericalDiagnostics(
	collection *diagnosticCollection,
	cfg config,
	dependencies diagnosticDependencies,
) {
	collection.report.Add(Diagnostic{
		Section: "Numerical reproducibility",
		Name:    "BLAS implementation",
		Value:   "OpenBLAS",
		Status:  DiagnosticOK,
		Detail:  "scBOLT runtime environments pin the OpenBLAS implementation.",
	})

	coreType := strings.TrimSpace(collection.config.openBLASCore.value)
	coreSource := collection.config.openBLASCore.source
	if coreType == "" && collection.image != nil {
		if value := collection.image.Environment["OPENBLAS_CORETYPE"]; value != "" {
			coreType = value
			coreSource = "container image"
		}
	}
	if coreType == "" && collection.host.HaswellCompatible() {
		coreType = "Haswell"
		coreSource = "scBOLT automatic numerical profile"
	}
	if coreType == "" {
		collection.report.Add(Diagnostic{
			Section: "Numerical reproducibility",
			Name:    "OpenBLAS core type",
			Value:   "not set",
			Status:  DiagnosticWarning,
			Detail: "The expected value is Haswell. OpenBLAS kernel selection " +
				"will otherwise remain processor-dependent.",
		})
	} else if !strings.EqualFold(coreType, "Haswell") {
		collection.report.Add(Diagnostic{
			Section: "Numerical reproducibility",
			Name:    "OpenBLAS core type",
			Value:   coreType,
			Status:  DiagnosticWarning,
			Detail: "The expected value is Haswell; diagnostics do not modify " +
				"the configured value.",
		})
	} else {
		detail := "OPENBLAS_CORETYPE=Haswell normalises OpenBLAS kernel selection."
		if coreSource != "" {
			detail += " Source: " + displayConfigurationSource(coreSource) + "."
		}
		collection.report.Add(Diagnostic{
			Section: "Numerical reproducibility",
			Name:    "OpenBLAS core type",
			Value:   "Haswell",
			Status:  DiagnosticOK,
			Detail:  detail,
		})
	}

	collection.report.Add(Diagnostic{
		Section: "Numerical reproducibility",
		Name:    "BLAS threads",
		Value:   "1 for deterministic numerical routines",
		Status:  DiagnosticOK,
		Detail:  "scBOLT applies function-scoped numerical thread limits where required.",
	})
	if limits := numericalThreadEnvironment(dependencies.getenv); limits != "" {
		collection.report.Add(Diagnostic{
			Section: "Numerical reproducibility",
			Name:    "process thread limits",
			Value:   limits,
			Status:  DiagnosticOK,
		})
	}
	collection.report.Add(Diagnostic{
		Section: "Numerical reproducibility",
		Name:    "random seed",
		Value:   collection.config.seed.value,
		Status:  DiagnosticOK,
		Detail:  "source: " + displayConfigurationSource(collection.config.seed.source),
	})
	collection.report.Add(Diagnostic{
		Section: "Numerical reproducibility",
		Name:    "UMAP numerical controls",
		Value:   "enabled",
		Status:  DiagnosticOK,
		Detail: "Self-distances are exact, spectral coordinates are oriented and " +
			"converted to float32, and fitted a/b values are preserved without rounding.",
	})
	collection.report.Add(Diagnostic{
		Section: "Numerical reproducibility",
		Name:    "t-SNE numerical controls",
		Value:   "enabled",
		Status:  DiagnosticOK,
		Detail:  "Seeded random initialization and function-scoped thread limits define the serial path.",
	})

	contract, contractStatus, contractDetail := numericalArchitectureContract(
		collection.host,
	)
	collection.report.Add(Diagnostic{
		Section: "Numerical reproducibility",
		Name:    "numerical architecture",
		Value:   contract,
		Status:  contractStatus,
		Detail:  contractDetail,
	})

	detail := "Different processor microarchitectures may still produce small " +
		"floating-point differences, which UMAP and t-SNE may amplify."
	if cfg.backend == "docker" {
		detail = "Docker fixes the software environment, and the Haswell profile " +
			"normalises OpenBLAS kernel selection. " + detail
	}
	collection.report.Add(Diagnostic{
		Section: "Numerical reproducibility",
		Name:    "cross-platform identity",
		Value:   "not guaranteed",
		Status:  DiagnosticWarning,
		Detail: detail + " Exact numerical identity is not claimed unless the " +
			"complete configuration has been validated.",
	})
}

func numericalThreadEnvironment(getenv func(string) string) string {
	variables := []struct {
		name  string
		label string
	}{
		{name: "OPENBLAS_NUM_THREADS", label: "OpenBLAS"},
		{name: "OMP_NUM_THREADS", label: "OpenMP"},
		{name: "MKL_NUM_THREADS", label: "MKL"},
		{name: "NUMEXPR_NUM_THREADS", label: "NumExpr"},
	}
	values := make([]string, 0, len(variables))
	for _, variable := range variables {
		if value := strings.TrimSpace(getenv(variable.name)); value != "" {
			values = append(values, variable.label+"="+value)
		}
	}
	return strings.Join(values, ", ")
}

func directoryDiagnostic(section string, name string, path string) Diagnostic {
	status, detail := directoryStatus(path)
	return Diagnostic{
		Section: section,
		Name:    name,
		Value:   path,
		Status:  status,
		Detail:  detail,
	}
}

func directoryStatus(path string) (DiagnosticStatus, string) {
	if strings.TrimSpace(path) == "" {
		return DiagnosticWarning, "No directory is configured."
	}
	info, err := os.Stat(path)
	if err == nil {
		if !info.IsDir() {
			return DiagnosticError, "The configured path is not a directory."
		}
		directory, openErr := os.Open(path)
		if openErr != nil {
			return DiagnosticError, "The directory is not accessible."
		}
		_ = directory.Close()
		if info.Mode().Perm()&0o222 == 0 {
			return DiagnosticError, "The directory is not writable."
		}
		return DiagnosticOK, ""
	}
	if !os.IsNotExist(err) {
		return DiagnosticError, "The directory cannot be inspected."
	}
	ancestor := filepath.Dir(path)
	for {
		ancestorInfo, ancestorErr := os.Stat(ancestor)
		if ancestorErr == nil {
			if !ancestorInfo.IsDir() || ancestorInfo.Mode().Perm()&0o222 == 0 {
				return DiagnosticError, "The directory cannot be created from its nearest existing parent."
			}
			return DiagnosticOK, "The directory does not exist yet; its parent is writable."
		}
		parent := filepath.Dir(ancestor)
		if parent == ancestor {
			return DiagnosticError, "No accessible parent directory was found."
		}
		ancestor = parent
	}
}

func renderDiagnostics(
	output io.Writer,
	report DiagnosticReport,
	interactive bool,
) {
	for sectionIndex, section := range diagnosticSectionOrder {
		if sectionIndex > 0 {
			fmt.Fprintln(output)
		}
		fmt.Fprintln(output, section)
		for _, diagnostic := range report.Diagnostics {
			if diagnostic.Section != section {
				continue
			}
			fmt.Fprintf(
				output,
				"  %s %s: %s\n",
				diagnosticStatusIcon(diagnostic.Status, interactive),
				diagnostic.Name,
				diagnostic.Value,
			)
			for _, line := range strings.Split(strings.TrimSpace(diagnostic.Detail), "\n") {
				if line != "" {
					fmt.Fprintf(output, "    %s\n", line)
				}
			}
		}
	}

	fmt.Fprintln(output)
	fmt.Fprintln(output, "Status")
	errors := report.Count(DiagnosticError)
	warnings := report.Count(DiagnosticWarning)
	if errors > 0 {
		fmt.Fprintf(
			output,
			"  Not operational: %d blocking %s%s.\n",
			errors,
			plural(errors, "error", "errors"),
			warningSuffix(warnings),
		)
		return
	}
	if warnings > 0 {
		fmt.Fprintf(
			output,
			"  Operational with %d %s.\n",
			warnings,
			plural(warnings, "warning", "warnings"),
		)
		return
	}
	fmt.Fprintln(output, "  Operational.")
}

func diagnosticStatusIcon(status DiagnosticStatus, interactive bool) string {
	icon := "✓"
	color := "\x1b[0;32m"
	switch status {
	case DiagnosticWarning:
		icon = "⚠"
		color = "\x1b[0;33m"
	case DiagnosticError:
		icon = "✗"
		color = "\x1b[0;31m"
	}
	if !interactive {
		return icon
	}
	return color + icon + "\x1b[0m"
}

func warningSuffix(warnings int) string {
	if warnings == 0 {
		return ""
	}
	return fmt.Sprintf(
		" and %d %s",
		warnings,
		plural(warnings, "warning", "warnings"),
	)
}

func plural(count int, singular string, multiple string) string {
	if count == 1 {
		return singular
	}
	return multiple
}

func withDiagnosticTimeout(
	ctx context.Context,
	dependencies diagnosticDependencies,
) (context.Context, context.CancelFunc) {
	timeout := dependencies.commandTimeout
	if timeout <= 0 {
		timeout = 5 * time.Second
	}
	return context.WithTimeout(ctx, timeout)
}
