package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
)

type installedCompletion struct {
	shell string
	path  string
}

type installRequest struct {
	installAll           bool
	targetRequested      bool
	assumeYes            bool
	backendRequested     bool
	backend              string
	selectedEnvironments []string
	ignoredEnvironments  []string
}

var installBackendNames = []string{
	"conda",
	"mamba",
	"micromamba",
	"docker",
}

var installEnvironmentSuffixes = []string{
	"system",
	"align",
	"bonesis",
	"cellrank",
	"core",
	"cotan",
	"fastq",
	"potency",
	"scboolseq",
	"stream",
	"velocity",
	"velocyto",
}

func runLauncherBootstrap(cfg config) error {
	if err := installLauncher(); err != nil {
		return err
	}
	if hasConfiguredBackend() {
		return nil
	}
	if !isTerminal(os.Stdin) {
		fmt.Println()
		fmt.Println("Install a runtime backend with: scbolt install <backend>")
		return nil
	}

	fmt.Println()
	backend, err := promptInstallBackend(bufio.NewReader(os.Stdin), cfg.backend)
	if err != nil {
		return err
	}
	return runInstall(cfg, []string{backend})
}

func launcherNeedsBootstrap() (bool, error) {
	current, err := os.Executable()
	if err != nil {
		return false, fmt.Errorf("cannot locate launcher executable: %w", err)
	}
	if resolved, resolveErr := filepath.EvalSymlinks(current); resolveErr == nil {
		current = resolved
	}
	destination, err := launcherInstallPath()
	if err != nil {
		return false, err
	}
	return launcherInvocationNeedsBootstrap(current, destination), nil
}

func launcherInvocationNeedsBootstrap(current string, destination string) bool {
	if sameFile(current, destination) {
		return false
	}
	return filepath.Base(current) != executableName()
}

func hasConfiguredBackend() bool {
	backend := readConfigVariable(userConfigPath(), "BACKEND")
	return isInstallBackend(backend) || readLegacyBackend() != ""
}

func runInstall(cfg config, arguments []string) error {
	request, err := parseInstallRequest(arguments)
	if err != nil {
		return err
	}
	if request.backendRequested {
		cfg.backend = request.backend
		cfg.backendSource = "cli"
	}
	for _, environment := range request.ignoredEnvironments {
		printWarning("unsupported environment ignored: " + environment)
	}

	reader := bufio.NewReader(os.Stdin)
	if !request.backendRequested {
		if !isTerminal(os.Stdin) {
			return errors.New(
				"backend required in non-interactive mode; " +
					"use scbolt install <backend>",
			)
		}
		backend, promptErr := promptInstallBackend(reader, cfg.backend)
		if promptErr != nil {
			return promptErr
		}
		cfg.backend = backend
		cfg.backendSource = "install"
	}

	if cfg.backend == "docker" {
		if err := installDockerBackend(cfg); err != nil {
			return err
		}
		if request.targetRequested || request.installAll {
			printWarning(
				"Docker image contains prebuilt scBOLT environments; " +
					"local --env selections were ignored.",
			)
		}
		return nil
	}

	root, err := scboltRoot()
	if err != nil {
		return err
	}
	configuration := map[string]string{
		"BACKEND":     cfg.backend,
		"SCBOLT_ROOT": filepath.ToSlash(root),
	}
	if err := installConfiguration(configuration); err != nil {
		return err
	}
	if len(request.selectedEnvironments) == 0 {
		return nil
	}

	manager, err := environmentManager(cfg.backend)
	if err != nil {
		return err
	}
	return installLocalEnvironments(
		root,
		cfg.backend,
		manager,
		request,
		reader,
	)
}

