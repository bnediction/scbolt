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

	t.Run("typed scbolt.yml", func(t *testing.T) {
		project := t.TempDir()
		if err := os.WriteFile(
			filepath.Join(project, "scbolt.yml"),
			[]byte("backend: micromamba\nlogging: false\nspec_file: spec.yml\n"),
			0o644,
		); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(
			filepath.Join(project, ".scbolt"),
			[]byte("CONFIG=scbolt.yml\n"),
			0o644,
		); err != nil {
			t.Fatal(err)
		}
		if err := os.Chdir(project); err != nil {
			t.Fatal(err)
		}
		cfg, err := effectiveConfig([]string{"config"})
		if err != nil {
			t.Fatal(err)
		}
		if cfg.backend != "micromamba" || cfg.backendSource != "project-config" {
			t.Fatalf("backend = %q (%s)", cfg.backend, cfg.backendSource)
		}
		if setting := cfg.setting("LOGGING"); setting.value != "false" || setting.source != "project-config" {
			t.Fatalf("logging = %#v", setting)
		}
	})
}

func TestLauncherCommandsParticipateInSuggestions(t *testing.T) {
	if got := closestChoice("instal", scboltCommands); got != "install" {
		t.Fatalf("suggestion = %q, want install", got)
	}
}

func TestEffectiveConfigurationPrecedenceAndExplicitNull(t *testing.T) {
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
	configHome := filepath.Join(home, "config")
	userDirectory := filepath.Join(configHome, "scbolt")
	if err := os.MkdirAll(userDirectory, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(userDirectory, "config.mk"),
		[]byte("LOGGING = false\nPROJECT_DIR = global-project\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", configHome)
	t.Setenv("SCBOLT_DEFAULT_BACKEND", "")

	project := t.TempDir()
	configurationPath := filepath.Join(project, "scbolt.yml")
	if err := os.WriteFile(
		configurationPath,
		[]byte("logging: null\nproject_dir: project-value\nspec_file: spec.yml\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(project, ".scbolt"),
		[]byte("CONFIG=scbolt.yml\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(project); err != nil {
		t.Fatal(err)
	}

	configuration, err := effectiveConfig(nil)
	if err != nil {
		t.Fatal(err)
	}
	if setting := configuration.setting("LOGGING"); setting.value != "" || setting.source != "project-config" {
		t.Fatalf("explicit null did not override global configuration: %#v", setting)
	}
	if setting := configuration.setting("PROJECT_DIR"); setting.value != "project-value" || setting.source != "project-config" {
		t.Fatalf("project configuration did not override global configuration: %#v", setting)
	}

	configuration, err = effectiveConfig([]string{
		"config",
		"--logging=true",
		"--project-dir=cli-project",
	})
	if err != nil {
		t.Fatal(err)
	}
	if setting := configuration.setting("LOGGING"); setting.value != "true" || setting.source != "cli" {
		t.Fatalf("CLI did not override project configuration: %#v", setting)
	}
	if setting := configuration.setting("PROJECT_DIR"); setting.value != "cli-project" || setting.source != "cli" {
		t.Fatalf("CLI did not override project configuration: %#v", setting)
	}

	if err := os.WriteFile(
		configurationPath,
		[]byte("spec_file: spec.yml\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	configuration, err = effectiveConfig(nil)
	if err != nil {
		t.Fatal(err)
	}
	if setting := configuration.setting("LOGGING"); setting.value != "false" || setting.source != "user-config" {
		t.Fatalf("global configuration did not override defaults: %#v", setting)
	}
	if setting := configuration.setting("PROJECT_DIR"); setting.value != "global-project" || setting.source != "user-config" {
		t.Fatalf("global configuration did not override defaults: %#v", setting)
	}
}
