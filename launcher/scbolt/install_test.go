package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

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
