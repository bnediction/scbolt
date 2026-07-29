package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestMain(tests *testing.M) {
	if os.Getenv("SCBOLT_FAKE_ENV_MANAGER") == "true" {
		os.Exit(runFakeEnvironmentManager())
	}
	os.Exit(tests.Run())
}

func runFakeEnvironmentManager() int {
	root := os.Getenv("SCBOLT_FAKE_ENV_ROOT")
	prefix := filepath.Join(root, systemEnvironment)
	arguments := os.Args[1:]
	switch strings.Join(arguments, " ") {
	case "env list --json":
		if exists(filepath.Join(prefix, "conda-meta")) {
			fmt.Printf("{\"envs\":[%q]}\n", filepath.ToSlash(prefix))
		} else {
			fmt.Println("{\"envs\":[]}")
		}
		return 0
	case "env list":
		if exists(filepath.Join(prefix, "conda-meta")) {
			fmt.Printf("%s %s\n", systemEnvironment, prefix)
		}
		return 0
	default:
		if len(arguments) >= 2 && arguments[0] == "env" && arguments[1] == "create" {
			if err := os.MkdirAll(filepath.Join(prefix, "conda-meta"), 0o755); err != nil {
				fmt.Fprintln(os.Stderr, err)
				return 1
			}
			return 0
		}
		fmt.Fprintf(os.Stderr, "unsupported fake manager invocation: %v\n", arguments)
		return 2
	}
}

func TestUpdateUserConfigPreservesUnrelatedSettings(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(root, "config"))
	path := userConfigPath()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		path,
		[]byte("# existing\nBACKEND = conda\nSCBOLT_CONTAINER_ARGS = --gpus all\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	if err := updateUserConfig(map[string]string{
		"BACKEND":      "docker",
		"SCBOLT_IMAGE": "scbolt:test",
	}); err != nil {
		t.Fatal(err)
	}
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	text := string(content)
	for _, expected := range []string{
		"# existing",
		"BACKEND = docker",
		"SCBOLT_CONTAINER_ARGS = --gpus all",
		"SCBOLT_IMAGE = scbolt:test",
	} {
		if !strings.Contains(text, expected) {
			t.Fatalf("updated configuration is missing %q:\n%s", expected, text)
		}
	}
}

func TestInstallCompletionsDoesNotNeedCheckout(t *testing.T) {
	root := t.TempDir()
	t.Setenv("HOME", root)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(root, "config"))
	t.Setenv("XDG_DATA_HOME", filepath.Join(root, "data"))
	installed, err := installCompletions()
	if err != nil {
		t.Fatal(err)
	}
	if len(installed) == 0 {
		t.Fatal("no completion adapters were installed")
	}
	for _, completion := range installed {
		content, readErr := os.ReadFile(completion.path)
		if readErr != nil {
			t.Fatalf("%s completion: %v", completion.shell, readErr)
		}
		if !strings.Contains(string(content), "scbolt __complete") {
			t.Fatalf("%s completion is not launcher-backed", completion.shell)
		}
	}
}

func TestNativeLauncherBootstrapDoesNotNeedRepositoryInstallScript(t *testing.T) {
	home := t.TempDir()
	source := filepath.Join(t.TempDir(), "scbolt-source")
	if err := os.WriteFile(source, []byte("native launcher"), 0o755); err != nil {
		t.Fatal(err)
	}

	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, "config"))
	t.Setenv("XDG_DATA_HOME", filepath.Join(home, "data"))
	t.Setenv("SCBOLT_INSTALL_BIN_DIR", filepath.Join(home, "bin"))
	t.Setenv("SCBOLT_LAUNCHER_INSTALL_SOURCE", source)

	if err := installLauncher(); err != nil {
		t.Fatal(err)
	}
	if !exists(filepath.Join(home, "bin", executableName())) {
		t.Fatal("native launcher was not installed")
	}
	if exists(userConfigPath()) {
		t.Fatal("launcher bootstrap unexpectedly wrote backend configuration")
	}
}

func TestBackendInstallationDoesNotInstallLauncher(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, "config"))
	t.Setenv("XDG_DATA_HOME", filepath.Join(home, "data"))
	t.Setenv("SCBOLT_INSTALL_BIN_DIR", filepath.Join(home, "bin"))
	t.Setenv("SCBOLT_INSTALL_SKIP_IMAGE", "true")

	if err := runInstall(
		config{
			backend:       "conda",
			backendSource: "user-config",
			engine:        "docker",
			image:         "scbolt:test",
		},
		[]string{"docker"},
	); err != nil {
		t.Fatal(err)
	}
	if exists(filepath.Join(home, "bin", executableName())) {
		t.Fatal("backend installation unexpectedly installed the launcher")
	}
	configuration, err := os.ReadFile(userConfigPath())
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(configuration), "BACKEND = docker") {
		t.Fatalf("backend configuration was not installed:\n%s", configuration)
	}
}

