package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

type fakeCommandRunner struct {
	paths   map[string]string
	outputs map[string][]byte
	errors  map[string]error
	calls   []string
}

func (runner *fakeCommandRunner) LookPath(name string) (string, error) {
	runner.calls = append(runner.calls, "lookpath "+name)
	if path, found := runner.paths[name]; found {
		return path, nil
	}
	return "", errors.New("command not found")
}

func (runner *fakeCommandRunner) Run(
	_ context.Context,
	name string,
	args ...string,
) ([]byte, error) {
	key := diagnosticCommandKey(name, args...)
	runner.calls = append(runner.calls, key)
	if err, found := runner.errors[key]; found {
		return runner.outputs[key], err
	}
	if output, found := runner.outputs[key]; found {
		return output, nil
	}
	return nil, errors.New("unexpected command: " + key)
}

type fixedHostDetector struct {
	host HostInfo
}

func (detector fixedHostDetector) Detect(
	_ context.Context,
	_ CommandRunner,
) HostInfo {
	return detector.host
}

func TestDiagnosticReportStatusAggregation(t *testing.T) {
	report := DiagnosticReport{}
	report.Add(Diagnostic{Status: DiagnosticOK})
	report.Add(Diagnostic{Status: DiagnosticWarning})
	if report.Count(DiagnosticWarning) != 1 {
		t.Fatal("warning was not aggregated")
	}
	if report.ExitCode() != 0 {
		t.Fatal("warning-only diagnostics returned a blocking exit code")
	}
	report.Add(Diagnostic{Status: DiagnosticError})
	if report.ExitCode() != 1 {
		t.Fatal("blocking diagnostics did not return exit code 1")
	}
}

func TestDiagnosticsInvalidUsageReturnsTwo(t *testing.T) {
	var output bytes.Buffer
	status, err := runDiagnosticsCommand(
		context.Background(),
		testDiagnosticConfig("docker"),
		[]string{"diagnostics", "unexpected"},
		&output,
		false,
		diagnosticDependencies{},
	)
	if status != 2 || err == nil {
		t.Fatalf("status=%d err=%v, want usage error with status 2", status, err)
	}
}

func TestDiagnosticsHelpIsCommandSpecific(t *testing.T) {
	var output bytes.Buffer
	status, err := runDiagnosticsCommand(
		context.Background(),
		testDiagnosticConfig("docker"),
		[]string{"diagnostics", "--help"},
		&output,
		false,
		diagnosticDependencies{},
	)
	if err != nil || status != 0 {
		t.Fatalf("status=%d err=%v", status, err)
	}
	for _, expected := range []string{
		"usage: scbolt diagnostics",
		"does not validate pipeline inputs",
		"scbolt <command> check",
	} {
		if !strings.Contains(output.String(), expected) {
			t.Fatalf("diagnostics help does not contain %q:\n%s", expected, output.String())
		}
	}
}

func TestDiagnosticsRenderingIsOrderedAndPlain(t *testing.T) {
	report := DiagnosticReport{Diagnostics: []Diagnostic{
		{Section: "Runtime", Name: "runtime", Value: "ok", Status: DiagnosticOK},
		{Section: "scBOLT", Name: "version", Value: "1.0", Status: DiagnosticOK},
		{Section: "Host", Name: "host", Value: "ok", Status: DiagnosticWarning},
		{Section: "Backend", Name: "backend", Value: "ok", Status: DiagnosticError},
		{Section: "Configuration", Name: "config", Value: "ok", Status: DiagnosticOK},
		{Section: "Numerical reproducibility", Name: "profile", Value: "ok", Status: DiagnosticOK},
	}}
	var output bytes.Buffer
	renderDiagnostics(&output, report, false)
	text := output.String()
	previous := -1
	for _, section := range append(diagnosticSectionOrder, "Status") {
		index := strings.Index(text, section+"\n")
		if index <= previous {
			t.Fatalf("section %q is out of order:\n%s", section, text)
		}
		previous = index
	}
	if strings.Contains(text, "\x1b[") {
		t.Fatalf("non-terminal rendering contains ANSI sequences:\n%q", text)
	}
}

