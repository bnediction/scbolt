package main

import (
	"context"
	"encoding/json"
	"fmt"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

type dockerImageInspection struct {
	ID           string
	OperatingSys string
	Architecture string
	RepoDigests  []string
	Environment  map[string]string
}

type dockerInspectRecord struct {
	ID           string   `json:"Id"`
	OperatingSys string   `json:"Os"`
	Architecture string   `json:"Architecture"`
	RepoDigests  []string `json:"RepoDigests"`
	Config       struct {
		Environment []string `json:"Env"`
	} `json:"Config"`
}

var makeVersionPattern = regexp.MustCompile(`GNU Make ([0-9]+)\.([0-9]+)`) //nolint:gochecknoglobals

func collectDockerDiagnostics(
	ctx context.Context,
	collection *diagnosticCollection,
	cfg config,
	dependencies diagnosticDependencies,
) {
	engineLabel := containerEngineLabel(cfg.engine)
	collection.report.Add(Diagnostic{
		Section: "Backend",
		Name:    "selected backend",
		Value:   "docker",
		Status:  DiagnosticOK,
	})
	collection.report.Add(Diagnostic{
		Section: "Backend",
		Name:    "container engine",
		Value:   cfg.engine,
		Status:  DiagnosticOK,
	})
	collection.report.Add(Diagnostic{
		Section: "Backend",
		Name:    "image",
		Value:   cfg.image,
		Status:  DiagnosticOK,
	})
	collectDockerMountDiagnostics(collection, cfg, dependencies)

	enginePath, err := dependencies.runner.LookPath(cfg.engine)
	if err != nil {
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    engineLabel + " CLI",
			Value:   "unavailable",
			Status:  DiagnosticError,
			Detail:  "Install " + engineLabel + " and run diagnostics again.",
		})
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    engineLabel + " daemon",
			Value:   "not checked",
			Status:  DiagnosticWarning,
			Detail:  "The daemon cannot be checked without the container CLI.",
		})
		return
	}

	versionContext, cancelVersion := withDiagnosticTimeout(ctx, dependencies)
	versionOutput, versionErr := dependencies.runner.Run(
		versionContext,
		enginePath,
		"--version",
	)
	cancelVersion()
	if versionErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    engineLabel + " CLI",
			Value:   enginePath,
			Status:  DiagnosticError,
			Detail:  "The container CLI was found but could not be executed.",
		})
		return
	}
	collection.report.Add(Diagnostic{
		Section: "Runtime",
		Name:    engineLabel + " CLI",
		Value:   firstOutputLine(versionOutput),
		Status:  DiagnosticOK,
		Detail:  "executable: " + enginePath,
	})

	daemonContext, cancelDaemon := withDiagnosticTimeout(ctx, dependencies)
	daemonOutput, daemonErr := dependencies.runner.Run(
		daemonContext,
		enginePath,
		"info",
		"--format",
		"{{.ServerVersion}}",
	)
	cancelDaemon()
	if daemonErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    engineLabel + " daemon",
			Value:   "unreachable",
			Status:  DiagnosticError,
			Detail:  startContainerEngineDetail(cfg.engine),
		})
		return
	}
	collection.report.Add(Diagnostic{
		Section: "Runtime",
		Name:    engineLabel + " daemon",
		Value:   "reachable (server " + firstOutputLine(daemonOutput) + ")",
		Status:  DiagnosticOK,
	})

	inspectContext, cancelInspect := withDiagnosticTimeout(ctx, dependencies)
	inspectOutput, inspectErr := dependencies.runner.Run(
		inspectContext,
		enginePath,
		"image",
		"inspect",
		cfg.image,
	)
	cancelInspect()
	if inspectErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "image availability",
			Value:   "missing",
			Status:  DiagnosticError,
			Detail: "The selected image is not available locally. Diagnostics will " +
				"not pull it; run 'scbolt install docker' explicitly.",
		})
		return
	}
	inspection, decodeErr := decodeDockerInspection(inspectOutput)
	if decodeErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "image availability",
			Value:   "unreadable metadata",
			Status:  DiagnosticError,
			Detail:  "The container engine returned invalid image metadata.",
		})
		return
	}
	collection.image = &inspection
	collection.report.Add(Diagnostic{
		Section: "Backend",
		Name:    "image availability",
		Value:   "available",
		Status:  DiagnosticOK,
	})
	collectDockerImageDiagnostics(collection, inspection)
}

