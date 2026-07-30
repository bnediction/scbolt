package main

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func writeProjectConfiguration(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "scbolt.yml")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestProjectConfigurationTranslatesFlatYAML(t *testing.T) {
	path := writeProjectConfiguration(t, `
project_dir: project_gsm
inference_dir: infer/alternative
organism: mouse
gsm:
  ctrl: GSM5492245
  treated: GSM5492246
pca_dimensions: 15
neighbors: 14
zeroes_are_zeroes: false
hvg_method: binning
hvg_top: null
analysis_hvg_method: loess
binarization_include_nodes: [Rara, Cebpa]
spec_file: spec.yml
knnsc_centrality:
  ctrl: [Prom1, Prom2]
  treated:
    - Prom1
    - Prom2
`)
	configuration, err := loadProjectConfiguration(path)
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]string{
		"PROJECT_DIR":              "project_gsm",
		"INFERENCE_DIR":            "infer/alternative",
		"SPEC_FILE":                "spec.yml",
		"ORGANISM":                 "mouse",
		"CONDITIONS":               "ctrl treated",
		"GSM_CTRL":                 "GSM5492245",
		"GSM_TREATED":              "GSM5492246",
		"DIM_PCA":                  "15",
		"NEIGHBORS":                "14",
		"ZEROES_ARE_ZEROES":        "false",
		"ANALYSIS_HVG_METHOD":      "loess",
		"BIN_HVG_METHOD":           "binning",
		"ANALYSIS_HVG_TOP":         "",
		"BIN_HVG_TOP":              "",
		"BIN_INCLUDE_NODES":        "Rara Cebpa",
		"KNNSC_CENTRALITY_CTRL":    "Prom1 Prom2",
		"KNNSC_CENTRALITY_TREATED": "Prom1 Prom2",
	}
	for name, expected := range want {
		if got := configuration.Value(name); got != expected {
			t.Errorf("%s = %q, want %q", name, got, expected)
		}
	}
}

func TestProjectConfigurationListSyntaxesAreEquivalent(t *testing.T) {
	compact := writeProjectConfiguration(t, "labels: [Prom1, Prom2, Rep]\n"+
		"binarization_include_nodes: [Rara, Spi1]\n")
	vertical := writeProjectConfiguration(t, "labels:\n  - Prom1\n  - Prom2\n  - Rep\n"+
		"binarization_include_nodes:\n  - Rara\n  - Spi1\n")
	left, err := loadProjectConfiguration(compact)
	if err != nil {
		t.Fatal(err)
	}
	right, err := loadProjectConfiguration(vertical)
	if err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"LABEL", "BIN_INCLUDE_NODES"} {
		if left.Value(name) != right.Value(name) {
			t.Errorf("%s differs: %q != %q", name, left.Value(name), right.Value(name))
		}
	}
}

func TestProjectConfigurationConditionalSyntaxesAreEquivalent(t *testing.T) {
	mapped := writeProjectConfiguration(t, `
gsm:
  ctrl: GSM5492245
  treated: GSM5492246
sra:
  ctrl: [SRR1, SRR2]
  treated: [SRR3]
knnsc_centrality:
  ctrl: [Prom1, Prom2]
  treated: [Prom1]
knnsc_periphery:
  ctrl: [Rep, Neu]
  treated: [Rep]
`)
	flattened := writeProjectConfiguration(t, `
gsm_ctrl: GSM5492245
gsm_treated: GSM5492246
sra_ctrl: [SRR1, SRR2]
sra_treated: [SRR3]
knnsc_centrality_ctrl: [Prom1, Prom2]
knnsc_centrality_treated: [Prom1]
knnsc_periphery_ctrl: [Rep, Neu]
knnsc_periphery_treated: [Rep]
`)

	left, err := loadProjectConfiguration(mapped)
	if err != nil {
		t.Fatal(err)
	}
	right, err := loadProjectConfiguration(flattened)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(left.Environment(), right.Environment()) {
		t.Fatalf(
			"conditional syntaxes differ:\n mapped: %#v\nflat: %#v",
			left.Environment(),
			right.Environment(),
		)
	}
}

func TestProjectConfigurationAllowsMatchingConditionalDefinitions(t *testing.T) {
	path := writeProjectConfiguration(t, `
conditions: [ctrl]
knnsc_centrality:
  ctrl: [Prom1, Prom2]
knnsc_centrality_ctrl: [Prom1, Prom2]
`)
	configuration, err := loadProjectConfiguration(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := configuration.Value("KNNSC_CENTRALITY_CTRL"); got != "Prom1 Prom2" {
		t.Fatalf("KNNSC_CENTRALITY_CTRL = %q", got)
	}
}

func TestProjectConfigurationRejectsUnknownKeysAndInvalidTypes(t *testing.T) {
	tests := []struct {
		name    string
		content string
		want    string
	}{
		{"unknown key", "neigbors: 14\n", `unknown configuration key "neigbors"`},
		{"quoted boolean", "logging: \"true\"\n", `configuration key "logging" must be a boolean`},
		{"embedded constraints", "constraints: []\n", `unknown configuration key "constraints"`},
		{"condition outside list", "conditions: [ctrl]\ngsm:\n  treated: GSM2\n", `condition "treated" in gsm is not listed in conditions`},
		{"flat condition outside list", "conditions: [ctrl]\ngsm_treated: GSM2\n", `condition "treated" in gsm is not listed in conditions`},
		{"scalar with conditions", "conditions: [ctrl]\ngsm: GSM1\n", `configuration key "gsm" must be indexed by condition`},
		{
			"conflicting conditional forms",
			"knnsc_centrality:\n  ctrl: [Prom1]\nknnsc_centrality_ctrl: [Prom2]\n",
			`conflicting values for condition "ctrl" in knnsc_centrality`,
		},
		{"version", "version: 1\n", `unknown configuration key "version"`},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			path := writeProjectConfiguration(t, test.content)
			_, err := loadProjectConfiguration(path)
			if err == nil || !strings.Contains(err.Error(), test.want) {
				t.Fatalf("error = %v, want substring %q", err, test.want)
			}
			if !strings.Contains(err.Error(), path+":") {
				t.Fatalf("error does not contain a source location: %v", err)
			}
		})
	}
}

