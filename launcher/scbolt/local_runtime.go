package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
)

const systemEnvironment = "scbolt-system"

type localRuntime struct {
	root          string
	config        config
	backend       string
	manager       string
	prefix        string
	makePath      string
	bashPath      string
	systemBinPath string
	projectRoot   string
}

type processResult struct {
	status      int
	interrupted bool
}

type environmentList struct {
	Environments []string `json:"envs"`
}

func newLocalRuntime(root string, cfg config) (*localRuntime, error) {
	backend := cfg.backend
	if os.Getenv("SCBOLT_IN_DOCKER") == "true" {
		backend = "micromamba"
	}

	manager, err := environmentManager(backend)
	if err != nil {
		return nil, err
	}
	prefix, err := systemEnvironmentPrefix(manager, backend)
	if err != nil {
		return nil, err
	}
	local := &localRuntime{
		root:          root,
		config:        cfg,
		backend:       backend,
		manager:       manager,
		prefix:        prefix,
		systemBinPath: filepath.Join(prefix, "bin"),
	}
	local.makePath = filepath.Join(local.systemBinPath, executableFile("make"))
	local.bashPath = filepath.Join(local.systemBinPath, executableFile("bash"))
	for _, required := range []string{local.makePath, local.bashPath} {
		if !isExecutable(required) {
			return nil, fmt.Errorf(
				"%s is missing from %s; reinstall the scbolt-system environment",
				filepath.Base(required),
				systemEnvironment,
			)
		}
	}
	return local, nil
}

func executableFile(name string) string {
	if runtime.GOOS == "windows" {
		return name + ".exe"
	}
	return name
}

func environmentManager(backend string) (string, error) {
	if configured := os.Getenv("SCBOLT_ENV_MANAGER"); configured != "" {
		if resolved, err := exec.LookPath(configured); err == nil {
			return resolved, nil
		}
		return "", fmt.Errorf("command not found: %s", configured)
	}
	if backend == "conda" {
		if conda := os.Getenv("CONDA_EXE"); conda != "" && isExecutable(conda) {
			return conda, nil
		}
	}
	manager, err := exec.LookPath(backend)
	if err != nil {
		return "", fmt.Errorf(
			"%s backend failed to initialize: command not found: %s",
			backend,
			backend,
		)
	}
	return manager, nil
}

func systemEnvironmentPrefix(manager string, backend string) (string, error) {
	if configured := os.Getenv("SCBOLT_SYSTEM_PREFIX"); configured != "" {
		if validSystemEnvironmentPrefix(configured) {
			return filepath.Clean(configured), nil
		}
		return "", fmt.Errorf(
			"invalid SCBOLT_SYSTEM_PREFIX: %s",
			configured,
		)
	}

	for _, candidate := range conventionalSystemPrefixes(manager) {
		if validSystemEnvironmentPrefix(candidate) {
			return candidate, nil
		}
	}

	command := exec.Command(manager, "env", "list", "--json")
	output, err := command.Output()
	if err == nil {
		var listing environmentList
		start := bytes.IndexByte(output, '{')
		end := bytes.LastIndexByte(output, '}')
		if start >= 0 && end >= start && json.Unmarshal(output[start:end+1], &listing) == nil {
			for _, candidate := range listing.Environments {
				if filepath.Base(filepath.Clean(candidate)) == systemEnvironment &&
					validSystemEnvironmentPrefix(candidate) {
					return filepath.Clean(candidate), nil
				}
			}
		}
	}

	command = exec.Command(manager, "env", "list")
	output, plainErr := command.Output()
	if plainErr == nil {
		for _, line := range strings.Split(string(output), "\n") {
			fields := strings.Fields(line)
			if len(fields) == 0 {
				continue
			}
			candidate := fields[len(fields)-1]
			if filepath.Base(filepath.Clean(candidate)) == systemEnvironment &&
				validSystemEnvironmentPrefix(candidate) {
				return filepath.Clean(candidate), nil
			}
		}
	}

	return "", fmt.Errorf(
		"%s environment not found for the %s backend; "+
			"run scbolt install %s --env=system",
		systemEnvironment,
		backend,
		backend,
	)
}

func conventionalSystemPrefixes(manager string) []string {
	candidates := make([]string, 0, 4)
	seen := make(map[string]bool)
	appendCandidate := func(candidate string) {
		candidate = filepath.Clean(candidate)
		if candidate != "." && !seen[candidate] {
			seen[candidate] = true
			candidates = append(candidates, candidate)
		}
	}
	if root := os.Getenv("MAMBA_ROOT_PREFIX"); root != "" {
		appendCandidate(filepath.Join(root, "envs", systemEnvironment))
	}
	for _, executable := range []string{manager, os.Getenv("CONDA_EXE")} {
		if executable == "" {
			continue
		}
		directory := filepath.Dir(executable)
		if base := filepath.Base(directory); base == "bin" || base == "condabin" {
			appendCandidate(filepath.Join(filepath.Dir(directory), "envs", systemEnvironment))
		}
	}
	return candidates
}