func collectDockerImageDiagnostics(
	collection *diagnosticCollection,
	inspection dockerImageInspection,
) {
	platform := inspection.OperatingSys + "/" + normalizeArchitecture(inspection.Architecture)
	platformStatus := DiagnosticOK
	platformDetail := ""
	if !strings.EqualFold(inspection.OperatingSys, "linux") {
		platformStatus = DiagnosticError
		platformDetail = "The scBOLT container pipeline requires a Linux image."
	}
	collection.report.Add(Diagnostic{
		Section: "Backend",
		Name:    "image platform",
		Value:   platform,
		Status:  platformStatus,
		Detail:  platformDetail,
	})

	hostArchitecture := normalizeArchitecture(collection.host.Architecture)
	imageArchitecture := normalizeArchitecture(inspection.Architecture)
	if hostArchitecture == imageArchitecture {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "architecture compatibility",
			Value:   "native (" + imageArchitecture + ")",
			Status:  DiagnosticOK,
		})
	} else {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "architecture compatibility",
			Value:   hostArchitecture + " host, " + imageArchitecture + " image",
			Status:  DiagnosticWarning,
			Detail: "Container execution requires architecture emulation and may be " +
				"slower. Docker still fixes the container software environment.",
		})
	}

	digest := dockerImageDigest(inspection.RepoDigests)
	if digest == "" {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "image digest",
			Value:   "unavailable",
			Status:  DiagnosticWarning,
			Detail:  "Use a repository digest when exact image identity is required.",
		})
	} else {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "image digest",
			Value:   digest,
			Status:  DiagnosticOK,
		})
	}
}

func decodeDockerInspection(output []byte) (dockerImageInspection, error) {
	var records []dockerInspectRecord
	if err := json.Unmarshal(output, &records); err != nil || len(records) == 0 {
		if err == nil {
			err = fmt.Errorf("empty image inspection")
		}
		return dockerImageInspection{}, err
	}
	record := records[0]
	environment := make(map[string]string)
	for _, assignment := range record.Config.Environment {
		name, value, found := strings.Cut(assignment, "=")
		if found {
			environment[name] = value
		}
	}
	return dockerImageInspection{
		ID:           record.ID,
		OperatingSys: record.OperatingSys,
		Architecture: record.Architecture,
		RepoDigests:  append([]string{}, record.RepoDigests...),
		Environment:  environment,
	}, nil
}

func dockerImageDigest(repoDigests []string) string {
	for _, repoDigest := range repoDigests {
		_, digest, found := strings.Cut(repoDigest, "@")
		if found && strings.HasPrefix(digest, "sha256:") {
			return digest
		}
	}
	return ""
}

func collectDockerMountDiagnostics(
	collection *diagnosticCollection,
	cfg config,
	dependencies diagnosticDependencies,
) {
	workingDirectory, _ := dependencies.workingDir()
	mountRoots := []string{workingDirectory}
	if projectFile := findProjectFile(workingDirectory); projectFile != "" {
		mountRoots = append(mountRoots, filepath.Dir(projectFile))
	}
	if collection.config.params.value != "" {
		mountRoots = append(mountRoots, filepath.Dir(collection.config.params.value))
	}
	for _, mount := range strings.Fields(cfg.containerMounts) {
		if !filepath.IsAbs(mount) {
			mount = filepath.Join(workingDirectory, mount)
		}
		mountRoots = append(mountRoots, mount)
	}

	if collection.config.projectSelected {
		collection.report.Add(dockerMountDiagnostic(
			"project directory mount",
			collection.config.projectDir.value,
			mountRoots,
		))
	} else {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "project directory mount",
			Value:   "not required",
			Status:  DiagnosticOK,
		})
	}
	collection.report.Add(dockerMountDiagnostic(
		"resources directory mount",
		collection.config.resourcesDir.value,
		mountRoots,
	))
}

func dockerMountDiagnostic(name string, path string, roots []string) Diagnostic {
	status, detail := directoryStatus(path)
	if status == DiagnosticError {
		return Diagnostic{
			Section: "Backend",
			Name:    name,
			Value:   "unavailable",
			Status:  DiagnosticError,
			Detail:  detail,
		}
	}
	for _, root := range roots {
		if pathWithinRoot(path, root) {
			return Diagnostic{
				Section: "Backend",
				Name:    name,
				Value:   "available",
				Status:  DiagnosticOK,
				Detail:  path,
			}
		}
	}
	return Diagnostic{
		Section: "Backend",
		Name:    name,
		Value:   "not mounted",
		Status:  DiagnosticError,
		Detail: "The path is outside the automatic Docker mounts. Add it to " +
			"SCBOLT_CONTAINER_MOUNTS.",
	}
}

func pathWithinRoot(path string, root string) bool {
	path, pathErr := filepath.Abs(path)
	root, rootErr := filepath.Abs(root)
	if pathErr != nil || rootErr != nil {
		return false
	}
	relative, err := filepath.Rel(root, path)
	return err == nil && relative != ".." &&
		!strings.HasPrefix(relative, ".."+string(filepath.Separator))
}

