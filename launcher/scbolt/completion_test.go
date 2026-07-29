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
		"completion",
		"install",
		"bn-submin",
		"max-nodes-soft",
	} {
		if commandByName(manifest, name) == nil {
			t.Fatalf("missing command in embedded manifest: %s", name)
		}
	}
}

func TestCleanScboltOutputRemovesMakeDirectoryMessages(t *testing.T) {
	output := "make[1]: Entering directory '/tmp/scbolt'\nusage: scbolt\n" +
		"make[1]: Leaving directory '/tmp/scbolt'\n"
	if got := cleanScboltOutput(output); got != "usage: scbolt\n" {
		t.Fatalf("cleaned help = %q", got)
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
			words: []string{"scbolt", "spec", "--prior-knowledge=d"},
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
			words: []string{"scbolt", "completion", "p"},
			index: 2,
			want:  []string{"powershell"},
		},
	}
	for _, test := range tests {
		got := completeWords(manifest, test.words, test.index)
		if !reflect.DeepEqual(got, test.want) {
			t.Fatalf("completion for %v: got %v, want %v", test.words, got, test.want)
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