func TestProjectLocatorPrefersConfigAndReadsLegacyParams(t *testing.T) {
	project := t.TempDir()
	locator := filepath.Join(project, ".scbolt")
	if err := os.WriteFile(
		locator,
		[]byte("PARAMS=legacy.mk\nCONFIG=scbolt.yml\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	selection := readProjectConfiguration(locator)
	if selection.path != "scbolt.yml" || selection.legacy {
		t.Fatalf("selection = %#v", selection)
	}
	if err := os.WriteFile(locator, []byte("PARAMS=legacy.mk\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	selection = readProjectConfiguration(locator)
	if selection.path != "legacy.mk" || !selection.legacy {
		t.Fatalf("legacy selection = %#v", selection)
	}
}

func TestInitCreatesConfigurationSpecificationAndProjectLocator(t *testing.T) {
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	project := t.TempDir()
	if err := os.Chdir(project); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if restoreErr := os.Chdir(workingDirectory); restoreErr != nil {
			t.Errorf("restore working directory: %v", restoreErr)
		}
	})

	err = runInit(config{backend: "conda"}, []string{
		"init",
		"scbolt.yml",
		"--organism=mouse",
		"--conditions=ctrl treated",
		"--gsm-ctrl=GSM5492245",
		"--gsm-treated=GSM5492246",
		"--pca-dimensions=15",
		"--zeroes-are-zeroes=false",
	})
	if err != nil {
		t.Fatal(err)
	}
	locator, err := os.ReadFile(filepath.Join(project, ".scbolt"))
	if err != nil {
		t.Fatal(err)
	}
	if got := string(locator); got != "CONFIG=scbolt.yml\n" {
		t.Fatalf("project locator = %q", got)
	}
	path := filepath.Join(project, "scbolt.yml")
	configuration, err := loadProjectConfiguration(path)
	if err != nil {
		t.Fatal(err)
	}
	for name, want := range map[string]string{
		"SPEC_FILE":         "spec.yml",
		"ORGANISM":          "mouse",
		"CONDITIONS":        "ctrl treated",
		"GSM_CTRL":          "GSM5492245",
		"GSM_TREATED":       "GSM5492246",
		"DIM_PCA":           "15",
		"ZEROES_ARE_ZEROES": "false",
	} {
		if got := configuration.Value(name); got != want {
			t.Errorf("%s = %q, want %q", name, got, want)
		}
	}
	contents, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{
		"sra",
		"count_files",
		"macrostate_files",
		"binarization_file",
	} {
		if !strings.Contains(string(contents), key+": null") {
			t.Errorf("generated configuration is missing the %q placeholder", key)
		}
	}
	for _, expected := range []string{"labels: []", "spec_file: spec.yml"} {
		if !strings.Contains(string(contents), expected) {
			t.Errorf("generated configuration is missing %q", expected)
		}
	}
	specification, err := os.ReadFile(filepath.Join(project, "spec.yml"))
	if err != nil {
		t.Fatal(err)
	}
	for _, section := range specificationKeys() {
		if !strings.Contains(string(specification), section+": []") {
			t.Errorf("generated specification is missing %q", section)
		}
	}
}

func TestMinimalYAMLContentIncludesProjectScaffold(t *testing.T) {
	content, err := minimalYAMLContent(nil)
	if err != nil {
		t.Fatal(err)
	}
	for _, expected := range []string{
		"# Organism used for gene resources",
		"# Input sources are mutually exclusive",
		"# Biological labels assigned to clusters",
		"organism: null",
		"conditions: null",
		"sra: null",
		"gsm: null",
		"count_files: null",
		"macrostate_files: null",
		"binarization_file: null",
		"labels: []",
		"spec_file: spec.yml",
	} {
		if !strings.Contains(content, expected) {
			t.Errorf("generated configuration is missing %q", expected)
		}
	}
}

func TestMinimalSpecificationContentIncludesContracts(t *testing.T) {
	content, err := minimalSpecificationContent()
	if err != nil {
		t.Fatal(err)
	}
	for _, section := range specificationKeys() {
		if !strings.Contains(content, section+": []") {
			t.Errorf("generated specification is missing %q", section)
		}
	}
	if !strings.Contains(content, "# BoNesis observations and dynamical constraints") {
		t.Error("generated specification is missing contract comments")
	}
}
