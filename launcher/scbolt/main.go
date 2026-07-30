package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

const (
	defaultBackend = "conda"
)

var (
	launcherVersion = "dev"
	sourceRevision  = "unknown"
	defaultImage    = "ghcr.io/bnediction/scbolt:latest"
)

type config struct {
	backend             string
	backendSource       string
	image               string
	engine              string
	containerArgs       string
	containerMounts     string
	configurationPath   string
	configurationSource string
	configurationFormat configurationFormat
	projectConfig       *projectConfiguration
	settings            map[string]effectiveSetting
}

type effectiveSetting struct {
	value  string
	source string
}

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		if os.Getenv("SCBOLT_IN_DOCKER") == "true" {
			printLauncherHelp()
			return
		}
		bootstrap, err := launcherNeedsBootstrap()
		if err != nil {
			fatal(err)
		}
		if bootstrap {
			cfg, configErr := effectiveConfig(nil)
			if configErr != nil {
				fatal(configErr)
			}
			if bootstrapErr := runLauncherBootstrap(cfg); bootstrapErr != nil {
				fatal(bootstrapErr)
			}
			return
		}
		printLauncherHelp()
		return
	}
	if (isHelpToken(args[0]) || firstCommand(args) == "help") &&
		os.Getenv("SCBOLT_GENERATING_COMPLETION_MANIFEST") != "true" {
		printLauncherHelp()
		return
	}
	handled, commandErr := handleLauncherCommand(args)
	if commandErr != nil {
		fatal(commandErr)
	}
	if handled {
		return
	}
	if isVersionInvocation(args) {
		printLauncherVersion()
		return
	}
	if isCompletionInstallCommand(args) {
		if installErr := runInstall(config{}, installArgs(args)); installErr != nil {
			fatal(installErr)
		}
		return
	}

	cfg, err := effectiveConfig(args)
	if err != nil {
		fatal(err)
	}
	if cfg.configurationFormat == configurationLegacy &&
		firstCommand(args) != "diagnostics" &&
		os.Getenv("SCBOLT_IN_DOCKER") != "true" {
		printWarningTo(
			os.Stderr,
			"legacy Make parameter files are deprecated; use scbolt.yml",
		)
	}
	if firstCommand(args) == "diagnostics" {
		status, diagnosticsErr := runDiagnosticsCommand(
			context.Background(),
			cfg,
			args,
			os.Stdout,
			isTerminal(os.Stdout),
			defaultDiagnosticDependencies(),
		)
		if diagnosticsErr != nil {
			fmt.Fprintln(os.Stderr, diagnosticsErr)
		}
		os.Exit(status)
	}
	if firstCommand(args) == "init" {
		if initErr := runInit(cfg, args); initErr != nil {
			fatal(initErr)
		}
		return
	}

	if os.Getenv("SCBOLT_IN_DOCKER") == "true" {
		root, rootErr := scboltRoot()
		if rootErr != nil {
			fatal(rootErr)
		}
		exitLocal(root, cfg, args)
	}

	if isInstallCommand(args) {
		if installErr := runInstall(cfg, installArgs(args)); installErr != nil {
			fatal(installErr)
		}
		return
	}

	if cfg.backend == "docker" {
		execDocker(cfg, args)
		return
	}

	root, err := scboltRoot()
	if err != nil {
		fatal(err)
	}
	exitLocal(root, cfg, args)
}

func fatal(err error) {
	var reported *reportedError
	if errors.As(err, &reported) {
		os.Exit(reported.status)
	}
	printFailure(err.Error())
	os.Exit(1)
}

