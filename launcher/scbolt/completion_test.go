package main

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func TestEmbeddedCompletionManifest(t *testing.T) {
	manifest, err := completionManifest()
	if err != nil {
		t.Fatal(err)
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

func TestCompleteCommandsAndModuleOptions(t *testing.T) {
	manifest, err := completionManifest()
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
	manifest, err := completionManifest()
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
}
