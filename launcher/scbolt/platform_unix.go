//go:build !windows

package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"
)

func executeProcess(path string, argv []string) (int, error) {
	return 1, syscall.Exec(path, argv, os.Environ())
}

func defaultDockerUserArgs() []string {
	return []string{"--user", fmtUserID(os.Getuid(), os.Getgid())}
}

func dockerMountTarget(path string, _ string, _ int) string {
	return path
}

func dockerNeedsPathTranslation() bool {
	return false
}

func fmtUserID(uid int, gid int) string {
	return fmt.Sprintf("%d:%d", uid, gid)
}

func defaultLauncherBinDir() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("cannot determine user home: %w", err)
	}
	return filepath.Join(home, ".local", "bin"), nil
}

func replaceInstalledExecutable(source string, destination string) error {
	return os.Rename(source, destination)
}

func completionInstallPaths() (map[string]string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, fmt.Errorf("cannot determine user home: %w", err)
	}
	dataHome := os.Getenv("XDG_DATA_HOME")
	if dataHome == "" {
		dataHome = filepath.Join(home, ".local", "share")
	}
	configHome, err := os.UserConfigDir()
	if err != nil {
		return nil, fmt.Errorf("cannot determine user configuration directory: %w", err)
	}
	return map[string]string{
		"bash":       filepath.Join(dataHome, "bash-completion", "completions", "scbolt"),
		"fish":       filepath.Join(configHome, "fish", "completions", "scbolt.fish"),
		"powershell": filepath.Join(dataHome, "scbolt", "completions", "scbolt.ps1"),
		"zsh":        filepath.Join(dataHome, "zsh", "site-functions", "_scbolt"),
	}, nil
}

func printPathHint(binDirectory string) {
	for _, path := range filepath.SplitList(os.Getenv("PATH")) {
		if path == binDirectory {
			return
		}
	}
	fmt.Printf("Add to your shell configuration:\n\n  export PATH=\"%s:$PATH\"\n", binDirectory)
}

func printCompletionHint(completions []installedCompletion) {
	for _, completion := range completions {
		if completion.shell == "powershell" {
			fmt.Printf(
				"PowerShell completion can be loaded with:\n\n  . %s\n",
				shellQuote(completion.path),
			)
		}
	}
}

func shellQuote(value string) string {
	if !strings.ContainsAny(value, " '\"") {
		return value
	}
	return "'" + strings.ReplaceAll(value, "'", "'\\''") + "'"
}
