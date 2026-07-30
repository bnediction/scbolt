package main

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func TestEmbeddedCompletionManifest(t *testing.T) {
	manifest, err := loadCompletionManifest()
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(manifest.Help, "usage: scbolt") {
		t.Fatal("embedded launcher help is missing")
	}
	for _, name := range []string{
		"diagnostics",
		"install",
		"bn-submin",
		"max-nodes-soft",
	} {
		if commandByName(manifest, name) == nil {
			t.Fatalf("missing command in embedded manifest: %s", name)
		}
	}
	if commandByName(manifest, "completion") != nil {
		t.Fatal("removed public completion command remains in embedded manifest")
	}
}

func TestCleanScboltOutputRemovesMakeDirectoryMessages(t *testing.T) {
	output := "make[1]: Entering directory '/tmp/scbolt'\n" +
		"\x1b[1mUtilities\x1b[0m\n" +
		"  \x1b[0;32mbn-submin\x1b[0m  enumerate networks\n" +
		"make[1]: Leaving directory '/tmp/scbolt'\n"
	want := "Utilities\n  bn-submin  enumerate networks\n"
	if got := cleanScboltOutput(output); got != want {
		t.Fatalf("cleaned help = %q", got)
	}
}

func TestStyleLauncherHelp(t *testing.T) {
	help := "usage: scbolt <command...>\n\n" +
		"Special parameters\n" +
		"  --help                          display command help\n\n" +
		"Utilities\n" +
		"  help                    display help\n"
	commands := []completionCommand{{Name: "help"}}

	if got := styleLauncherHelp(help, commands, false); got != help {
		t.Fatalf("non-interactive help changed:\n%q", got)
	}

	styled := styleLauncherHelp(help, commands, true)
	for _, expected := range []string{
		"usage: scbolt \x1b[0;32m<command...>\x1b[0m",
		"\x1b[1mSpecial parameters\x1b[0m",
		"\x1b[1mUtilities\x1b[0m",
		"  \x1b[0;32mhelp\x1b[0m",
	} {
		if !strings.Contains(styled, expected) {
			t.Errorf("styled help does not contain %q:\n%s", expected, styled)
		}
	}
	if strings.Contains(styled, "\x1b[0;32m--help") {
		t.Errorf("special parameter was colored as a command:\n%s", styled)
	}
}

func TestCompleteCommandsAndModuleOptions(t *testing.T) {
	manifest, err := loadCompletionManifest()
	if err != nil {
		t.Fatal(err)
	}
	tests := []struct {
		words []string
		index int
		want  []string
	}{
		{
			words: []string{"scbolt", "bn"},
			index: 1,
			want:  []string{"bn-diverse", "bn-min", "bn-submin"},
		},
		{
			words: []string{"scbolt", "bn-submin", "--max-cl"},
			index: 2,
			want:  []string{"--max-clauses="},
		},
		{
			words: []string{"scbolt", "bn-submin", "--backend=d"},
			index: 2,
			want:  []string{"--backend=docker"},
		},
		{
			words: []string{"scbolt", "install", "m"},
			index: 2,
			want:  []string{"mamba", "micromamba"},
		},
		{
			words: []string{"scbolt", "install", "conda", "--e"},
			index: 3,
			want:  []string{"--env="},
		},
		{
			words: []string{"scbolt", "clustering", "--analysis-hvg-method=b"},
			index: 2,
			want:  []string{"--analysis-hvg-method=binning"},
		},
		{
			words: []string{"scbolt", "spec", "--dorothea-api=m"},
			index: 2,
			want:  []string{"--dorothea-api=modern"},
		},
		{
			words: []string{"scbolt", "spec", "--prior-knowledge=do"},
			index: 2,
			want:  []string{"--prior-knowledge=dorothea"},
		},
		{
			words: []string{"scbolt", "spec", "--organism=m"},
			index: 2,
			want:  []string{"--organism=mouse"},
		},
		{
			words: []string{"scbolt", "max-nodes-soft", "--clause-continuation-soft=t"},
			index: 2,
			want:  []string{"--clause-continuation-soft=true"},
		},
		{
			words: []string{"scbolt", "max-nodes-soft", "--clingo-config-soft=hand"},
			index: 2,
			want:  []string{"--clingo-config-soft=handy"},
		},
		{
			words: []string{"scbolt", "max-nodes-soft", "--clingo-strategy-soft=bb,i"},
			index: 2,
			want:  []string{"--clingo-strategy-soft=bb,inc"},
		},
		{
			words: []string{"scbolt", "install", "--com"},
			index: 2,
			want:  []string{"--completions"},
		},
	}
	for _, test := range tests {
		got := completeWords(manifest, test.words, test.index)
		if !reflect.DeepEqual(got, test.want) {
			t.Fatalf("completion for %v: got %v, want %v", test.words, got, test.want)
		}
	}
}

