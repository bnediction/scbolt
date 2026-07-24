package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
)

type installedCompletion struct {
	shell string
	path  string
}

func installDockerLauncher(cfg config) error {
	if err := installCurrentExecutable(); err != nil {
		return err
	}
	configuration := map[string]string{
		"BACKEND":                 "docker",
		"SCBOLT_CONTAINER_ENGINE": cfg.engine,
		"SCBOLT_IMAGE":            cfg.image,
	}
	if cfg.containerArgs != "" {
		configuration["SCBOLT_CONTAINER_ARGS"] = cfg.containerArgs
	}
	if cfg.containerMounts != "" {
		configuration["SCBOLT_CONTAINER_MOUNTS"] = cfg.containerMounts
	}
	if err := updateUserConfig(configuration); err != nil {
		return err
	}
	completions, err := installCompletions()
	if err != nil {
		return err
	}
	if !truthy(os.Getenv("SCBOLT_INSTALL_SKIP_IMAGE")) {
		if _, err := exec.LookPath(cfg.engine); err != nil {
			return fmt.Errorf(
				"Docker backend requested but command not found: %s",
				cfg.engine,
			)
		}
		if !dockerImageExists(cfg.engine, cfg.image) {
			fmt.Printf("Pulling Docker image: %s\n", cfg.image)
			command := exec.Command(cfg.engine, "pull", cfg.image)
			command.Stdin = os.Stdin
			command.Stdout = os.Stdout
			command.Stderr = os.Stderr
			if err := command.Run(); err != nil {
				return fmt.Errorf("failed to pull Docker image %s: %w", cfg.image, err)
			}
		}
	}

	installedExecutable, _ := launcherInstallPath()
	fmt.Printf("Installed launcher: %s\n", installedExecutable)
	fmt.Printf("Installed configuration: %s\n", userConfigPath())
	for _, completion := range completions {
		fmt.Printf(
			"Installed %s completion: %s\n",
			completion.shell,
			completion.path,
		)
	}
	printPathHint(filepath.Dir(installedExecutable))
	printCompletionHint(completions)
	return nil
}

func installCurrentExecutable() error {
	source := os.Getenv("SCBOLT_LAUNCHER_INSTALL_SOURCE")
	if source == "" {
		var err error
		source, err = os.Executable()
		if err != nil {
			return fmt.Errorf("cannot locate launcher executable: %w", err)
		}
	}
	if resolved, err := filepath.EvalSymlinks(source); err == nil {
		source = resolved
	}
	destination, err := launcherInstallPath()
	if err != nil {
		return err
	}
	if sameFile(source, destination) {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(destination), 0o755); err != nil {
		return fmt.Errorf("cannot create launcher directory: %w", err)
	}
	return copyExecutable(source, destination)
}

func launcherInstallPath() (string, error) {
	if directory := os.Getenv("SCBOLT_INSTALL_BIN_DIR"); directory != "" {
		return filepath.Join(directory, executableName()), nil
	}
	directory, err := defaultLauncherBinDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(directory, executableName()), nil
}

func executableName() string {
	if runtime.GOOS == "windows" {
		return "scbolt.exe"
	}
	return "scbolt"
}

func copyExecutable(source string, destination string) error {
	input, err := os.Open(source)
	if err != nil {
		return fmt.Errorf("cannot open launcher executable: %w", err)
	}
	defer input.Close()

	temporary, err := os.CreateTemp(filepath.Dir(destination), ".scbolt-*")
	if err != nil {
		return fmt.Errorf("cannot create temporary launcher: %w", err)
	}
	temporaryPath := temporary.Name()
	defer os.Remove(temporaryPath)

	if _, err := io.Copy(temporary, input); err != nil {
		temporary.Close()
		return fmt.Errorf("cannot copy launcher executable: %w", err)
	}
	if err := temporary.Chmod(0o755); err != nil {
		temporary.Close()
		return fmt.Errorf("cannot set launcher permissions: %w", err)
	}
	if err := temporary.Close(); err != nil {
		return fmt.Errorf("cannot finalize launcher executable: %w", err)
	}
	if err := replaceInstalledExecutable(temporaryPath, destination); err != nil {
		return fmt.Errorf("cannot install launcher executable: %w", err)
	}
	return nil
}

func sameFile(left string, right string) bool {
	leftInfo, leftErr := os.Stat(left)
	rightInfo, rightErr := os.Stat(right)
	return leftErr == nil && rightErr == nil && os.SameFile(leftInfo, rightInfo)
}

func updateUserConfig(assignments map[string]string) error {
	path := userConfigPath()
	if path == "" {
		return fmt.Errorf("cannot determine scBOLT configuration path")
	}
	lines := make([]string, 0)
	if file, err := os.Open(path); err == nil {
		scanner := bufio.NewScanner(file)
		for scanner.Scan() {
			lines = append(lines, scanner.Text())
		}
		file.Close()
		if err := scanner.Err(); err != nil {
			return fmt.Errorf("cannot read scBOLT configuration: %w", err)
		}
	} else if !os.IsNotExist(err) {
		return fmt.Errorf("cannot read scBOLT configuration: %w", err)
	}

	written := make(map[string]bool)
	for index, line := range lines {
		for name, value := range assignments {
			if configAssignmentName(line) == name {
				lines[index] = fmt.Sprintf("%s = %s", name, value)
				written[name] = true
			}
		}
	}
	if len(lines) == 0 {
		lines = append(lines, "# scBOLT user configuration.")
	}
	for _, name := range sortedKeys(assignments) {
		if !written[name] {
			lines = append(lines, fmt.Sprintf("%s = %s", name, assignments[name]))
		}
	}

	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return fmt.Errorf("cannot create scBOLT configuration directory: %w", err)
	}
	content := strings.Join(lines, "\n") + "\n"
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		return fmt.Errorf("cannot write scBOLT configuration: %w", err)
	}
	return nil
}

func configAssignmentName(line string) string {
	line = strings.TrimSpace(stripComment(line))
	for _, operator := range []string{":=", "?=", "="} {
		if index := strings.Index(line, operator); index >= 0 {
			return strings.TrimSpace(line[:index])
		}
	}
	return ""
}

func sortedKeys(values map[string]string) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func installCompletions() ([]installedCompletion, error) {
	paths, err := completionInstallPaths()
	if err != nil {
		return nil, err
	}
	installed := make([]installedCompletion, 0, len(paths))
	for shell, path := range paths {
		script, scriptErr := completionScript(shell)
		if scriptErr != nil {
			return nil, scriptErr
		}
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			return nil, fmt.Errorf("cannot create completion directory: %w", err)
		}
		if err := os.WriteFile(path, []byte(script), 0o644); err != nil {
			return nil, fmt.Errorf("cannot install %s completion: %w", shell, err)
		}
		installed = append(installed, installedCompletion{shell: shell, path: path})
	}
	sort.Slice(installed, func(left int, right int) bool {
		return installed[left].shell < installed[right].shell
	})
	return installed, nil
}
