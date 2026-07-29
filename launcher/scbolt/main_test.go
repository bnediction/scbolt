package main

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestNullDeviceIsNotTerminal(t *testing.T) {
	null, err := os.Open(os.DevNull)
	if err != nil {
		t.Fatal(err)
	}
	defer null.Close()
	if isTerminal(null) {
		t.Fatal("null device was detected as an interactive terminal")
	}
}

func TestDockerForwardedArgsRemoveLauncherConfiguration(t *testing.T) {
	arguments := []string{
		"bn-submin",
		"--backend=docker",
		"--scbolt-image",
		"scbolt:test",
		"SCBOLT_CONTAINER_ENGINE=podman",
		"--params=params.mk",
		"SEED=10",
	}
	want := []string{
		"bn-submin",
		"--params=params.mk",
		"SEED=10",
	}

	if got := dockerForwardedArgs(arguments); !reflect.DeepEqual(got, want) {
		t.Fatalf("dockerForwardedArgs() = %#v, want %#v", got, want)
	}
}

func TestDockerForwardedArgsPreservePipelineOptions(t *testing.T) {
	arguments := []string{
		"--version",
		"--logging=false",
		"--reset-target",
		"spec",
	}

	if got := dockerForwardedArgs(arguments); !reflect.DeepEqual(got, arguments) {
		t.Fatalf("dockerForwardedArgs() = %#v, want %#v", got, arguments)
	}
}

func TestEffectiveConfigUsesImplicitProjectParameters(t *testing.T) {
	originalDirectory, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if restoreErr := os.Chdir(originalDirectory); restoreErr != nil {
			t.Errorf("restore working directory: %v", restoreErr)
		}
	})
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, "config"))
	t.Setenv("SCBOLT_DEFAULT_BACKEND", "")

	t.Run("default params.mk", func(t *testing.T) {
		project := t.TempDir()
		if err := os.WriteFile(
			filepath.Join(project, "params.mk"),
			[]byte("BACKEND = docker\n"),
			0o644,
		); err != nil {
			t.Fatal(err)
		}
		if err := os.Chdir(project); err != nil {
			t.Fatal(err)
		}
		cfg, err := effectiveConfig(nil)
		if err != nil {
			t.Fatal(err)
		}
		if cfg.backend != "docker" || cfg.backendSource != "params" {
			t.Fatalf("backend = %q (%s)", cfg.backend, cfg.backendSource)
		}
	})

	t.Run("legacy .scbolt path", func(t *testing.T) {
		project := t.TempDir()
		if err := os.WriteFile(
			filepath.Join(project, "custom.mk"),
			[]byte("BACKEND = micromamba\n"),
			0o644,
		); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(
			filepath.Join(project, ".scbolt"),
			[]byte("custom.mk\n"),
			0o644,
		); err != nil {
			t.Fatal(err)
		}
		if err := os.Chdir(project); err != nil {
			t.Fatal(err)
		}
		cfg, err := effectiveConfig(nil)
		if err != nil {
			t.Fatal(err)
		}
		if cfg.backend != "micromamba" || cfg.backendSource != "params" {
			t.Fatalf("backend = %q (%s)", cfg.backend, cfg.backendSource)
		}
	})
}

func TestLauncherCommandsParticipateInSuggestions(t *testing.T) {
	if got := closestChoice("instal", scboltCommands); got != "install" {
		t.Fatalf("suggestion = %q, want install", got)
	}
}