func collectLocalDiagnostics(
	ctx context.Context,
	collection *diagnosticCollection,
	cfg config,
	dependencies diagnosticDependencies,
) {
	collection.report.Add(Diagnostic{
		Section: "Backend",
		Name:    "selected backend",
		Value:   cfg.backend,
		Status:  DiagnosticOK,
	})
	if strings.ToLower(collection.host.OperatingSystem) != "linux" {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "native execution",
			Value:   "unsupported on " + displayOperatingSystem(collection.host.OperatingSystem),
			Status:  DiagnosticError,
			Detail:  "Use the Docker backend on macOS and Windows.",
		})
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    "local runtime",
			Value:   "not checked",
			Status:  DiagnosticWarning,
			Detail:  "Native runtime checks are only supported on Linux.",
		})
		return
	}
	if normalizeArchitecture(collection.host.Architecture) != "amd64" {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "native execution",
			Value:   "unsupported architecture",
			Status:  DiagnosticError,
			Detail:  "Native execution is currently validated on linux/amd64; use Docker as an alternative.",
		})
		return
	}
	collection.report.Add(Diagnostic{
		Section: "Backend",
		Name:    "native execution",
		Value:   "supported (linux/amd64)",
		Status:  DiagnosticOK,
	})

	root, rootErr := dependencies.root()
	if rootErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "scBOLT source tree",
			Value:   "unavailable",
			Status:  DiagnosticError,
			Detail:  "Set SCBOLT_ROOT or reinstall the local launcher from a scBOLT checkout.",
		})
	} else {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "scBOLT source tree",
			Value:   root,
			Status:  DiagnosticOK,
		})
	}

	managerName := configuredEnvironmentManager(cfg.backend, dependencies.getenv)
	managerPath, managerErr := dependencies.runner.LookPath(managerName)
	if managerErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "environment manager",
			Value:   "unavailable (" + managerName + ")",
			Status:  DiagnosticError,
			Detail:  "Install or configure the selected " + cfg.backend + " backend.",
		})
		return
	}
	managerContext, cancelManager := withDiagnosticTimeout(ctx, dependencies)
	managerOutput, managerRunErr := dependencies.runner.Run(
		managerContext,
		managerPath,
		"--version",
	)
	cancelManager()
	if managerRunErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "environment manager",
			Value:   managerPath,
			Status:  DiagnosticError,
			Detail:  "The configured environment manager could not be executed.",
		})
		return
	}
	collection.report.Add(Diagnostic{
		Section: "Backend",
		Name:    "environment manager",
		Value:   firstOutputLine(managerOutput),
		Status:  DiagnosticOK,
		Detail:  "executable: " + managerPath,
	})

	environments, environmentsErr := diagnosticManagedEnvironments(
		ctx,
		managerPath,
		dependencies,
	)
	if environmentsErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "runtime environments",
			Value:   "unavailable",
			Status:  DiagnosticError,
			Detail:  "The environment manager could not list installed environments.",
		})
		return
	}
	missing := make([]string, 0)
	for _, suffix := range installEnvironmentSuffixes {
		name := "scbolt-" + suffix
		if _, found := environments[name]; !found {
			missing = append(missing, name)
		}
	}
	if len(missing) > 0 {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "runtime environments",
			Value: fmt.Sprintf(
				"%d/%d available",
				len(installEnvironmentSuffixes)-len(missing),
				len(installEnvironmentSuffixes),
			),
			Status: DiagnosticError,
			Detail: "Missing: " + strings.Join(missing, ", ") + ". Run 'scbolt install " +
				cfg.backend + " --all' to install them.",
		})
	} else {
		collection.report.Add(Diagnostic{
			Section: "Backend",
			Name:    "runtime environments",
			Value: fmt.Sprintf(
				"%d/%d available",
				len(installEnvironmentSuffixes),
				len(installEnvironmentSuffixes),
			),
			Status: DiagnosticOK,
		})
	}

	systemPrefix, found := environments[systemEnvironment]
	if !found {
		return
	}
	collectLocalRuntimeTools(ctx, collection, systemPrefix, dependencies)
}