func TestDiagnosticsUsesEffectiveConfigurationAndProvenance(t *testing.T) {
	originalDirectory, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = os.Chdir(originalDirectory)
	})
	home := t.TempDir()
	project := t.TempDir()
	configHome := filepath.Join(home, "config")
	if err := os.MkdirAll(filepath.Join(configHome, "scbolt"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(configHome, "scbolt", "config.mk"),
		[]byte("BACKEND = docker\nRESOURCES_DIR = global-resources\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(project, "params.mk"),
		[]byte("BACKEND = mamba\nLOGGING = false\nSEED = 20\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(project); err != nil {
		t.Fatal(err)
	}
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", configHome)
	t.Setenv("SCBOLT_DEFAULT_BACKEND", "")

	cfg, err := effectiveConfig([]string{
		"diagnostics",
		"--backend=conda",
		"SEED=42",
	})
	if err != nil {
		t.Fatal(err)
	}
	if got := cfg.setting("BACKEND"); got.value != "conda" || got.source != "cli" {
		t.Fatalf("backend setting = %#v", got)
	}
	if got := cfg.setting("LOGGING"); got.value != "false" || got.source != "params" {
		t.Fatalf("logging setting = %#v", got)
	}
	if got := cfg.setting("SEED"); got.value != "42" || got.source != "cli" {
		t.Fatalf("seed setting = %#v", got)
	}
	if got := cfg.setting("RESOURCES_DIR"); got.value != "global-resources" || got.source != "user-config" {
		t.Fatalf("resources setting = %#v", got)
	}
}

func TestDockerDiagnosticDispatch(t *testing.T) {
	directory := t.TempDir()
	if err := os.Mkdir(filepath.Join(directory, "resources"), 0o755); err != nil {
		t.Fatal(err)
	}
	runner := successfulDockerRunner(t, "amd64")
	dependencies := testDiagnosticDependencies(directory, runner, referenceHost())
	report := collectDiagnostics(
		context.Background(),
		testDiagnosticConfig("docker"),
		dependencies,
	)
	if report.ExitCode() != 0 {
		t.Fatalf("Docker diagnostics unexpectedly failed: %#v", report.Diagnostics)
	}
	assertDiagnostic(t, report, "Runtime", "Docker daemon", DiagnosticOK)
	assertDiagnostic(t, report, "Backend", "image digest", DiagnosticOK)
	if !containsCall(runner.calls, "docker image inspect ghcr.io/bnediction/scbolt:test") {
		t.Fatalf("Docker image was not inspected: %v", runner.calls)
	}
	for _, call := range runner.calls {
		if strings.Contains(call, " pull ") || strings.Contains(call, " run ") {
			t.Fatalf("diagnostics executed a mutating Docker command: %s", call)
		}
	}
}

func TestDockerDiagnosticFailures(t *testing.T) {
	tests := []struct {
		name       string
		configure  func(*fakeCommandRunner)
		diagnostic string
	}{
		{
			name: "CLI unavailable",
			configure: func(runner *fakeCommandRunner) {
				runner.paths = map[string]string{}
			},
			diagnostic: "Docker CLI",
		},
		{
			name: "daemon unreachable",
			configure: func(runner *fakeCommandRunner) {
				runner.errors[diagnosticCommandKey("docker", "info", "--format", "{{.ServerVersion}}")] = errors.New("offline")
			},
			diagnostic: "Docker daemon",
		},
		{
			name: "image missing",
			configure: func(runner *fakeCommandRunner) {
				runner.errors[diagnosticCommandKey("docker", "image", "inspect", "ghcr.io/bnediction/scbolt:test")] = errors.New("missing")
			},
			diagnostic: "image availability",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			directory := t.TempDir()
			if err := os.Mkdir(filepath.Join(directory, "resources"), 0o755); err != nil {
				t.Fatal(err)
			}
			runner := successfulDockerRunner(t, "amd64")
			test.configure(runner)
			report := collectDiagnostics(
				context.Background(),
				testDiagnosticConfig("docker"),
				testDiagnosticDependencies(directory, runner, referenceHost()),
			)
			if report.ExitCode() != 1 {
				t.Fatalf("blocking failure returned %d", report.ExitCode())
			}
			assertDiagnostic(t, report, "", test.diagnostic, DiagnosticError)
		})
	}
}

func TestDockerArchitectureEmulationIsWarning(t *testing.T) {
	directory := t.TempDir()
	if err := os.Mkdir(filepath.Join(directory, "resources"), 0o755); err != nil {
		t.Fatal(err)
	}
	runner := successfulDockerRunner(t, "amd64")
	host := HostInfo{
		OperatingSystem:   "darwin",
		Architecture:      "arm64",
		Processor:         "Apple M3",
		Microarchitecture: "Apple Silicon",
		ProcessorFeatures: map[string]bool{},
	}
	report := collectDiagnostics(
		context.Background(),
		testDiagnosticConfig("docker"),
		testDiagnosticDependencies(directory, runner, host),
	)
	assertDiagnostic(t, report, "Backend", "architecture compatibility", DiagnosticWarning)
	if report.ExitCode() != 0 {
		t.Fatal("architecture emulation warning blocked Docker diagnostics")
	}
}

func TestLocalDiagnosticDispatch(t *testing.T) {
	directory := t.TempDir()
	if err := os.Mkdir(filepath.Join(directory, "resources"), 0o755); err != nil {
		t.Fatal(err)
	}
	runner := &fakeCommandRunner{
		paths:   map[string]string{"mamba": "/opt/mamba"},
		outputs: make(map[string][]byte),
		errors:  make(map[string]error),
	}
	runner.outputs[diagnosticCommandKey("/opt/mamba", "--version")] = []byte("mamba 2.1.0\n")
	environmentPaths := make([]string, 0, len(installEnvironmentSuffixes))
	for _, suffix := range installEnvironmentSuffixes {
		environmentPaths = append(environmentPaths, filepath.Join(directory, "envs", "scbolt-"+suffix))
	}
	environmentJSON, err := json.Marshal(environmentList{Environments: environmentPaths})
	if err != nil {
		t.Fatal(err)
	}
	runner.outputs[diagnosticCommandKey("/opt/mamba", "env", "list", "--json")] = environmentJSON
	systemPrefix := filepath.Join(directory, "envs", systemEnvironment)
	binDirectory := filepath.Join(systemPrefix, "bin")
	if err := os.MkdirAll(binDirectory, 0o755); err != nil {
		t.Fatal(err)
	}
	for _, executable := range []string{
		"make", "bash", "awk", "cat", "curl", "find", "grep", "gzip", "sed", "tar", "wget",
	} {
		if err := os.WriteFile(filepath.Join(binDirectory, executable), []byte(""), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	runner.outputs[diagnosticCommandKey(filepath.Join(binDirectory, "make"), "--version")] = []byte("GNU Make 4.4.1\n")
	runner.outputs[diagnosticCommandKey(filepath.Join(binDirectory, "bash"), "--version")] = []byte("GNU bash, version 5.2.0\n")

	report := collectDiagnostics(
		context.Background(),
		testDiagnosticConfig("mamba"),
		testDiagnosticDependencies(directory, runner, referenceHost()),
	)
	if report.ExitCode() != 0 {
		t.Fatalf("local diagnostics unexpectedly failed: %#v", report.Diagnostics)
	}
	assertDiagnostic(t, report, "Runtime", "GNU Make", DiagnosticOK)
	assertDiagnostic(t, report, "Runtime", "GNU utilities", DiagnosticOK)
	if !containsCall(runner.calls, "/opt/mamba env list --json") {
		t.Fatalf("local environment manager was not dispatched: %v", runner.calls)
	}

	missingEnvironmentJSON, err := json.Marshal(environmentList{
		Environments: environmentPaths[:len(environmentPaths)-1],
	})
	if err != nil {
		t.Fatal(err)
	}
	runner.outputs[diagnosticCommandKey("/opt/mamba", "env", "list", "--json")] = missingEnvironmentJSON
	missingReport := collectDiagnostics(
		context.Background(),
		testDiagnosticConfig("mamba"),
		testDiagnosticDependencies(directory, runner, referenceHost()),
	)
	assertDiagnostic(t, missingReport, "Backend", "runtime environments", DiagnosticError)
}

func TestUnsupportedNativePlatformsAreBlocking(t *testing.T) {
	for _, operatingSystem := range []string{"darwin", "windows"} {
		t.Run(operatingSystem, func(t *testing.T) {
			directory := t.TempDir()
			if err := os.Mkdir(filepath.Join(directory, "resources"), 0o755); err != nil {
				t.Fatal(err)
			}
			host := referenceHost()
			host.OperatingSystem = operatingSystem
			report := collectDiagnostics(
				context.Background(),
				testDiagnosticConfig("conda"),
				testDiagnosticDependencies(directory, &fakeCommandRunner{}, host),
			)
			assertDiagnostic(t, report, "Backend", "native execution", DiagnosticError)
			if report.ExitCode() != 1 {
				t.Fatal("unsupported native platform was not blocking")
			}
		})
	}
}

func TestOpenBLASCoreTypeDiagnostics(t *testing.T) {
	tests := []struct {
		name      string
		core      string
		host      HostInfo
		status    DiagnosticStatus
		wantValue string
	}{
		{name: "expected", core: "Haswell", host: referenceHost(), status: DiagnosticOK, wantValue: "Haswell"},
		{name: "automatic", host: referenceHost(), status: DiagnosticOK, wantValue: "Haswell"},
		{name: "missing", host: unknownHost(), status: DiagnosticWarning, wantValue: "not set"},
		{name: "unexpected", core: "ZEN", host: referenceHost(), status: DiagnosticWarning, wantValue: "ZEN"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			collection := diagnosticCollection{
				host: test.host,
				config: diagnosticConfiguration{
					seed:         effectiveSetting{value: "10", source: "default"},
					openBLASCore: effectiveSetting{value: test.core, source: "environment"},
				},
			}
			collectNumericalDiagnostics(
				&collection,
				testDiagnosticConfig("conda"),
				diagnosticDependencies{getenv: func(string) string { return "" }},
			)
			diagnostic := findDiagnostic(collection.report, "Numerical reproducibility", "OpenBLAS core type")
			if diagnostic == nil || diagnostic.Status != test.status || diagnostic.Value != test.wantValue {
				t.Fatalf("OpenBLAS diagnostic = %#v", diagnostic)
			}
		})
	}
}

func TestUnknownCPUMicroarchitectureIsWarning(t *testing.T) {
	collection := diagnosticCollection{host: unknownHost()}
	collection.host.Processor = "Unclassified CPU"
	collectHostDiagnostics(&collection)
	assertDiagnostic(t, collection.report, "Host", "CPU microarchitecture", DiagnosticWarning)
}

func TestReferenceCPUMicroarchitectureIsOK(t *testing.T) {
	collection := diagnosticCollection{host: referenceHost()}
	collectHostDiagnostics(&collection)
	assertDiagnostic(t, collection.report, "Host", "CPU microarchitecture", DiagnosticOK)
}

func TestAMDZen3MicroarchitectureIsStrictValidated(t *testing.T) {
	host := referenceHost()
	host.Processor = "AMD Ryzen 9 5950X 16-Core Processor"
	host.Microarchitecture = "AMD Zen 3"
	collection := diagnosticCollection{host: host}
	collectHostDiagnostics(&collection)
	assertDiagnostic(t, collection.report, "Host", "CPU microarchitecture", DiagnosticOK)
}

func TestAMDZen3DetectionFromLinuxCPUInfo(t *testing.T) {
	host := HostInfo{
		Architecture:      "amd64",
		ProcessorFeatures: make(map[string]bool),
	}
	populateLinuxHost(&host, `vendor_id : AuthenticAMD
cpu family : 25
model : 33
model name : AMD Ryzen 9 5950X 16-Core Processor
flags : fma avx2
`)
	host.Microarchitecture = inferMicroarchitecture(host)
	if host.Microarchitecture != "AMD Zen 3" {
		t.Fatalf("microarchitecture = %q", host.Microarchitecture)
	}
	if !host.HaswellCompatible() {
		t.Fatal("Zen 3 host should support the OpenBLAS Haswell profile")
	}
}

func TestAMDZen4IsNotMisclassifiedAsZen3(t *testing.T) {
	host := HostInfo{
		Processor:         "AMD processor",
		ProcessorFeatures: map[string]bool{"avx2": true, "fma": true},
		VendorID:          "AuthenticAMD",
		CPUFamily:         25,
		CPUModel:          0x61,
		CPUFamilyDetected: true,
		CPUModelDetected:  true,
	}
	if got := inferMicroarchitecture(host); got == "AMD Zen 3" {
		t.Fatalf("Zen 4 model was classified as %q", got)
	}
}

func TestNumericalArchitectureContracts(t *testing.T) {
	tests := []struct {
		name   string
		host   HostInfo
		value  string
		status DiagnosticStatus
	}{
		{
			name:   "canonical Meteor Lake",
			host:   referenceHost(),
			value:  "strict validated (canonical)",
			status: DiagnosticOK,
		},
		{
			name: "validated AMD Zen 3",
			host: HostInfo{
				OperatingSystem:   "linux",
				Microarchitecture: "AMD Zen 3",
			},
			value:  "strict validated",
			status: DiagnosticOK,
		},
		{
			name: "portable Emerald Rapids",
			host: HostInfo{
				OperatingSystem:   "linux",
				Microarchitecture: "Emerald Rapids",
			},
			value:  "portable",
			status: DiagnosticWarning,
		},
		{
			name: "unqualified Linux",
			host: HostInfo{
				OperatingSystem:   "linux",
				Microarchitecture: "AMD Zen 4",
			},
			value:  "not yet qualified",
			status: DiagnosticWarning,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			value, status, _ := numericalArchitectureContract(test.host)
			if value != test.value || status != test.status {
				t.Fatalf("contract = %q, %q", value, status)
			}
		})
	}
}

func TestDiagnosticsDoNotLeakUnrelatedEnvironment(t *testing.T) {
	t.Setenv("SCBOLT_TEST_SECRET", "do-not-print-this")
	report := DiagnosticReport{Diagnostics: []Diagnostic{{
		Section: "scBOLT",
		Name:    "version",
		Value:   "1.0",
		Status:  DiagnosticOK,
	}}}
	var output bytes.Buffer
	renderDiagnostics(&output, report, false)
	if strings.Contains(output.String(), os.Getenv("SCBOLT_TEST_SECRET")) {
		t.Fatal("diagnostics leaked an unrelated environment variable")
	}
}

func testDiagnosticConfig(backend string) config {
	return config{
		backend:       backend,
		backendSource: "default",
		image:         "ghcr.io/bnediction/scbolt:test",
		engine:        "docker",
		settings: map[string]effectiveSetting{
			"BACKEND":           {value: backend, source: "default"},
			"LOGGING":           {value: "true", source: "default"},
			"PROJECT_DIR":       {value: "project", source: "default"},
			"RESOURCES_DIR":     {value: "resources", source: "default"},
			"SEED":              {value: "10", source: "default"},
			"OPENBLAS_CORETYPE": {source: "default"},
		},
	}
}

func testDiagnosticDependencies(
	directory string,
	runner CommandRunner,
	host HostInfo,
) diagnosticDependencies {
	return diagnosticDependencies{
		runner:         runner,
		hostDetector:   fixedHostDetector{host: host},
		executable:     func() (string, error) { return filepath.Join(directory, "scbolt"), nil },
		workingDir:     func() (string, error) { return directory, nil },
		root:           func() (string, error) { return directory, nil },
		getenv:         func(string) string { return "" },
		commandTimeout: time.Second,
	}
}

func successfulDockerRunner(t *testing.T, architecture string) *fakeCommandRunner {
	t.Helper()
	runner := &fakeCommandRunner{
		paths:   map[string]string{"docker": "docker"},
		outputs: make(map[string][]byte),
		errors:  make(map[string]error),
	}
	runner.outputs[diagnosticCommandKey("docker", "--version")] = []byte("Docker version 29.1.0\n")
	runner.outputs[diagnosticCommandKey("docker", "info", "--format", "{{.ServerVersion}}")] = []byte("29.1.0\n")
	record := dockerInspectRecord{
		ID:           "sha256:image-id",
		OperatingSys: "linux",
		Architecture: architecture,
		RepoDigests:  []string{"ghcr.io/bnediction/scbolt@sha256:8d91"},
	}
	inspection, err := json.Marshal([]dockerInspectRecord{record})
	if err != nil {
		t.Fatal(err)
	}
	runner.outputs[diagnosticCommandKey("docker", "image", "inspect", "ghcr.io/bnediction/scbolt:test")] = inspection
	return runner
}

func referenceHost() HostInfo {
	return HostInfo{
		OperatingSystem:   "linux",
		Architecture:      "amd64",
		Processor:         "Intel Core Ultra 7 155H",
		Microarchitecture: "Meteor Lake",
		ProcessorFeatures: map[string]bool{"avx2": true, "fma": true},
	}
}

func unknownHost() HostInfo {
	return HostInfo{
		OperatingSystem:   "linux",
		Architecture:      "amd64",
		ProcessorFeatures: map[string]bool{},
	}
}

func diagnosticCommandKey(name string, args ...string) string {
	return strings.Join(append([]string{name}, args...), " ")
}

func assertDiagnostic(
	t *testing.T,
	report DiagnosticReport,
	section string,
	name string,
	status DiagnosticStatus,
) {
	t.Helper()
	diagnostic := findDiagnostic(report, section, name)
	if diagnostic == nil {
		t.Fatalf("diagnostic %q/%q not found in %#v", section, name, report.Diagnostics)
	}
	if diagnostic.Status != status {
		t.Fatalf("diagnostic %q/%q has status %q, want %q", section, name, diagnostic.Status, status)
	}
}

func findDiagnostic(
	report DiagnosticReport,
	section string,
	name string,
) *Diagnostic {
	for index := range report.Diagnostics {
		diagnostic := &report.Diagnostics[index]
		if diagnostic.Name == name && (section == "" || diagnostic.Section == section) {
			return diagnostic
		}
	}
	return nil
}

func containsCall(calls []string, expected string) bool {
	return slicesContain(calls, expected)
}

func slicesContain(values []string, expected string) bool {
	for _, value := range values {
		if value == expected {
			return true
		}
	}
	return false
}