func parseInstallRequest(arguments []string) (installRequest, error) {
	request := installRequest{}
	known := make(map[string]bool, len(installEnvironmentSuffixes))
	for _, environment := range installEnvironmentSuffixes {
		known[environment] = true
	}

	for index := 0; index < len(arguments); index++ {
		argument := arguments[index]
		valueFor := func(option string) (string, error) {
			if strings.HasPrefix(argument, option+"=") {
				value := strings.TrimSpace(strings.TrimPrefix(argument, option+"="))
				if value == "" {
					return "", fmt.Errorf("missing value for %s", option)
				}
				return value, nil
			}
			if index+1 >= len(arguments) {
				return "", fmt.Errorf("missing value for %s", option)
			}
			index++
			value := strings.TrimSpace(arguments[index])
			if value == "" {
				return "", fmt.Errorf("missing value for %s", option)
			}
			return value, nil
		}

		switch {
		case argument == "--all":
			if request.targetRequested {
				return request, errors.New(
					"use either --all or explicit targets, not both",
				)
			}
			request.installAll = true
		case argument == "--env" || strings.HasPrefix(argument, "--env="):
			if request.installAll {
				return request, errors.New(
					"use either --all or explicit targets, not both",
				)
			}
			value, err := valueFor("--env")
			if err != nil {
				return request, err
			}
			if known[value] {
				request.selectedEnvironments = append(
					request.selectedEnvironments,
					value,
				)
			} else {
				request.ignoredEnvironments = append(
					request.ignoredEnvironments,
					value,
				)
			}
			request.targetRequested = true
		case argument == "--backend" || strings.HasPrefix(argument, "--backend="):
			value, err := valueFor("--backend")
			if err != nil {
				return request, err
			}
			if err := setInstallBackend(&request, value); err != nil {
				return request, err
			}
		case installLauncherOptionTakesValue(argument):
			option := strings.SplitN(argument, "=", 2)[0]
			if _, err := valueFor(option); err != nil {
				return request, err
			}
		case argument == "--help" || argument == "-h" || argument == "help":
			fmt.Print(launcherInstallHelp)
			return request, &reportedError{status: 0}
		case isLauncherAssignment(argument):
			name, value, _ := strings.Cut(argument, "=")
			if strings.TrimSpace(value) == "" {
				return request, fmt.Errorf("missing value for %s", name)
			}
			if strings.EqualFold(strings.TrimSpace(name), "BACKEND") {
				if err := setInstallBackend(&request, value); err != nil {
					return request, err
				}
			}
		case isInstallBackend(argument):
			if err := setInstallBackend(&request, argument); err != nil {
				return request, err
			}
		default:
			if !strings.HasPrefix(argument, "-") && !strings.Contains(argument, "=") {
				return request, fmt.Errorf("unsupported backend: %s", argument)
			}
			return request, fmt.Errorf("unsupported install option: %s", argument)
		}
	}

	request.selectedEnvironments = uniqueStrings(request.selectedEnvironments)
	request.ignoredEnvironments = uniqueStrings(request.ignoredEnvironments)
	if request.installAll {
		request.selectedEnvironments = append(
			[]string{},
			installEnvironmentSuffixes...,
		)
		request.assumeYes = true
	} else if request.targetRequested {
		request.assumeYes = true
	} else {
		request.selectedEnvironments = append(
			[]string{},
			installEnvironmentSuffixes...,
		)
	}
	return request, nil
}

func setInstallBackend(request *installRequest, value string) error {
	backend := strings.ToLower(strings.TrimSpace(value))
	if !isInstallBackend(backend) {
		return fmt.Errorf("unsupported backend: %s", value)
	}
	if request.backendRequested && request.backend != backend {
		return fmt.Errorf(
			"conflicting install backends: %s and %s",
			request.backend,
			backend,
		)
	}
	request.backend = backend
	request.backendRequested = true
	return nil
}

func isInstallBackend(value string) bool {
	for _, backend := range installBackendNames {
		if value == backend {
			return true
		}
	}
	return false
}