func collectLocalRuntimeTools(
	ctx context.Context,
	collection *diagnosticCollection,
	systemPrefix string,
	dependencies diagnosticDependencies,
) {
	makePath := filepath.Join(systemPrefix, "bin", executableFile("make"))
	bashPath := filepath.Join(systemPrefix, "bin", executableFile("bash"))
	makeContext, cancelMake := withDiagnosticTimeout(ctx, dependencies)
	makeOutput, makeErr := dependencies.runner.Run(makeContext, makePath, "--version")
	cancelMake()
	if makeErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    "GNU Make",
			Value:   "unavailable",
			Status:  DiagnosticError,
			Detail:  "GNU Make >= 4.3 is required in scbolt-system.",
		})
	} else {
		version := firstOutputLine(makeOutput)
		status := DiagnosticOK
		detail := ""
		if !supportedMakeVersion(version) {
			status = DiagnosticError
			detail = "GNU Make >= 4.3 is required."
		}
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    "GNU Make",
			Value:   version,
			Status:  status,
			Detail:  detail,
		})
	}

	bashContext, cancelBash := withDiagnosticTimeout(ctx, dependencies)
	bashOutput, bashErr := dependencies.runner.Run(bashContext, bashPath, "--version")
	cancelBash()
	if bashErr != nil {
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    "Bash",
			Value:   "unavailable",
			Status:  DiagnosticError,
			Detail:  "Bash is required in scbolt-system for the local pipeline runtime.",
		})
	} else {
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    "Bash",
			Value:   firstOutputLine(bashOutput),
			Status:  DiagnosticOK,
		})
	}

	utilities := []string{"awk", "cat", "curl", "find", "grep", "gzip", "sed", "tar", "wget"}
	missing := make([]string, 0)
	for _, utility := range utilities {
		path := filepath.Join(systemPrefix, "bin", executableFile(utility))
		if !isExecutable(path) {
			missing = append(missing, utility)
		}
	}
	if len(missing) > 0 {
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    "GNU utilities",
			Value:   "incomplete",
			Status:  DiagnosticError,
			Detail:  "Missing from scbolt-system: " + strings.Join(missing, ", ") + ".",
		})
	} else {
		collection.report.Add(Diagnostic{
			Section: "Runtime",
			Name:    "GNU utilities",
			Value:   "available",
			Status:  DiagnosticOK,
			Detail:  strings.Join(utilities, ", "),
		})
	}
}

func configuredEnvironmentManager(
	backend string,
	getenv func(string) string,
) string {
	if configured := strings.TrimSpace(getenv("SCBOLT_ENV_MANAGER")); configured != "" {
		return configured
	}
	if backend == "conda" {
		if configured := strings.TrimSpace(getenv("CONDA_EXE")); configured != "" {
			return configured
		}
	}
	return backend
}

func diagnosticManagedEnvironments(
	ctx context.Context,
	manager string,
	dependencies diagnosticDependencies,
) (map[string]string, error) {
	jsonContext, cancelJSON := withDiagnosticTimeout(ctx, dependencies)
	output, err := dependencies.runner.Run(jsonContext, manager, "env", "list", "--json")
	cancelJSON()
	if err == nil {
		if environments, ok := decodeManagedEnvironmentList(output); ok {
			return environments, nil
		}
	}
	plainContext, cancelPlain := withDiagnosticTimeout(ctx, dependencies)
	output, err = dependencies.runner.Run(plainContext, manager, "env", "list")
	cancelPlain()
	if err != nil {
		return nil, err
	}
	environments := make(map[string]string)
	for _, line := range strings.Split(string(output), "\n") {
		fields := strings.Fields(line)
		if len(fields) == 0 || strings.HasPrefix(fields[0], "#") {
			continue
		}
		prefix := filepath.Clean(fields[len(fields)-1])
		name := fields[0]
		if name == "*" || filepath.IsAbs(name) || strings.HasPrefix(name, ".") {
			name = filepath.Base(prefix)
		}
		environments[name] = prefix
	}
	return environments, nil
}

func supportedMakeVersion(version string) bool {
	match := makeVersionPattern.FindStringSubmatch(version)
	if len(match) != 3 {
		return false
	}
	major, _ := strconv.Atoi(match[1])
	minor, _ := strconv.Atoi(match[2])
	return major > 4 || (major == 4 && minor >= 3)
}

func firstOutputLine(output []byte) string {
	line, _, _ := strings.Cut(strings.TrimSpace(string(output)), "\n")
	line = strings.TrimSpace(line)
	if line == "" {
		return "available"
	}
	if len(line) > 200 {
		return line[:200] + "..."
	}
	return line
}

func containerEngineLabel(engine string) string {
	if strings.EqualFold(filepath.Base(engine), "podman") {
		return "Podman"
	}
	return "Docker"
}

func startContainerEngineDetail(engine string) string {
	if strings.EqualFold(filepath.Base(engine), "podman") {
		return "Start the Podman service and run this command again."
	}
	return "Start Docker or Docker Desktop and run this command again."
}