func scboltRoot() (string, error) {
	if root := os.Getenv("SCBOLT_ROOT"); root != "" {
		return filepath.Abs(root)
	}

	exe, err := os.Executable()
	if err == nil {
		exe, _ = filepath.EvalSymlinks(exe)
		if root := findScboltRoot(filepath.Dir(exe)); root != "" {
			return root, nil
		}
	}

	wd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	if root := findScboltRoot(wd); root != "" {
		return root, nil
	}
	if root := readConfigVariable(userConfigPath(), "SCBOLT_ROOT"); root != "" {
		absolute, absoluteErr := filepath.Abs(root)
		if absoluteErr == nil && findScboltRoot(absolute) == absolute {
			return absolute, nil
		}
	}

	return "", errors.New(
		"cannot locate scBOLT root; run the launcher from a scBOLT checkout " +
			"or set SCBOLT_ROOT",
	)
}

func findScboltRoot(start string) string {
	for dir := start; ; dir = filepath.Dir(dir) {
		if exists(filepath.Join(dir, "Makefile")) &&
			exists(filepath.Join(dir, "mk", "default_params.mk")) {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return ""
		}
	}
}

func exitLocal(root string, cfg config, args []string) {
	status, err := runLocal(root, cfg, args)
	if err != nil {
		fatal(err)
	}
	os.Exit(status)
}

func execDocker(cfg config, args []string) {
	dryRun := truthy(os.Getenv("SCBOLT_LAUNCHER_DRY_RUN"))
	imageID := ""
	imageDigests := ""

	if !dryRun {
		if _, err := exec.LookPath(cfg.engine); err != nil {
			fatal(fmt.Errorf("Docker backend requested but command not found: %s", cfg.engine))
		}

		if !dockerImageExists(cfg.engine, cfg.image) {
			printWarningTo(os.Stderr, "pulling Docker image: "+cfg.image)
			runCommand(cfg.engine, "pull", cfg.image)
		}

		imageID = dockerInspect(cfg.engine, cfg.image, "{{.Id}}")
		imageDigests = dockerInspect(cfg.engine, cfg.image, "{{join .RepoDigests \" \"}}")
	}

	cwd, err := os.Getwd()
	if err != nil {
		fatal(err)
	}

	mounts := newMountSet(cwd)
	mounts.add(cwd)
	if projectFile := findProjectFile(cwd); projectFile != "" {
		mounts.add(filepath.Dir(projectFile))
	}
	configurationPath := cfg.configurationPath
	if configurationPath != "" {
		mounts.add(filepath.Dir(configurationPath))
	}
	for _, mount := range strings.Fields(cfg.containerMounts) {
		mounts.add(mount)
	}

	dockerArgs := []string{"run", "--rm"}
	if isTerminal(os.Stdin) && isTerminal(os.Stdout) {
		dockerArgs = append(dockerArgs, "-it")
	}
	if cfg.containerArgs != "" {
		dockerArgs = append(dockerArgs, strings.Fields(cfg.containerArgs)...)
	} else {
		dockerArgs = append(dockerArgs, defaultDockerUserArgs()...)
	}
	for _, mount := range mounts.values() {
		dockerArgs = append(
			dockerArgs,
			"--mount",
			fmt.Sprintf(
				"type=bind,source=%s,target=%s",
				mount.source,
				mount.target,
			),
		)
	}

	envs := map[string]string{
		"SCBOLT_IN_DOCKER":              "true",
		"SCBOLT_DEFAULT_BACKEND":        "docker",
		"SCBOLT_DEFAULT_BACKEND_SOURCE": cfg.backendSource,
		"SCBOLT_IMAGE":                  cfg.image,
		"SCBOLT_IMAGE_ID":               imageID,
		"SCBOLT_IMAGE_REPO_DIGESTS":     imageDigests,
		"HOME":                          "/tmp/scbolt-home",
		"MPLCONFIGDIR":                  "/tmp/scbolt-matplotlib",
	}

	dockerArgs = append(dockerArgs, "-w", mounts.containerPath(cwd))
	keys := make([]string, 0, len(envs))
	for key := range envs {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		dockerArgs = append(dockerArgs, "-e", key+"="+envs[key])
	}
	dockerArgs = append(dockerArgs, "--entrypoint", "scbolt", cfg.image)
	dockerArgs = append(
		dockerArgs,
		rewriteDockerPaths(
			dockerForwardedArgs(args),
			configurationPath,
			cfg.configurationFormat,
			mounts,
		)...,
	)

	if dryRun {
		fmt.Println(shellJoin(append([]string{cfg.engine}, dockerArgs...)))
		return
	}

	path, err := exec.LookPath(cfg.engine)
	if err != nil {
		fatal(err)
	}
	execPath(path, append([]string{cfg.engine}, dockerArgs...))
}