func installLauncherOptionTakesValue(argument string) bool {
	name := strings.SplitN(argument, "=", 2)[0]
	switch name {
	case "--scbolt-image",
		"--scbolt-container-engine",
		"--scbolt-container-args",
		"--scbolt-container-mounts":
		return true
	default:
		return false
	}
}

func uniqueStrings(values []string) []string {
	unique := make([]string, 0, len(values))
	seen := make(map[string]bool, len(values))
	for _, value := range values {
		if !seen[value] {
			seen[value] = true
			unique = append(unique, value)
		}
	}
	return unique
}

func promptInstallBackend(reader *bufio.Reader, current string) (string, error) {
	choices := installBackendNames
	defaultChoice := 1
	for index, choice := range choices {
		if choice == current {
			defaultChoice = index + 1
			break
		}
	}

	fmt.Println("Select the scBOLT backend to install:")
	for index, choice := range choices {
		fmt.Printf("  %d) %s\n", index+1, choice)
	}
	fmt.Printf("Backend (%s): ", promptChoiceLayout(defaultChoice, len(choices)))
	value, err := reader.ReadString('\n')
	if err != nil && !errors.Is(err, io.EOF) {
		return "", fmt.Errorf("cannot read backend selection: %w", err)
	}
	value = strings.TrimSpace(value)
	if value == "" {
		fmt.Println()
		return choices[defaultChoice-1], nil
	}
	for index, choice := range choices {
		if value == fmt.Sprint(index+1) || value == choice {
			fmt.Println()
			return choice, nil
		}
	}
	return "", fmt.Errorf("unsupported backend: %s", value)
}

func promptChoiceLayout(defaultChoice int, choices int) string {
	parts := make([]string, choices)
	for index := range parts {
		parts[index] = fmt.Sprint(index + 1)
		if index+1 == defaultChoice {
			parts[index] = "[" + parts[index] + "]"
		}
	}
	return strings.Join(parts, "/")
}

func installLauncher() error {
	if err := installCurrentExecutable(); err != nil {
		return err
	}
	completions, err := installCompletions()
	if err != nil {
		return err
	}
	printInstalledLauncher(completions)
	printSuccess("scBOLT launcher successfully installed.")
	return nil
}

func installConfiguration(configuration map[string]string) error {
	if err := updateUserConfig(configuration); err != nil {
		return err
	}
	fmt.Printf("Installed configuration: %s\n", userConfigPath())
	return nil
}

func printInstalledLauncher(completions []installedCompletion) {
	installedExecutable, _ := launcherInstallPath()
	fmt.Printf("Installed launcher: %s\n", installedExecutable)
	for _, completion := range completions {
		fmt.Printf(
			"Installed %s completion: %s\n",
			completion.shell,
			completion.path,
		)
	}
	printPathHint(filepath.Dir(installedExecutable))
	printCompletionHint(completions)
}

func installDockerBackend(cfg config) error {
	configuration := map[string]string{
		"BACKEND":                 "docker",
		"SCBOLT_CONTAINER_ENGINE": cfg.engine,
		"SCBOLT_IMAGE":            cfg.image,
	}
	if cfg.containerArgs != "" {
		configuration["SCBOLT_CONTAINER_ARGS"] = cfg.containerArgs
	}
	if cfg.containerMounts != "" {
		configuration["SCBOLT_CONTAINER_MOUNTS"] = cfg.containerMounts
	}
	if err := installConfiguration(configuration); err != nil {
		return err
	}
	if !truthy(os.Getenv("SCBOLT_INSTALL_SKIP_IMAGE")) {
		if _, err := exec.LookPath(cfg.engine); err != nil {
			return fmt.Errorf(
				"Docker backend requested but command not found: %s",
				cfg.engine,
			)
		}
		if !dockerImageExists(cfg.engine, cfg.image) {
			fmt.Printf("Pulling Docker image: %s\n", cfg.image)
			command := exec.Command(cfg.engine, "pull", cfg.image)
			command.Stdin = os.Stdin
			command.Stdout = os.Stdout
			command.Stderr = os.Stderr
			if err := command.Run(); err != nil {
				return fmt.Errorf("failed to pull Docker image %s: %w", cfg.image, err)
			}
		}
	}

	printSuccess("docker backend successfully installed.")
	return nil
}