func TestParseInstallRequestDefaultsAndExplicitTargets(t *testing.T) {
	request, err := parseInstallRequest(nil)
	if err != nil {
		t.Fatal(err)
	}
	if request.assumeYes || request.backendRequested {
		t.Fatalf("unexpected default install request: %#v", request)
	}
	if len(request.selectedEnvironments) != len(installEnvironmentSuffixes) {
		t.Fatalf("default environments = %v", request.selectedEnvironments)
	}

	request, err = parseInstallRequest([]string{
		"--env=system",
		"--env",
		"core",
		"--env=system",
		"micromamba",
	})
	if err != nil {
		t.Fatal(err)
	}
	if !request.assumeYes || !request.backendRequested {
		t.Fatalf("unexpected explicit install request: %#v", request)
	}
	if request.backend != "micromamba" {
		t.Fatalf("selected backend = %q", request.backend)
	}
	want := []string{"system", "core"}
	if strings.Join(request.selectedEnvironments, ",") != strings.Join(want, ",") {
		t.Fatalf("selected environments = %v, want %v", request.selectedEnvironments, want)
	}
}

func TestParseInstallRequestBackendCompatibilityAndConflicts(t *testing.T) {
	request, err := parseInstallRequest([]string{"--backend=conda"})
	if err != nil {
		t.Fatal(err)
	}
	if request.backend != "conda" || !request.backendRequested {
		t.Fatalf("legacy backend selection was not retained: %#v", request)
	}

	if _, err := parseInstallRequest([]string{"conda", "--backend=mamba"}); err == nil {
		t.Fatal("conflicting backend selections were accepted")
	}
	if _, err := parseInstallRequest([]string{"unsupported"}); err == nil {
		t.Fatal("unsupported positional backend was accepted")
	}
	if _, err := parseInstallRequest([]string{"conda", "--cli"}); err == nil {
		t.Fatal("removed --cli option was accepted")
	}
}

func TestLauncherInvocationNeedsBootstrap(t *testing.T) {
	directory := t.TempDir()
	external := filepath.Join(directory, "scbolt-linux-amd64")
	installed := filepath.Join(directory, executableName())
	for _, path := range []string{external, installed} {
		if err := os.WriteFile(path, []byte(path), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	if !launcherInvocationNeedsBootstrap(external, installed) {
		t.Fatal("external distribution launcher did not request bootstrap")
	}
	if launcherInvocationNeedsBootstrap(installed, external) {
		t.Fatal("installed launcher unexpectedly requested bootstrap")
	}
	if launcherInvocationNeedsBootstrap(installed, installed) {
		t.Fatal("managed launcher unexpectedly requested bootstrap")
	}
}

func TestDecodeManagedEnvironmentListIgnoresLeadingNotices(t *testing.T) {
	output := []byte("notice\n{\"envs\":[\"/opt/conda/envs/scbolt-system\"]}\n")
	environments, ok := decodeManagedEnvironmentList(output)
	if !ok {
		t.Fatal("environment list was not decoded")
	}
	if environments["scbolt-system"] != "/opt/conda/envs/scbolt-system" {
		t.Fatalf("decoded environments = %v", environments)
	}
}

func TestInstallSystemEnvironmentInvokesManagerDirectly(t *testing.T) {
	root := t.TempDir()
	managerRoot := t.TempDir()
	environmentDirectory := filepath.Join(root, "envs", "conda")
	if err := os.MkdirAll(environmentDirectory, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(environmentDirectory, "system.yml"),
		[]byte("name: scbolt-system\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	manager, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("SCBOLT_FAKE_ENV_MANAGER", "true")
	t.Setenv("SCBOLT_FAKE_ENV_ROOT", managerRoot)

	request := installRequest{
		assumeYes:            true,
		selectedEnvironments: []string{"system"},
	}
	if err := installLocalEnvironments(
		root,
		"conda",
		manager,
		request,
		bufio.NewReader(strings.NewReader("")),
	); err != nil {
		t.Fatal(err)
	}
	if !exists(filepath.Join(managerRoot, systemEnvironment, "conda-meta")) {
		t.Fatal("system environment was not created by the manager")
	}
}