func validSystemEnvironmentPrefix(prefix string) bool {
	bin := filepath.Join(prefix, "bin")
	return isExecutable(filepath.Join(bin, executableFile("make"))) &&
		isExecutable(filepath.Join(bin, executableFile("bash")))
}

func isExecutable(path string) bool {
	info, err := os.Stat(path)
	if err != nil || info.IsDir() {
		return false
	}
	if runtime.GOOS == "windows" {
		return true
	}
	return info.Mode()&0o111 != 0
}

func (local *localRuntime) makeCommand(arguments ...string) *exec.Cmd {
	makefile := filepath.Join(local.root, "Makefile")
	commandArguments := append([]string{"-f", makefile}, arguments...)
	if os.Getenv("SCBOLT_IN_DOCKER") == "true" {
		commandArguments = append(commandArguments, "BACKEND=docker")
	}
	command := exec.Command(local.makePath, commandArguments...)
	includeProjectConfiguration := true
	for _, argument := range arguments {
		if argument == "DEFAULT_CONFIG=true" {
			includeProjectConfiguration = false
			break
		}
	}
	command.Env = local.runtimeEnvironment(includeProjectConfiguration)
	return command
}

func (local *localRuntime) environment() []string {
	return local.runtimeEnvironment(true)
}

func (local *localRuntime) runtimeEnvironment(
	includeProjectConfiguration bool,
) []string {
	environment := append([]string{}, os.Environ()...)
	workflowBackend := local.config.backend
	if os.Getenv("SCBOLT_IN_DOCKER") == "true" {
		workflowBackend = "docker"
	}
	values := map[string]string{
		"PATH":                               local.systemBinPath + string(os.PathListSeparator) + os.Getenv("PATH"),
		"SCBOLT_CLI":                         "true",
		"SCBOLT_DEFAULT_BACKEND":             workflowBackend,
		"SCBOLT_DEFAULT_BACKEND_SOURCE":      local.config.backendSource,
		"SCBOLT_ENV_MANAGER":                 local.manager,
		"SCBOLT_PUBLIC_PARAMETER_PARAMS":     "configuration",
		"SCBOLT_PUBLIC_PARAMETER_REFERENCES": "references",
		"SCBOLT_PUBLIC_PARAMETER_SPEC_FILE":  "spec_file",
		"SCBOLT_SHELL":                       local.bashPath,
		"SCBOLT_SYSTEM_BIN":                  local.systemBinPath,
	}
	if local.config.configurationPath != "" {
		values["PARAMS"] = local.config.configurationPath
	}
	if includeProjectConfiguration && local.config.configurationFormat == configurationYAML {
		values["SCBOLT_CONFIG_MODE"] = "true"
		values["SCBOLT_CONFIG"] = local.config.configurationPath
		for _, setting := range local.config.projectConfig.Environment() {
			values[setting.name] = setting.value
		}
	}
	for _, parameter := range yamlParameters {
		if parameter.makeVariable == "" {
			continue
		}
		name := parameter.makeVariable
		values["SCBOLT_PUBLIC_PARAMETER_"+name] = publicConfigurationKey(name)
	}
	if includeProjectConfiguration {
		conditions := configurationConditionNames(
			local.config.configurationPath,
			local.config.configurationFormat,
			local.config.projectConfig,
		)
		for key, parameter := range yamlParameters {
			if !parameter.condition {
				continue
			}
			for _, condition := range conditions {
				name := parameter.makeVariable + "_" + strings.ToUpper(condition)
				values["SCBOLT_PUBLIC_PARAMETER_"+name] = key + "." + strings.ToLower(condition)
			}
		}
	}
	if includeProjectConfiguration && local.config.projectConfig != nil {
		for _, setting := range local.config.projectConfig.Environment() {
			name := "SCBOLT_PUBLIC_PARAMETER_" + setting.name
			if _, found := values[name]; !found {
				values[name] = publicConfigurationKey(setting.name)
			}
		}
	}
	if local.projectRoot != "" {
		values["SCBOLT_PROJECT_ROOT"] = local.projectRoot
	}
	if local.backend == "conda" {
		values["CONDA_EXE"] = local.manager
	}
	for name, value := range values {
		environment = setEnvironmentValue(environment, name, value)
	}
	return environment
}

func setEnvironmentValue(environment []string, name string, value string) []string {
	prefix := name + "="
	for index, item := range environment {
		if strings.HasPrefix(item, prefix) {
			environment[index] = prefix + value
			return environment
		}
	}
	return append(environment, prefix+value)
}