func installLocalEnvironments(
	root string,
	backend string,
	manager string,
	request installRequest,
	reader *bufio.Reader,
) error {
	installed, err := listManagedEnvironments(manager)
	if err != nil {
		return fmt.Errorf("%s backend failed to initialize: %w", backend, err)
	}

	for _, suffix := range request.selectedEnvironments {
		name := "scbolt-" + suffix
		environmentFile := filepath.Join(root, "envs", "conda", suffix+".yml")
		if !exists(environmentFile) {
			return fmt.Errorf("missing environment file: %s", environmentFile)
		}

		if _, found := installed[name]; found {
			reinstall := request.assumeYes
			if !request.assumeYes {
				var promptErr error
				reinstall, promptErr = promptEnvironmentReinstall(
					reader,
					backend,
					name,
				)
				if promptErr != nil {
					return promptErr
				}
			}
			if !reinstall {
				printWarning(name + " not reinstalled.")
				fmt.Println()
				continue
			}

			fmt.Printf("Removing %s environment '%s'.\n", backend, name)
			if err := runQuietInstallCommand(
				exec.Command(manager, "remove", "--name", name, "--all", "--yes"),
			); err != nil {
				return fmt.Errorf("failed to remove %s: %w", name, err)
			}
		}

		fmt.Printf("Creating %s environment '%s'.\n", backend, name)
		fmt.Printf("Resolving %s environment '%s'.\n", backend, name)
		if err := runQuietInstallCommand(
			exec.Command(manager, "env", "create", "-f", environmentFile, "--yes"),
		); err != nil {
			return fmt.Errorf("failed to install %s: %w", name, err)
		}

		installed, err = listManagedEnvironments(manager)
		if err != nil {
			return fmt.Errorf("cannot verify %s: %w", name, err)
		}
		if _, found := installed[name]; !found {
			return fmt.Errorf("%s environment '%s' was not created", backend, name)
		}
		if err := configureInstalledEnvironment(
			root,
			backend,
			manager,
			name,
		); err != nil {
			return fmt.Errorf("failed to configure %s: %w", name, err)
		}
		printSuccess(name + " successfully installed.")
		fmt.Println()
	}
	return nil
}

func promptEnvironmentReinstall(
	reader *bufio.Reader,
	backend string,
	name string,
) (bool, error) {
	fmt.Printf("%s environment '%s' already exists.\n", backend, name)
	fmt.Printf("Do you want to reinstall %s environment '%s'? ([y]/n): ", backend, name)
	value, err := reader.ReadString('\n')
	if err != nil && !errors.Is(err, io.EOF) {
		return false, fmt.Errorf("cannot read environment selection: %w", err)
	}
	value = strings.ToLower(strings.TrimSpace(value))
	return value == "" || value == "y" || value == "yes", nil
}

func listManagedEnvironments(manager string) (map[string]string, error) {
	jsonCommand := exec.Command(manager, "env", "list", "--json")
	jsonOutput, jsonErr := jsonCommand.Output()
	if jsonErr == nil {
		if environments, ok := decodeManagedEnvironmentList(jsonOutput); ok {
			return environments, nil
		}
	}

	plainCommand := exec.Command(manager, "env", "list")
	plainOutput, plainErr := plainCommand.Output()
	if plainErr != nil {
		if jsonErr != nil {
			return nil, fmt.Errorf("could not list environments: %w", jsonErr)
		}
		return nil, fmt.Errorf("could not list environments: %w", plainErr)
	}

	environments := make(map[string]string)
	for _, line := range strings.Split(string(plainOutput), "\n") {
		fields := strings.Fields(line)
		if len(fields) == 0 || strings.HasPrefix(fields[0], "#") {
			continue
		}
		prefix := filepath.Clean(fields[len(fields)-1])
		if !exists(filepath.Join(prefix, "conda-meta")) {
			continue
		}
		name := fields[0]
		if name == "*" || filepath.IsAbs(name) || strings.HasPrefix(name, ".") {
			name = filepath.Base(prefix)
		}
		environments[name] = prefix
	}
	return environments, nil
}