func effectiveConfig(args []string) (config, error) {
	cfg := config{
		backend:       envDefault("SCBOLT_DEFAULT_BACKEND", defaultBackend),
		backendSource: envDefault("SCBOLT_DEFAULT_BACKEND_SOURCE", "default"),
		image:         defaultImage,
		engine:        "docker",
	}

	if value := readConfigVariable(userConfigPath(), "BACKEND"); value != "" {
		cfg.backend = value
		cfg.backendSource = "user-config"
	}
	if value := readLegacyBackend(); value != "" && readConfigVariable(userConfigPath(), "BACKEND") == "" {
		cfg.backend = value
		cfg.backendSource = "install"
	}
	if value := readConfigVariable(userConfigPath(), "SCBOLT_IMAGE"); value != "" {
		cfg.image = value
	}
	if value := readConfigVariable(userConfigPath(), "SCBOLT_CONTAINER_ENGINE"); value != "" {
		cfg.engine = value
	}
	if value := readConfigVariable(userConfigPath(), "SCBOLT_CONTAINER_ARGS"); value != "" {
		cfg.containerArgs = value
	}
	if value := readConfigVariable(userConfigPath(), "SCBOLT_CONTAINER_MOUNTS"); value != "" {
		cfg.containerMounts = value
	}

	configurationPath, configurationSource, format, err := selectedConfigurationPath(args)
	if err != nil {
		return cfg, err
	}
	cfg.configurationPath = configurationPath
	cfg.configurationSource = configurationSource
	cfg.configurationFormat = format
	if configurationPath != "" && exists(configurationPath) {
		if format == configurationYAML {
			cfg.projectConfig, err = loadProjectConfiguration(configurationPath)
			if err != nil {
				return cfg, err
			}
		}
		if value, found := projectConfigurationSetting(
			cfg.projectConfig,
			configurationPath,
			"BACKEND",
		); found {
			cfg.backend = value
			cfg.backendSource = configurationValueSource(configurationPath)
		}
		if value, found := projectConfigurationSetting(
			cfg.projectConfig,
			configurationPath,
			"SCBOLT_IMAGE",
		); found {
			cfg.image = value
		}
		if value, found := projectConfigurationSetting(
			cfg.projectConfig,
			configurationPath,
			"SCBOLT_CONTAINER_ENGINE",
		); found {
			cfg.engine = value
		}
		if value, found := projectConfigurationSetting(
			cfg.projectConfig,
			configurationPath,
			"SCBOLT_CONTAINER_ARGS",
		); found {
			cfg.containerArgs = value
		}
		if value, found := projectConfigurationSetting(
			cfg.projectConfig,
			configurationPath,
			"SCBOLT_CONTAINER_MOUNTS",
		); found {
			cfg.containerMounts = value
		}
	}

	if value := argumentValue(args, "BACKEND"); value != "" {
		cfg.backend = value
		cfg.backendSource = "cli"
	}
	if value := argumentValue(args, "SCBOLT_IMAGE"); value != "" {
		cfg.image = value
	}
	if value := argumentValue(args, "SCBOLT_CONTAINER_ENGINE"); value != "" {
		cfg.engine = value
	}
	if value := argumentValue(args, "SCBOLT_CONTAINER_ARGS"); value != "" {
		cfg.containerArgs = value
	}
	if value := argumentValue(args, "SCBOLT_CONTAINER_MOUNTS"); value != "" {
		cfg.containerMounts = value
	}

	cfg.settings = map[string]effectiveSetting{
		"BACKEND": {
			value:  cfg.backend,
			source: cfg.backendSource,
		},
		"LOGGING": resolveEffectiveSetting(
			args,
			cfg.projectConfig,
			cfg.configurationPath,
			"LOGGING",
			effectiveSetting{value: "true", source: "default"},
		),
		"PROJECT_DIR": resolveEffectiveSetting(
			args,
			cfg.projectConfig,
			cfg.configurationPath,
			"PROJECT_DIR",
			effectiveSetting{value: "project", source: "default"},
		),
		"RESOURCES_DIR": resolveEffectiveSetting(
			args,
			cfg.projectConfig,
			cfg.configurationPath,
			"RESOURCES_DIR",
			effectiveSetting{value: "resources", source: "default"},
		),
		"SEED": resolveEffectiveSetting(
			args,
			cfg.projectConfig,
			cfg.configurationPath,
			"SEED",
			effectiveSetting{value: "10", source: "default"},
		),
		"OPENBLAS_CORETYPE": resolveEffectiveSetting(
			args,
			cfg.projectConfig,
			cfg.configurationPath,
			"OPENBLAS_CORETYPE",
			environmentSetting("OPENBLAS_CORETYPE"),
		),
	}

	switch cfg.backend {
	case "conda", "mamba", "micromamba", "docker":
		return cfg, nil
	default:
		return cfg, fmt.Errorf("unsupported backend: %s", cfg.backend)
	}
}

