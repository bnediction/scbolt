package main

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func TestLocalRuntimeUsesScboltSystemToolsDirectly(t *testing.T) {
	root := t.TempDir()
	prefix := filepath.Join(t.TempDir(), systemEnvironment)
	bin := filepath.Join(prefix, "bin")
	if err := os.MkdirAll(bin, 0o755); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"make", "bash"} {
		path := filepath.Join(bin, executableFile(name))
		if err := os.WriteFile(path, []byte("placeholder"), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	manager := filepath.Join(t.TempDir(), executableFile("mamba"))
	if err := os.WriteFile(manager, []byte("placeholder"), 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("SCBOLT_ENV_MANAGER", manager)
	t.Setenv("SCBOLT_SYSTEM_PREFIX", prefix)

	local, err := newLocalRuntime(root, config{
		backend:       "mamba",
		backendSource: "cli",
	})
	if err != nil {
		t.Fatal(err)
	}
	command := local.makeCommand("check", "TARGET=spec")
	if command.Path != filepath.Join(bin, executableFile("make")) {
		t.Fatalf("Make path = %q", command.Path)
	}
	wantArgs := []string{
		command.Path,
		"-f",
		filepath.Join(root, "Makefile"),
		"check",
		"TARGET=spec",
	}
	if !reflect.DeepEqual(command.Args, wantArgs) {
		t.Fatalf("Make arguments = %#v, want %#v", command.Args, wantArgs)
	}
	environment := strings.Join(command.Env, "\n")
	for _, expected := range []string{
		"SCBOLT_ENV_MANAGER=" + manager,
		"SCBOLT_SHELL=" + filepath.Join(bin, executableFile("bash")),
		"SCBOLT_SYSTEM_BIN=" + bin,
	} {
		if !strings.Contains(environment, expected) {
			t.Fatalf("runtime environment is missing %q", expected)
		}
	}
}

func TestContainerRuntimeForcesInternalDockerBackend(t *testing.T) {
	t.Setenv("SCBOLT_IN_DOCKER", "true")
	local := &localRuntime{
		root:          "/opt/scbolt",
		config:        config{backend: "mamba", backendSource: "params"},
		manager:       "/opt/conda/bin/micromamba",
		makePath:      "/opt/conda/envs/scbolt-system/bin/make",
		bashPath:      "/opt/conda/envs/scbolt-system/bin/bash",
		systemBinPath: "/opt/conda/envs/scbolt-system/bin",
	}
	command := local.makeCommand("config")
	if got := command.Args[len(command.Args)-1]; got != "BACKEND=docker" {
		t.Fatalf("internal Make backend = %q, want docker", got)
	}
	if !strings.Contains(
		strings.Join(command.Env, "\n"),
		"SCBOLT_DEFAULT_BACKEND=docker",
	) {
		t.Fatal("container runtime does not expose the Docker workflow backend")
	}
}

func TestLocalRuntimeExportsTypedProjectConfiguration(t *testing.T) {
	path := filepath.Join(t.TempDir(), "scbolt.yml")
	if err := os.WriteFile(
		path,
		[]byte("organism: mouse\nconditions: [ctrl, treated]\nneighbors: 14\n"+
			"logging: false\nspec_file: spec.yml\n"+
			"knnsc_centrality_ctrl: [Prom1]\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	projectConfig, err := loadProjectConfiguration(path)
	if err != nil {
		t.Fatal(err)
	}
	local := &localRuntime{
		config: config{
			backend:             "conda",
			backendSource:       "default",
			configurationPath:   path,
			configurationFormat: configurationYAML,
			projectConfig:       projectConfig,
		},
		manager:       "/conda",
		bashPath:      "/bash",
		systemBinPath: "/system/bin",
	}
	environment := strings.Join(local.environment(), "\n")
	for _, expected := range []string{
		"SCBOLT_CLI=true",
		"SCBOLT_CONFIG_MODE=true",
		"SCBOLT_CONFIG=" + path,
		"SCBOLT_PUBLIC_PARAMETER_ORGANISM=organism",
		"SCBOLT_PUBLIC_PARAMETER_LABEL=labels",
		"SCBOLT_PUBLIC_PARAMETER_SPEC_FILE=spec_file",
		"SCBOLT_PUBLIC_PARAMETER_KNNSC_CENTRALITY_CTRL=knnsc_centrality.ctrl",
		"SCBOLT_PUBLIC_PARAMETER_KNNSC_PERIPHERY_TREATED=knnsc_periphery.treated",
		"PARAMS=" + path,
		"ORGANISM=mouse",
		"NEIGHBORS=14",
		"LOGGING=false",
		"SPEC_FILE=spec.yml",
	} {
		if !strings.Contains(environment, expected) {
			t.Errorf("runtime environment is missing %q", expected)
		}
	}
}

func TestDefaultConfigDoesNotExportProjectYAMLValues(t *testing.T) {
	path := filepath.Join(t.TempDir(), "scbolt.yml")
	if err := os.WriteFile(
		path,
		[]byte("organism: mouse\nneighbors: 14\nspec_file: spec.yml\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	projectConfig, err := loadProjectConfiguration(path)
	if err != nil {
		t.Fatal(err)
	}
	local := &localRuntime{
		root: t.TempDir(),
		config: config{
			backend:             "conda",
			backendSource:       "default",
			configurationPath:   path,
			configurationFormat: configurationYAML,
			projectConfig:       projectConfig,
		},
		manager:       "/conda",
		makePath:      "/make",
		bashPath:      "/bash",
		systemBinPath: "/system/bin",
	}
	environment := strings.Join(
		local.makeCommand("config", "DEFAULT_CONFIG=true").Env,
		"\n",
	)
	for _, unexpected := range []string{
		"SCBOLT_CONFIG_MODE=true",
		"ORGANISM=mouse",
		"NEIGHBORS=14",
	} {
		if strings.Contains(environment, unexpected) {
			t.Errorf("default configuration environment contains %q", unexpected)
		}
	}
}

func TestTranslateLocalArgumentsPreservesMakeOverrides(t *testing.T) {
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	project := t.TempDir()
	params := filepath.Join(project, "params.mk")
	if err := os.WriteFile(params, []byte("PROJECT_DIR = project\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(project, ".scbolt"),
		[]byte("PARAMS = params.mk\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(project); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if restoreErr := os.Chdir(workingDirectory); restoreErr != nil {
			t.Errorf("restore working directory: %v", restoreErr)
		}
	})

	cli := &localCLI{}
	translated, err := cli.translate("bn-submin", []string{
		"--reset-target=spec",
		"--trust-target", "max-nodes-lock",
		"--trust-existing",
		"--max-clauses=8",
		"--pca-dimensions=15",
		"REFERENCES=ctrl+treated",
	})
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"CLI_RESET_TARGETS+=spec",
		"CLI_TRUST_TARGETS+=max-nodes-lock",
		"TRUST_EXISTING=true",
		"MAX_CLAUSES=8",
		"DIM_PCA=15",
		"REFERENCES=ctrl+treated",
	}
	if !reflect.DeepEqual(translated.makeArgs, want) {
		t.Fatalf("translated Make arguments = %#v, want %#v", translated.makeArgs, want)
	}
	if translated.configurationPath != params {
		t.Fatalf(
			"resolved configuration = %q, want %q",
			translated.configurationPath,
			params,
		)
	}
	if translated.projectRoot != project {
		t.Fatalf("project root = %q, want %q", translated.projectRoot, project)
	}
}

func TestMakeOutputWriterFiltersOnlyGenericMakeErrors(t *testing.T) {
	var output strings.Builder
	writer := newMakeOutputWriter(&output)
	input := "useful error\nmake[1]: *** [Makefile:10: target] Error 1\nnext line\n"
	if _, err := writer.Write([]byte(input)); err != nil {
		t.Fatal(err)
	}
	if err := writer.flush(); err != nil {
		t.Fatal(err)
	}
	if got, want := output.String(), "useful error\nnext line\n"; got != want {
		t.Fatalf("filtered output = %q, want %q", got, want)
	}
	if summary := writer.summary(); !summary.hasOutput || summary.lastByte != '\n' {
		t.Fatalf("unexpected output summary: %#v", summary)
	}
}

func TestMakeOutputWriterKeepsBoundedStreamSummary(t *testing.T) {
	var output strings.Builder
	writer := newMakeOutputWriter(&output)
	chunks := []string{
		strings.Repeat("progress\r", outputSummaryTailLimit),
		"2026-07-29 10:00:00 - RU",
		"LE - max-nodes-seed\n",
		"2026-07-29 10:00:01 - WARNING - stale module output: spec\n",
		"user-defined time limit reached\n",
	}
	for _, chunk := range chunks {
		if _, err := writer.Write([]byte(chunk)); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.flush(); err != nil {
		t.Fatal(err)
	}
	summary := writer.summary()
	if !summary.rule || !summary.stale || !summary.timedOut {
		t.Fatalf("stream events were not retained: %#v", summary)
	}
	if summary.inferenceModule != "max-nodes-seed" {
		t.Fatalf("inference module = %q", summary.inferenceModule)
	}
	if len(writer.summaryTail) > outputSummaryTailLimit {
		t.Fatalf("summary tail grew to %d bytes", len(writer.summaryTail))
	}
}