func decodeManagedEnvironmentList(output []byte) (map[string]string, bool) {
	start := bytes.IndexByte(output, '{')
	end := bytes.LastIndexByte(output, '}')
	if start < 0 || end < start {
		return nil, false
	}
	var listing environmentList
	if err := json.Unmarshal(output[start:end+1], &listing); err != nil {
		return nil, false
	}
	environments := make(map[string]string, len(listing.Environments))
	for _, prefix := range listing.Environments {
		prefix = filepath.Clean(prefix)
		environments[filepath.Base(prefix)] = prefix
	}
	return environments, true
}

func configureInstalledEnvironment(
	root string,
	backend string,
	manager string,
	name string,
) error {
	if name == "scbolt-align" || name == systemEnvironment {
		return nil
	}
	const configureLibrary = `
import sysconfig
import sys
from pathlib import Path

lib_dir = Path(sys.argv[1]).resolve()
site_packages = Path(sysconfig.get_path("purelib"))
pth_file = site_packages / "scbolt-lib.pth"
pth_file.write_text(f"{lib_dir}\n", encoding="utf-8")
`
	arguments := []string{"run"}
	if backend == "conda" {
		arguments = append(arguments, "--no-capture-output")
	}
	arguments = append(
		arguments,
		"-n",
		name,
		"python",
		"-c",
		configureLibrary,
		filepath.Join(root, "lib"),
	)
	return runQuietInstallCommand(exec.Command(manager, arguments...))
}

func runQuietInstallCommand(command *exec.Cmd) error {
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	command.Stdin = os.Stdin
	command.Stdout = &stdout
	command.Stderr = &stderr
	result, err := runManagedProcess(command)
	if result.status != 0 || err != nil {
		if stdout.Len() > 0 {
			_, _ = os.Stderr.Write(stdout.Bytes())
		}
		if stderr.Len() > 0 {
			_, _ = os.Stderr.Write(stderr.Bytes())
		}
	}
	if result.interrupted {
		fmt.Fprintln(os.Stderr)
		fmt.Fprintln(os.Stderr, "✗ installation canceled by user.")
		return &reportedError{status: 130}
	}
	if err != nil {
		return err
	}
	if result.status != 0 {
		return fmt.Errorf(
			"%s exited with status %d",
			filepath.Base(command.Path),
			result.status,
		)
	}
	return nil
}

func installCurrentExecutable() error {
	source := os.Getenv("SCBOLT_LAUNCHER_INSTALL_SOURCE")
	if source == "" {
		var err error
		source, err = os.Executable()
		if err != nil {
			return fmt.Errorf("cannot locate launcher executable: %w", err)
		}
	}
	if resolved, err := filepath.EvalSymlinks(source); err == nil {
		source = resolved
	}
	destination, err := launcherInstallPath()
	if err != nil {
		return err
	}
	if sameFile(source, destination) {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(destination), 0o755); err != nil {
		return fmt.Errorf("cannot create launcher directory: %w", err)
	}
	return copyExecutable(source, destination)
}

func launcherInstallPath() (string, error) {
	if directory := os.Getenv("SCBOLT_INSTALL_BIN_DIR"); directory != "" {
		return filepath.Join(directory, executableName()), nil
	}
	directory, err := defaultLauncherBinDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(directory, executableName()), nil
}

func executableName() string {
	if runtime.GOOS == "windows" {
		return "scbolt.exe"
	}
	return "scbolt"
}