func argumentValue(args []string, variable string) string {
	value, _ := argumentSetting(args, variable)
	return value
}

func argumentSetting(args []string, variable string) (string, bool) {
	options := []string{
		"--" + strings.ToLower(strings.ReplaceAll(variable, "_", "-")),
	}
	publicOption := "--" + strings.NewReplacer("_", "-", ".", "-").Replace(
		publicConfigurationKey(variable),
	)
	if !containsString(options, publicOption) {
		options = append(options, publicOption)
	}
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if strings.EqualFold(arg, variable+"=") {
			return "", true
		}
		if strings.HasPrefix(strings.ToUpper(arg), variable+"=") {
			return strings.TrimSpace(arg[strings.Index(arg, "=")+1:]), true
		}
		for _, option := range options {
			if arg == option && i+1 < len(args) {
				return args[i+1], true
			}
			if strings.HasPrefix(arg, option+"=") {
				return strings.TrimSpace(strings.TrimPrefix(arg, option+"=")), true
			}
		}
	}
	return "", false
}

func selectedConfigurationPath(
	args []string,
) (string, string, configurationFormat, error) {
	var selected string
	source := ""
	legacyOption := false
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch {
		case (arg == "--config" || arg == "--params") && i+1 < len(args):
			selected = args[i+1]
			source = "cli"
			legacyOption = arg == "--params"
			i++
		case strings.HasPrefix(arg, "--config="):
			selected = strings.TrimPrefix(arg, "--config=")
			source = "cli"
			legacyOption = false
		case strings.HasPrefix(arg, "--params="):
			selected = strings.TrimPrefix(arg, "--params=")
			source = "cli"
			legacyOption = true
		case strings.HasPrefix(strings.ToUpper(arg), "CONFIG="):
			selected = arg[strings.Index(arg, "=")+1:]
			source = "cli"
			legacyOption = false
		case strings.HasPrefix(strings.ToUpper(arg), "PARAMS="):
			selected = arg[strings.Index(arg, "=")+1:]
			source = "cli"
			legacyOption = true
		}
	}
	if selected == "" {
		selection := resolveProjectConfiguration()
		selected = selection.path
		legacyOption = selection.legacy
		if selected != "" {
			source = "project-config"
		}
	}
	if selected == "" {
		return "", "", configurationNone, nil
	}
	format := configurationFormatForPath(selected)
	if legacyOption && format == configurationNone {
		format = configurationLegacy
	}
	if format == configurationNone {
		return "", "", format, fmt.Errorf(
			"configuration file must have a .yml, .yaml, or .mk extension: %s",
			selected,
		)
	}
	if filepath.IsAbs(selected) {
		return filepath.Clean(selected), source, format, nil
	}
	wd, err := os.Getwd()
	if err != nil {
		return "", "", format, err
	}
	return filepath.Join(wd, selected), source, format, nil
}

