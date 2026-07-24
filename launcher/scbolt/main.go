package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
)

const (
	defaultBackend = "conda"
	defaultImage   = "ghcr.io/bnediction/scbolt:latest"
)

type config struct {
	backend         string
	backendSource   string
	image           string
	engine          string
	containerArgs   string
	containerMounts string
}

func main() {
	root, err := scboltRoot()
	if err != nil {
		fatal(err)
	}

	args := os.Args[1:]
	if isInstallCommand(args) && os.Getenv("SCBOLT_IN_DOCKER") != "true" {
		execInstall(root, installArgs(args))
	}

	cfg, err := effectiveConfig(args)
	if err != nil {
		fatal(err)
	}

	if os.Getenv("SCBOLT_IN_DOCKER") == "true" || cfg.backend != "docker" || skipDocker(args) {
		execLocal(root, args)
	}

	execDocker(root, cfg, args)
}

func fatal(err error) {
	fmt.Fprintf(os.Stderr, "✗ %s\n", err)
	os.Exit(1)
}

func scboltRoot() (string, error) {
	if root := os.Getenv("SCBOLT_ROOT"); root != "" {
		return filepath.Abs(root)
	}

	exe, err := os.Executable()
	if err == nil {
		exe, _ = filepath.EvalSymlinks(exe)
		dir := filepath.Dir(exe)
		if filepath.Base(dir) == "bin" && exists(filepath.Join(filepath.Dir(dir), "Makefile")) {
			return filepath.Dir(dir), nil
		}
	}

	wd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for dir := wd; ; dir = filepath.Dir(dir) {
		if exists(filepath.Join(dir, "Makefile")) && exists(filepath.Join(dir, "bin", "scbolt")) {
			return dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
	}

	return "", errors.New("cannot locate scBOLT root; set SCBOLT_ROOT")
}

func execInstall(root string, args []string) {
	install := filepath.Join(root, "install")
	if !exists(install) {
		fatal(fmt.Errorf("install script not found: %s", install))
	}
	execPath(install, append([]string{install}, args...))
}

func execLocal(root string, args []string) {
	local := filepath.Join(root, "bin", "scbolt-local")
	if !exists(local) {
		local = filepath.Join(root, "bin", "scbolt")
	}

	exe, _ := os.Executable()
	exe, _ = filepath.EvalSymlinks(exe)
	localResolved, _ := filepath.EvalSymlinks(local)
	if exe != "" && localResolved == exe {
		fatal(fmt.Errorf("local scBOLT wrapper not found: %s", filepath.Join(root, "bin", "scbolt-local")))
	}

	execPath(local, append([]string{local}, args...))
}

func execDocker(root string, cfg config, args []string) {
	dryRun := truthy(os.Getenv("SCBOLT_LAUNCHER_DRY_RUN"))
	imageID := ""
	imageDigests := ""

	if !dryRun {
		if _, err := exec.LookPath(cfg.engine); err != nil {
			fatal(fmt.Errorf("Docker backend requested but command not found: %s", cfg.engine))
		}

		if !dockerImageExists(cfg.engine, cfg.image) {
			fmt.Fprintf(os.Stderr, "⚠ pulling Docker image: %s\n", cfg.image)
			runCommand(cfg.engine, "pull", cfg.image)
		}

		imageID = dockerInspect(cfg.engine, cfg.image, "{{.Id}}")
		imageDigests = dockerInspect(cfg.engine, cfg.image, "{{join .RepoDigests \" \"}}")
	}

	cwd, err := os.Getwd()
	if err != nil {
		fatal(err)
	}

	mounts := newMountSet()
	mounts.add(cwd)
	mounts.add(root)
	if projectFile := findProjectFile(cwd); projectFile != "" {
		mounts.add(filepath.Dir(projectFile))
	}
	if params := paramsPathFromArgs(args); params != "" {
		mounts.add(filepath.Dir(params))
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
		dockerArgs = append(dockerArgs, "--user", fmt.Sprintf("%d:%d", os.Getuid(), os.Getgid()))
	}
	for _, mount := range mounts.values() {
		dockerArgs = append(dockerArgs, "-v", mount+":"+mount)
	}

	envs := map[string]string{
		"SCBOLT_IN_DOCKER":              "true",
		"SCBOLT_DEFAULT_BACKEND":        "docker",
		"SCBOLT_DEFAULT_BACKEND_SOURCE": cfg.backendSource,
		"SCBOLT_IMAGE":                  cfg.image,
		"SCBOLT_IMAGE_ID":               imageID,
		"SCBOLT_IMAGE_REPO_DIGESTS":     imageDigests,
		"OPENBLAS_NUM_THREADS":          envDefault("OPENBLAS_NUM_THREADS", "1"),
		"OMP_NUM_THREADS":               envDefault("OMP_NUM_THREADS", "1"),
		"MKL_NUM_THREADS":               envDefault("MKL_NUM_THREADS", "1"),
		"NUMEXPR_NUM_THREADS":           envDefault("NUMEXPR_NUM_THREADS", "1"),
		"HOME":                          "/tmp/scbolt-home",
		"MPLCONFIGDIR":                  "/tmp/scbolt-matplotlib",
	}

	dockerArgs = append(dockerArgs, "-w", cwd)
	keys := make([]string, 0, len(envs))
	for key := range envs {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		dockerArgs = append(dockerArgs, "-e", key+"="+envs[key])
	}
	dockerArgs = append(dockerArgs, "--entrypoint", "scbolt", cfg.image)
	dockerArgs = append(dockerArgs, args...)

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

	if params := paramsPathFromArgs(args); params != "" && exists(params) {
		if value := readConfigVariable(params, "BACKEND"); value != "" {
			cfg.backend = value
			cfg.backendSource = "params"
		}
		if value := readConfigVariable(params, "SCBOLT_IMAGE"); value != "" {
			cfg.image = value
		}
		if value := readConfigVariable(params, "SCBOLT_CONTAINER_ENGINE"); value != "" {
			cfg.engine = value
		}
		if value := readConfigVariable(params, "SCBOLT_CONTAINER_ARGS"); value != "" {
			cfg.containerArgs = value
		}
		if value := readConfigVariable(params, "SCBOLT_CONTAINER_MOUNTS"); value != "" {
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

	switch cfg.backend {
	case "conda", "mamba", "micromamba", "docker":
		return cfg, nil
	default:
		return cfg, fmt.Errorf("unsupported backend: %s", cfg.backend)
	}
}

func argumentValue(args []string, variable string) string {
	option := "--" + strings.ToLower(strings.ReplaceAll(variable, "_", "-"))
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if strings.EqualFold(arg, variable+"=") {
			return ""
		}
		if strings.HasPrefix(strings.ToUpper(arg), variable+"=") {
			return strings.TrimSpace(arg[strings.Index(arg, "=")+1:])
		}
		if arg == option && i+1 < len(args) {
			return args[i+1]
		}
		if strings.HasPrefix(arg, option+"=") {
			return strings.TrimSpace(strings.TrimPrefix(arg, option+"="))
		}
	}
	return ""
}

func paramsPathFromArgs(args []string) string {
	var params string
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch {
		case arg == "--params" && i+1 < len(args):
			params = args[i+1]
		case strings.HasPrefix(arg, "--params="):
			params = strings.TrimPrefix(arg, "--params=")
		case strings.HasPrefix(strings.ToUpper(arg), "PARAMS="):
			params = arg[strings.Index(arg, "=")+1:]
		}
	}
	if params == "" {
		params = resolveProjectParams()
	}
	if params == "" {
		return ""
	}
	if filepath.IsAbs(params) {
		return filepath.Clean(params)
	}
	wd, err := os.Getwd()
	if err != nil {
		return ""
	}
	return filepath.Join(wd, params)
}

func resolveProjectParams() string {
	projectFile := findProjectFileFromCwd()
	if projectFile == "" {
		return ""
	}
	value := readConfigVariable(projectFile, "PARAMS")
	if value == "" {
		return ""
	}
	if filepath.IsAbs(value) {
		return value
	}
	return filepath.Join(filepath.Dir(projectFile), value)
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
	if xdg := os.Getenv("XDG_CONFIG_HOME"); xdg != "" {
		return filepath.Join(xdg, "scbolt", "config.mk")
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".config", "scbolt", "config.mk")
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

func skipDocker(args []string) bool {
	cmd := firstCommand(args)
	if cmd == "" || cmd == "-h" || cmd == "--help" || cmd == "help" || cmd == "init" {
		return true
	}
	for _, arg := range args {
		if arg == "-h" || arg == "--help" || arg == "help" {
			return true
		}
	}
	return false
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
	case "--params", "--references", "--reset-target", "--trust-target", "--old-file", "--logging", "--target", "--backend":
		return true
	default:
		return false
	}
}

func isInstallCommand(args []string) bool {
	return firstCommand(args) == "install"
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
	if err := syscall.Exec(path, argv, os.Environ()); err != nil {
		fatal(err)
	}
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
	return err == nil && info.Mode()&os.ModeCharDevice != 0
}

type mountSet struct {
	seen map[string]bool
	list []string
}

func newMountSet() *mountSet {
	return &mountSet{seen: map[string]bool{}}
}

func (set *mountSet) add(path string) {
	if path == "" || !exists(path) {
		return
	}
	absolute, err := filepath.Abs(path)
	if err != nil {
		return
	}
	if resolved, err := filepath.EvalSymlinks(absolute); err == nil {
		absolute = resolved
	}
	if set.seen[absolute] {
		return
	}
	set.seen[absolute] = true
	set.list = append(set.list, absolute)
}

func (set *mountSet) values() []string {
	return append([]string{}, set.list...)
}