func runManagedProcess(command *exec.Cmd) (processResult, error) {
	configureManagedProcess(command)
	if err := command.Start(); err != nil {
		return processResult{status: 1}, err
	}

	signals := make(chan os.Signal, 2)
	signal.Notify(signals, os.Interrupt, syscall.SIGTERM)
	var interrupted atomic.Bool
	done := make(chan struct{})
	go func() {
		defer close(done)
		for received := range signals {
			interrupted.Store(true)
			_ = signalManagedProcess(command, received)
		}
	}()

	err := command.Wait()
	signal.Stop(signals)
	close(signals)
	<-done
	if err == nil {
		return processResult{status: 0, interrupted: interrupted.Load()}, nil
	}
	var exitError *exec.ExitError
	if errors.As(err, &exitError) {
		status := exitError.ExitCode()
		if status < 0 {
			if interrupted.Load() {
				status = 130
			} else {
				status = 1
			}
		}
		return processResult{
			status:      status,
			interrupted: interrupted.Load(),
		}, nil
	}
	return processResult{status: 1, interrupted: interrupted.Load()}, err
}

var makeErrorLine = regexp.MustCompile(
	`^make(?:\[[0-9]+\])?: \*\*\* \[[^]]+\] Error [0-9]+\r?\n?$`,
)

type makeOutputWriter struct {
	mu              sync.Mutex
	destination     io.Writer
	pending         bytes.Buffer
	passthrough     bool
	hasOutput       bool
	lastByte        byte
	rule            bool
	stale           bool
	interrupted     bool
	terminated      bool
	timedOut        bool
	inferenceModule string
	summaryTail     []byte
}

const outputSummaryTailLimit = 4096

type makeOutputSummary struct {
	hasOutput       bool
	lastByte        byte
	rule            bool
	stale           bool
	interrupted     bool
	terminated      bool
	timedOut        bool
	inferenceModule string
}

func newMakeOutputWriter(destination io.Writer) *makeOutputWriter {
	return &makeOutputWriter{destination: destination}
}

func (writer *makeOutputWriter) Write(data []byte) (int, error) {
	writer.mu.Lock()
	defer writer.mu.Unlock()
	writer.observe(data)

	for _, character := range data {
		if writer.passthrough {
			if _, err := writer.destination.Write([]byte{character}); err != nil {
				return 0, err
			}
			if character == '\n' {
				writer.passthrough = false
			}
			continue
		}

		_ = writer.pending.WriteByte(character)
		pending := writer.pending.String()
		if character == '\n' {
			if !makeErrorLine.MatchString(pending) {
				if _, err := io.WriteString(writer.destination, pending); err != nil {
					return 0, err
				}
			}
			writer.pending.Reset()
			continue
		}

		if !strings.HasPrefix("make", pending) && !strings.HasPrefix(pending, "make") {
			if _, err := io.WriteString(writer.destination, pending); err != nil {
				return 0, err
			}
			writer.pending.Reset()
			writer.passthrough = true
		}
	}
	return len(data), nil
}

func (writer *makeOutputWriter) observe(data []byte) {
	if len(data) == 0 {
		return
	}
	writer.hasOutput = true
	writer.lastByte = data[len(data)-1]
	combined := make([]byte, 0, len(writer.summaryTail)+len(data))
	combined = append(combined, writer.summaryTail...)
	combined = append(combined, data...)
	text := string(combined)
	writer.rule = writer.rule || rulePattern.MatchString(text)
	writer.stale = writer.stale || stalePattern.MatchString(text)
	writer.interrupted = writer.interrupted || interruptPattern.MatchString(text)
	writer.terminated = writer.terminated || terminationPattern.MatchString(text)
	writer.timedOut = writer.timedOut || timeoutPattern.MatchString(text)
	if module := lastInferenceModule(text); module != "" {
		writer.inferenceModule = module
	}
	if len(combined) > outputSummaryTailLimit {
		combined = combined[len(combined)-outputSummaryTailLimit:]
	}
	writer.summaryTail = append([]byte{}, combined...)
}

func (writer *makeOutputWriter) flush() error {
	writer.mu.Lock()
	defer writer.mu.Unlock()
	if writer.pending.Len() == 0 {
		return nil
	}
	pending := writer.pending.String()
	writer.pending.Reset()
	if makeErrorLine.MatchString(pending) {
		return nil
	}
	_, err := io.WriteString(writer.destination, pending)
	return err
}

func (writer *makeOutputWriter) summary() makeOutputSummary {
	writer.mu.Lock()
	defer writer.mu.Unlock()
	return makeOutputSummary{
		hasOutput:       writer.hasOutput,
		lastByte:        writer.lastByte,
		rule:            writer.rule,
		stale:           writer.stale,
		interrupted:     writer.interrupted,
		terminated:      writer.terminated,
		timedOut:        writer.timedOut,
		inferenceModule: writer.inferenceModule,
	}
}