func resolveEffectiveSetting(
	args []string,
	projectConfig *projectConfiguration,
	configurationPath string,
	variable string,
	initial effectiveSetting,
) effectiveSetting {
	setting := initial
	if setting.source == "" {
		setting.source = "default"
	}
	if value := readConfigVariable(userConfigPath(), variable); value != "" {
		setting = effectiveSetting{value: value, source: "user-config"}
	}
	if value, found := projectConfigurationSetting(
		projectConfig,
		configurationPath,
		variable,
	); found {
		setting = effectiveSetting{
			value:  value,
			source: configurationValueSource(configurationPath),
		}
	}
	if value, found := argumentSetting(args, variable); found {
		setting = effectiveSetting{value: value, source: "cli"}
	}
	return setting
}

func environmentSetting(variable string) effectiveSetting {
	if value := os.Getenv(variable); value != "" {
		return effectiveSetting{value: value, source: "environment"}
	}
	return effectiveSetting{source: "default"}
}

type projectConfigurationSelection struct {
	path   string
	legacy bool
}

func resolveProjectConfiguration() projectConfigurationSelection {
	projectFile := findProjectFileFromCwd()
	if projectFile != "" {
		selection := readProjectConfiguration(projectFile)
		if selection.path == "" {
			return selection
		}
		if filepath.IsAbs(selection.path) {
			selection.path = filepath.Clean(selection.path)
			return selection
		}
		selection.path = filepath.Clean(filepath.Join(filepath.Dir(projectFile), selection.path))
		return selection
	}
	if exists(defaultProjectConfigurationFile) {
		return projectConfigurationSelection{path: defaultProjectConfigurationFile}
	}
	if exists("params.mk") {
		return projectConfigurationSelection{path: "params.mk", legacy: true}
	}
	return projectConfigurationSelection{}
}

func resolveProjectParams() string {
	return resolveProjectConfiguration().path
}

func projectConfigurationValue(
	configuration *projectConfiguration,
	path string,
	variable string,
) string {
	if configuration != nil {
		return configuration.Value(variable)
	}
	return readConfigVariable(path, variable)
}

func projectConfigurationSetting(
	configuration *projectConfiguration,
	path string,
	variable string,
) (string, bool) {
	if configuration != nil {
		return configuration.Lookup(variable)
	}
	value := readConfigVariable(path, variable)
	return value, value != ""
}

func configurationValueSource(path string) string {
	if configurationFormatForPath(path) == configurationLegacy {
		return "params"
	}
	return "project-config"
}

func readConfigVariable(path string, variable string) string {
	if path == "" {
		return ""
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	for _, raw := range strings.Split(string(data), "\n") {
		line := stripComment(raw)
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "$(eval ") && strings.HasSuffix(line, ")") {
			line = strings.TrimSuffix(strings.TrimPrefix(line, "$(eval "), ")")
			line = strings.TrimSpace(line)
		}
		for _, op := range []string{":=", "?=", "="} {
			prefix := variable + op
			prefixWithSpace := variable + " " + op
			switch {
			case strings.HasPrefix(line, prefix):
				return strings.TrimSpace(strings.TrimPrefix(line, prefix))
			case strings.HasPrefix(line, prefixWithSpace):
				return strings.TrimSpace(strings.TrimPrefix(line, prefixWithSpace))
			}
		}
	}
	return ""
}

func stripComment(line string) string {
	if index := strings.Index(line, "#"); index >= 0 {
		return line[:index]
	}
	return line
}