func copyExecutable(source string, destination string) error {
	input, err := os.Open(source)
	if err != nil {
		return fmt.Errorf("cannot open launcher executable: %w", err)
	}
	defer input.Close()

	temporary, err := os.CreateTemp(filepath.Dir(destination), ".scbolt-*")
	if err != nil {
		return fmt.Errorf("cannot create temporary launcher: %w", err)
	}
	temporaryPath := temporary.Name()
	defer os.Remove(temporaryPath)

	if _, err := io.Copy(temporary, input); err != nil {
		temporary.Close()
		return fmt.Errorf("cannot copy launcher executable: %w", err)
	}
	if err := temporary.Chmod(0o755); err != nil {
		temporary.Close()
		return fmt.Errorf("cannot set launcher permissions: %w", err)
	}
	if err := temporary.Close(); err != nil {
		return fmt.Errorf("cannot finalize launcher executable: %w", err)
	}
	if err := replaceInstalledExecutable(temporaryPath, destination); err != nil {
		return fmt.Errorf("cannot install launcher executable: %w", err)
	}
	return nil
}

func sameFile(left string, right string) bool {
	leftInfo, leftErr := os.Stat(left)
	rightInfo, rightErr := os.Stat(right)
	return leftErr == nil && rightErr == nil && os.SameFile(leftInfo, rightInfo)
}

func updateUserConfig(assignments map[string]string) error {
	path := userConfigPath()
	if path == "" {
		return fmt.Errorf("cannot determine scBOLT configuration path")
	}
	lines := make([]string, 0)
	if file, err := os.Open(path); err == nil {
		scanner := bufio.NewScanner(file)
		for scanner.Scan() {
			lines = append(lines, scanner.Text())
		}
		file.Close()
		if err := scanner.Err(); err != nil {
			return fmt.Errorf("cannot read scBOLT configuration: %w", err)
		}
	} else if !os.IsNotExist(err) {
		return fmt.Errorf("cannot read scBOLT configuration: %w", err)
	}

	written := make(map[string]bool)
	for index, line := range lines {
		for name, value := range assignments {
			if configAssignmentName(line) == name {
				lines[index] = fmt.Sprintf("%s = %s", name, value)
				written[name] = true
			}
		}
	}
	if len(lines) == 0 {
		lines = append(lines, "# scBOLT user configuration.")
	}
	for _, name := range sortedKeys(assignments) {
		if !written[name] {
			lines = append(lines, fmt.Sprintf("%s = %s", name, assignments[name]))
		}
	}

	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return fmt.Errorf("cannot create scBOLT configuration directory: %w", err)
	}
	content := strings.Join(lines, "\n") + "\n"
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		return fmt.Errorf("cannot write scBOLT configuration: %w", err)
	}
	return nil
}

func configAssignmentName(line string) string {
	line = strings.TrimSpace(stripComment(line))
	for _, operator := range []string{":=", "?=", "="} {
		if index := strings.Index(line, operator); index >= 0 {
			return strings.TrimSpace(line[:index])
		}
	}
	return ""
}

func sortedKeys(values map[string]string) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func installCompletions() ([]installedCompletion, error) {
	paths, err := completionInstallPaths()
	if err != nil {
		return nil, err
	}
	installed := make([]installedCompletion, 0, len(paths))
	for shell, path := range paths {
		script, scriptErr := completionScript(shell)
		if scriptErr != nil {
			return nil, scriptErr
		}
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			return nil, fmt.Errorf("cannot create completion directory: %w", err)
		}
		if err := os.WriteFile(path, []byte(script), 0o644); err != nil {
			return nil, fmt.Errorf("cannot install %s completion: %w", shell, err)
		}
		installed = append(installed, installedCompletion{shell: shell, path: path})
	}
	sort.Slice(installed, func(left int, right int) bool {
		return installed[left].shell < installed[right].shell
	})
	return installed, nil
}
