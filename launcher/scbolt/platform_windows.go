//go:build windows

package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

func executeProcess(path string, argv []string) (int, error) {
	command := exec.Command(path, argv[1:]...)
	command.Stdin = os.Stdin
	command.Stdout = os.Stdout
	command.Stderr = os.Stderr
	err := command.Run()
	if err == nil {
		return 0, nil
	}
	var exitError *exec.ExitError
	if errors.As(err, &exitError) {
		return exitError.ExitCode(), nil
	}
	return 1, err
}

func defaultDockerUserArgs() []string {
	return nil
}

func dockerMountTarget(path string, workingDirectory string, index int) string {
	workingDirectory, _ = filepath.Abs(workingDirectory)
	path, _ = filepath.Abs(path)
	if samePath(path, workingDirectory) {
		return "/work"
	}
	return fmt.Sprintf("/mnt/scbolt/%d", index)
}

func dockerNeedsPathTranslation() bool {
	return true
}

func samePath(left string, right string) bool {
	left = filepath.Clean(left)
	right = filepath.Clean(right)
	return strings.EqualFold(left, right)
}

func defaultLauncherBinDir() (string, error) {
	localAppData := os.Getenv("LOCALAPPDATA")
	if localAppData == "" {
		var err error
		localAppData, err = os.UserConfigDir()
		if err != nil {
			return "", fmt.Errorf("cannot determine local application directory: %w", err)
		}
	}
	return filepath.Join(localAppData, "scBOLT", "bin"), nil
}

func replaceInstalledExecutable(source string, destination string) error {
	if err := os.Remove(destination); err != nil && !os.IsNotExist(err) {
		return err
	}
	return os.Rename(source, destination)
}

func completionInstallPaths() (map[string]string, error) {
	localAppData := os.Getenv("LOCALAPPDATA")
	if localAppData == "" {
		var err error
		localAppData, err = os.UserConfigDir()
		if err != nil {
			return nil, fmt.Errorf("cannot determine local application directory: %w", err)
		}
	}
	return map[string]string{
		"powershell": filepath.Join(localAppData, "scBOLT", "completions", "scbolt.ps1"),
	}, nil
}

func printPathHint(binDirectory string) {
	for _, path := range filepath.SplitList(os.Getenv("PATH")) {
		if strings.EqualFold(path, binDirectory) {
			return
		}
	}
	fmt.Printf(
		"Add this directory to your user PATH:\n\n  %s\n",
		binDirectory,
	)
}

func printCompletionHint(completions []installedCompletion) {
	for _, completion := range completions {
		if completion.shell == "powershell" {
			fmt.Printf(
				"Add this line to your PowerShell profile:\n\n  . '%s'\n",
				strings.ReplaceAll(completion.path, "'", "''"),
			)
		}
	}
}