func userConfigPath() string {
	configHome, err := os.UserConfigDir()
	if err != nil {
		return ""
	}
	return filepath.Join(configHome, "scbolt", "config.mk")
}

func readLegacyBackend() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	data, err := os.ReadFile(filepath.Join(home, ".local", "share", "scbolt", "backend"))
	if err != nil {
		return ""
	}
	value := strings.TrimSpace(string(data))
	switch value {
	case "conda", "mamba", "micromamba", "docker":
		return value
	default:
		return ""
	}
}

func firstCommand(args []string) string {
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if strings.HasPrefix(arg, "--") {
			if !strings.Contains(arg, "=") && optionTakesValue(arg) && i+1 < len(args) {
				i++
			}
			continue
		}
		if strings.Contains(arg, "=") {
			continue
		}
		return arg
	}
	return ""
}

func optionTakesValue(arg string) bool {
	switch arg {
	case "--config", "--params", "--references", "--reset-target", "--trust-target", "--old-file", "--logging", "--target", "--backend":
		return true
	default:
		return false
	}
}

func isInstallCommand(args []string) bool {
	return firstCommand(args) == "install"
}

func isCompletionInstallCommand(args []string) bool {
	if !isInstallCommand(args) {
		return false
	}
	for _, argument := range installArgs(args) {
		if argument == "--completions" {
			return true
		}
	}
	return false
}

func installArgs(args []string) []string {
	installArgs := make([]string, 0, len(args))
	removed := false
	for _, arg := range args {
		if !removed && arg == "install" {
			removed = true
			continue
		}
		installArgs = append(installArgs, arg)
	}
	return installArgs
}

func findProjectFileFromCwd() string {
	wd, err := os.Getwd()
	if err != nil {
		return ""
	}
	return findProjectFile(wd)
}

func findProjectFile(start string) string {
	for dir := start; ; dir = filepath.Dir(dir) {
		path := filepath.Join(dir, ".scbolt")
		if exists(path) {
			return path
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return ""
		}
	}
}

func dockerImageExists(engine string, image string) bool {
	cmd := exec.Command(engine, "image", "inspect", image)
	return cmd.Run() == nil
}

func dockerInspect(engine string, image string, format string) string {
	cmd := exec.Command(engine, "image", "inspect", image, "--format", format)
	var out bytes.Buffer
	cmd.Stdout = &out
	if cmd.Run() != nil {
		return ""
	}
	return strings.TrimSpace(out.String())
}

func runCommand(name string, args ...string) {
	cmd := exec.Command(name, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		fatal(err)
	}
}

func execPath(path string, argv []string) {
	exitCode, err := executeProcess(path, argv)
	if err != nil {
		fatal(err)
	}
	os.Exit(exitCode)
}

func exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func envDefault(name string, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func truthy(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "1", "true", "yes", "y", "on":
		return true
	default:
		return false
	}
}

func shellJoin(args []string) string {
	quoted := make([]string, len(args))
	for i, arg := range args {
		quoted[i] = strconv.Quote(arg)
	}
	return strings.Join(quoted, " ")
}

func isTerminal(file *os.File) bool {
	info, err := file.Stat()
	if err != nil || info.Mode()&os.ModeCharDevice == 0 {
		return false
	}
	if nullInfo, nullErr := os.Stat(os.DevNull); nullErr == nil &&
		os.SameFile(info, nullInfo) {
		return false
	}
	return true
}

type bindMount struct {
	source string
	target string
}

type mountSet struct {
	workingDirectory string
	targets          map[string]string
	list             []bindMount
}

func newMountSet(workingDirectory string) *mountSet {
	return &mountSet{
		workingDirectory: workingDirectory,
		targets:          map[string]string{},
	}
}

func (set *mountSet) add(path string) string {
	if path == "" || !exists(path) {
		return ""
	}
	absolute, err := filepath.Abs(path)
	if err != nil {
		return ""
	}
	if resolved, err := filepath.EvalSymlinks(absolute); err == nil {
		absolute = resolved
	}
	if target, found := set.targets[absolute]; found {
		return target
	}
	target := dockerMountTarget(
		absolute,
		set.workingDirectory,
		len(set.list),
	)
	set.targets[absolute] = target
	set.list = append(set.list, bindMount{source: absolute, target: target})
	return target
}