func TestCompleteConditionDependentOptions(t *testing.T) {
	manifest, err := loadCompletionManifest()
	if err != nil {
		t.Fatal(err)
	}
	configuration := writeProjectConfiguration(t, `
knnsc_centrality_ctrl: [Prom1, Prom2]
knnsc_centrality_treated: [Prom1]
`)
	tests := []struct {
		prefix string
		want   []string
	}{
		{
			prefix: "--knnsc-c",
			want: []string{
				"--knnsc-centrality-ctrl=",
				"--knnsc-centrality-treated=",
			},
		},
		{
			prefix: "--knnsc-p",
			want: []string{
				"--knnsc-periphery-ctrl=",
				"--knnsc-periphery-treated=",
			},
		},
	}
	for _, test := range tests {
		words := []string{
			"scbolt",
			"knnsc",
			"--config=" + configuration,
			test.prefix,
		}
		got := completeWords(manifest, words, 3)
		if !reflect.DeepEqual(got, test.want) {
			t.Fatalf("completion for %q: got %v, want %v", test.prefix, got, test.want)
		}
	}
}

func TestParsePublicParameterOptions(t *testing.T) {
	help := `Parameters
----------
  configuration              scbolt.yml (existing yaml file)
  max_clauses                8 (>= 1)
  binarization_include_nodes Rara Spi1 (node list, optional)

Notes
-----
`
	want := []completionOption{
		{Name: "--binarization-include-nodes="},
		{Name: "--max-clauses="},
	}
	if got := parseParameterOptions(help); !reflect.DeepEqual(got, want) {
		t.Fatalf("parameter options = %#v, want %#v", got, want)
	}
}

func TestCompleteInitParameterSelection(t *testing.T) {
	manifest, err := loadCompletionManifest()
	if err != nil {
		t.Fatal(err)
	}
	directory := t.TempDir()
	for name, contents := range map[string]string{
		"params.mk": "ORGANISM = mouse\n",
		"notes.txt": "not a parameter file\n",
	} {
		if err := os.WriteFile(
			filepath.Join(directory, name),
			[]byte(contents),
			0o644,
		); err != nil {
			t.Fatal(err)
		}
	}
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(directory); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := os.Chdir(workingDirectory); err != nil {
			t.Errorf("restore working directory: %v", err)
		}
	})

	before := completeWords(
		manifest,
		[]string{"scbolt", "init", ""},
		2,
	)
	wantBefore := []string{"--help", "--remove", "--show", "params.mk", "scbolt.yml"}
	if !reflect.DeepEqual(before, wantBefore) {
		t.Fatalf("init selection completion: got %v, want %v", before, wantBefore)
	}

	after := completeWords(
		manifest,
		[]string{"scbolt", "init", "params.mk", ""},
		3,
	)
	if !containsString(after, "--organism=") {
		t.Fatalf("init parameter completion lacks --organism=: %v", after)
	}
	for _, unexpected := range []string{"--remove", "--show"} {
		if containsString(after, unexpected) {
			t.Fatalf("init parameter completion contains %s: %v", unexpected, after)
		}
	}
}

func TestCompleteProjectReferences(t *testing.T) {
	manifest, err := loadCompletionManifest()
	if err != nil {
		t.Fatal(err)
	}
	params := filepath.Join(t.TempDir(), "params.mk")
	if err := os.WriteFile(
		params,
		[]byte("CONDITIONS = ctrl treated\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	words := []string{
		"scbolt",
		"bn-submin",
		"--params=" + params,
		"--references=t",
	}
	want := []string{"--references=treated"}
	if got := completeWords(manifest, words, 3); !reflect.DeepEqual(got, want) {
		t.Fatalf("reference completion: got %v, want %v", got, want)
	}
}

func TestCompletePriorKnowledgeResourcesAndFiles(t *testing.T) {
	manifest, err := loadCompletionManifest()
	if err != nil {
		t.Fatal(err)
	}
	directory := t.TempDir()
	if err := os.WriteFile(filepath.Join(directory, "custom-prior.sif"), nil, 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(filepath.Join(directory, "prior-dir"), 0o755); err != nil {
		t.Fatal(err)
	}
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(directory); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := os.Chdir(workingDirectory); err != nil {
			t.Errorf("restore working directory: %v", err)
		}
	})

	words := []string{"scbolt", "spec", "--prior-knowledge="}
	want := []string{
		"--prior-knowledge=dorothea",
		"--prior-knowledge=collectri",
		"--prior-knowledge=custom-prior.sif",
		"--prior-knowledge=prior-dir" + string(filepath.Separator),
	}
	if got := completeWords(manifest, words, 2); !reflect.DeepEqual(got, want) {
		t.Fatalf("prior-knowledge completion: got %v, want %v", got, want)
	}
}

func TestCompletionScriptsUseLocalProtocol(t *testing.T) {
	for _, shell := range []string{"bash", "zsh", "fish", "powershell"} {
		script, err := completionScript(shell)
		if err != nil {
			t.Fatalf("%s completion: %v", shell, err)
		}
		if !strings.Contains(script, "scbolt __complete") {
			t.Fatalf("%s completion does not use the local protocol", shell)
		}
		if strings.Contains(script, "docker run") {
			t.Fatalf("%s completion starts Docker", shell)
		}
	}
}

func TestBashCompletionSupportsAppleBash(t *testing.T) {
	script, err := completionScript("bash")
	if err != nil {
		t.Fatal(err)
	}
	for _, unsupported := range []string{"mapfile", "-o nosort"} {
		if strings.Contains(script, unsupported) {
			t.Fatalf("Bash completion uses unsupported Bash 3.2 feature %q", unsupported)
		}
	}
	for _, fallback := range []string{"-o bashdefault", "-o default"} {
		if strings.Contains(script, fallback) {
			t.Fatalf("Bash completion enables filename fallback %q", fallback)
		}
	}
}