func (set *mountSet) containerPath(path string) string {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return path
	}
	if resolved, err := filepath.EvalSymlinks(absolute); err == nil {
		absolute = resolved
	}

	bestSource := ""
	bestTarget := ""
	for source, target := range set.targets {
		relative, relErr := filepath.Rel(source, absolute)
		if relErr != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
			continue
		}
		if len(source) > len(bestSource) {
			bestSource = source
			bestTarget = target
		}
	}
	if bestSource == "" {
		return path
	}
	relative, _ := filepath.Rel(bestSource, absolute)
	if relative == "." {
		return bestTarget
	}
	return filepath.ToSlash(filepath.Join(bestTarget, relative))
}

func (set *mountSet) values() []bindMount {
	return append([]bindMount{}, set.list...)
}

func rewriteDockerPaths(
	args []string,
	configurationPath string,
	format configurationFormat,
	mounts *mountSet,
) []string {
	rewritten := append([]string{}, args...)
	explicitConfiguration := false
	for index := 0; index < len(rewritten); index++ {
		argument := rewritten[index]
		switch {
		case argument == "--config" && index+1 < len(rewritten):
			explicitConfiguration = true
			rewritten[index+1] = mounts.containerPath(configurationPath)
			index++
		case strings.HasPrefix(argument, "--config="):
			explicitConfiguration = true
			rewritten[index] = "--config=" + mounts.containerPath(configurationPath)
		case strings.HasPrefix(strings.ToUpper(argument), "CONFIG="):
			explicitConfiguration = true
			rewritten[index] = "CONFIG=" + mounts.containerPath(configurationPath)
		case argument == "--params" && index+1 < len(rewritten):
			explicitConfiguration = true
			rewritten[index+1] = mounts.containerPath(configurationPath)
			index++
		case strings.HasPrefix(argument, "--params="):
			explicitConfiguration = true
			rewritten[index] = "--params=" + mounts.containerPath(configurationPath)
		case strings.HasPrefix(strings.ToUpper(argument), "PARAMS="):
			explicitConfiguration = true
			rewritten[index] = "PARAMS=" + mounts.containerPath(configurationPath)
		}
	}
	if configurationPath != "" && !explicitConfiguration && dockerNeedsPathTranslation() {
		option := "--config="
		if format == configurationLegacy {
			option = "--params="
		}
		rewritten = append(rewritten, option+mounts.containerPath(configurationPath))
	}
	return rewritten
}

func dockerForwardedArgs(args []string) []string {
	forwarded := make([]string, 0, len(args))
	for index := 0; index < len(args); index++ {
		argument := args[index]
		if isLauncherAssignment(argument) {
			continue
		}
		if isLauncherOption(argument) {
			if !strings.Contains(argument, "=") && index+1 < len(args) {
				index++
			}
			continue
		}
		forwarded = append(forwarded, argument)
	}
	return forwarded
}

func isLauncherAssignment(argument string) bool {
	name, _, found := strings.Cut(argument, "=")
	if !found {
		return false
	}
	switch strings.ToUpper(strings.TrimSpace(name)) {
	case "BACKEND",
		"SCBOLT_IMAGE",
		"SCBOLT_CONTAINER_ENGINE",
		"SCBOLT_CONTAINER_ARGS",
		"SCBOLT_CONTAINER_MOUNTS":
		return true
	default:
		return false
	}
}

func isLauncherOption(argument string) bool {
	name, _, _ := strings.Cut(argument, "=")
	switch name {
	case "--backend",
		"--scbolt-image",
		"--scbolt-container-engine",
		"--scbolt-container-args",
		"--scbolt-container-mounts":
		return true
	default:
		return false
	}
}
