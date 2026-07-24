package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/bnediction/scbolt/launcher/internal/completiondata"
)

var (
	commandPattern   = regexp.MustCompile(`^  ([a-z][a-z0-9-]*)[[:space:]]{2,}(.+)$`)
	parameterPattern = regexp.MustCompile(`^  ([A-Z][A-Z0-9_]*)[[:space:]]+(.+)$`)
	optionPattern    = regexp.MustCompile(`^  (--[a-z][a-z0-9-]*(?:=<[^>]+>)?)[[:space:]]+(.+)$`)
)

var moduleAcceptingCommands = map[string]bool{
	"check":    true,
	"clean":    true,
	"config":   true,
	"dry-run":  true,
	"progress": true,
}

var fileOptions = map[string]bool{
	"--binarization-file=": true,
	"--macrostate-files=":  true,
	"--old-file=":          true,
	"--params=":            true,
	"--prior-knowledge=":   true,
	"--project-dir=":       true,
	"--resources-dir=":     true,
	"--spec-file=":         true,
	"--star-whitelist=":    true,
}

func main() {
	root := flag.String("root", ".", "scBOLT repository root")
	output := flag.String(
		"output",
		"launcher/scbolt/completion_manifest.json",
		"generated manifest path",
	)
	params := flag.String(
		"params",
		"quickstart/params.mk",
		"parameter file used to render module help",
	)
	flag.Parse()

	absoluteRoot, err := filepath.Abs(*root)
	check(err)
	manifest, err := generateManifest(absoluteRoot, *params)
	check(err)

	encoded, err := json.MarshalIndent(manifest, "", "  ")
	check(err)
	encoded = append(encoded, '\n')

	outputPath := *output
	if !filepath.IsAbs(outputPath) {
		outputPath = filepath.Join(absoluteRoot, outputPath)
	}
	check(os.MkdirAll(filepath.Dir(outputPath), 0o755))
	check(os.WriteFile(outputPath, encoded, 0o644))
}

func check(err error) {
	if err == nil {
		return
	}
	fmt.Fprintf(os.Stderr, "generate completion manifest: %v\n", err)
	os.Exit(1)
}

func generateManifest(root string, params string) (completiondata.Manifest, error) {
	topHelp, err := scboltOutput(root, "help", "--params", params)
	if err != nil {
		return completiondata.Manifest{}, err
	}
	commands := parseCommands(topHelp)
	commands = appendLauncherCommands(commands)
	globalOptions := mergeOptions(
		parseHelpOptions(topHelp),
		[]completiondata.Option{
			{Name: "--backend=", Values: []string{"conda", "mamba", "micromamba", "docker"}},
			{Name: "--logging=", Values: []string{"true", "false"}},
			{Name: "--target="},
		},
	)
	modules := make([]string, 0)

	for index := range commands {
		command := &commands[index]
		command.AcceptsModules = moduleAcceptingCommands[command.Name]
		if command.Kind == "module" {
			modules = append(modules, command.Name)
			help, helpErr := scboltOutput(
				root,
				command.Name,
				"help",
				"--params",
				params,
			)
			if helpErr != nil {
				command.Options = append(
					[]completiondata.Option{},
					globalOptions...,
				)
				continue
			}
			command.Options = mergeOptions(
				globalOptions,
				parseParameterOptions(help),
			)
			continue
		}

		switch command.Name {
		case "completion", "help", "version":
			command.Options = nil
		case "install":
			continue
		default:
			help, helpErr := scboltOutput(
				root,
				command.Name,
				"help",
				"--params",
				params,
			)
			if helpErr != nil {
				return completiondata.Manifest{}, helpErr
			}
			command.Options = parseHelpOptions(help)
		}
	}

	return completiondata.Manifest{
		SchemaVersion: completiondata.SchemaVersion,
		Commands:      commands,
		Modules:       modules,
		GlobalOptions: globalOptions,
	}, nil
}

func appendLauncherCommands(commands []completiondata.Command) []completiondata.Command {
	commands = append(commands,
		completiondata.Command{
			Name:        "install",
			Description: "install the launcher or runtime backend",
			Kind:        "utility",
			Options: []completiondata.Option{
				{Name: "--backend=", Values: []string{"conda", "mamba", "micromamba", "docker"}},
				{Name: "--help"},
				{Name: "--scbolt-container-engine=", Values: []string{"docker", "podman"}},
				{Name: "--scbolt-image="},
			},
		},
		completiondata.Command{
			Name:        "completion",
			Description: "generate shell completion",
			Kind:        "utility",
		},
	)
	return commands
}

func scboltOutput(root string, args ...string) (string, error) {
	command := exec.Command(filepath.Join(root, "bin", "scbolt"), args...)
	command.Dir = root
	command.Env = append(os.Environ(), "SCBOLT_ROOT="+root)
	var output bytes.Buffer
	var stderr bytes.Buffer
	command.Stdout = &output
	command.Stderr = &stderr
	if err := command.Run(); err != nil {
		return "", fmt.Errorf(
			"scbolt %s failed: %w: %s",
			strings.Join(args, " "),
			err,
			strings.TrimSpace(stderr.String()),
		)
	}
	return output.String(), nil
}

func parseCommands(help string) []completiondata.Command {
	commands := make([]completiondata.Command, 0)
	section := ""
	scanner := bufio.NewScanner(strings.NewReader(help))
	for scanner.Scan() {
		line := scanner.Text()
		if line != "" && !strings.HasPrefix(line, " ") {
			section = line
			continue
		}
		match := commandPattern.FindStringSubmatch(line)
		if len(match) == 0 || strings.HasPrefix(match[1], "--") {
			continue
		}
		kind := "module"
		if section == "Utilities" {
			kind = "utility"
		}
		commands = append(commands, completiondata.Command{
			Name:        match[1],
			Description: strings.TrimSpace(match[2]),
			Kind:        kind,
		})
	}
	return commands
}

func parseHelpOptions(help string) []completiondata.Option {
	options := make([]completiondata.Option, 0)
	scanner := bufio.NewScanner(strings.NewReader(help))
	for scanner.Scan() {
		match := optionPattern.FindStringSubmatch(scanner.Text())
		if len(match) == 0 || match[1] == "--<parameter>=<value>" {
			continue
		}
		name := normalizeOption(match[1])
		options = append(options, completiondata.Option{
			Name: name,
			File: fileOptions[name],
		})
	}
	return uniqueOptions(options)
}

func parseParameterOptions(help string) []completiondata.Option {
	options := make([]completiondata.Option, 0)
	inParameters := false
	scanner := bufio.NewScanner(strings.NewReader(help))
	for scanner.Scan() {
		line := scanner.Text()
		switch line {
		case "Parameters", "Parameters\n----------":
			inParameters = true
			continue
		case "Notes", "Description", "Outputs", "Dependencies":
			inParameters = false
		}
		if !inParameters {
			continue
		}
		match := parameterPattern.FindStringSubmatch(line)
		if len(match) == 0 {
			continue
		}
		name := "--" + strings.ToLower(strings.ReplaceAll(match[1], "_", "-")) + "="
		options = append(options, completiondata.Option{
			Name:   name,
			Values: closedValues(match[2]),
			File:   fileOptions[name],
		})
	}
	return uniqueOptions(options)
}

func normalizeOption(option string) string {
	if strings.Contains(option, "=<") {
		return option[:strings.Index(option, "=<")] + "="
	}
	return option
}

func closedValues(text string) []string {
	start := strings.Index(text, "(")
	end := strings.Index(text, ")")
	if start < 0 || end <= start {
		return nil
	}
	content := text[start+1 : end]
	if !strings.Contains(content, "|") || strings.Contains(content, ">=") {
		return nil
	}
	values := strings.Split(content, "|")
	closed := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value != "" && !strings.ContainsAny(value, " *<>") {
			closed = append(closed, value)
		}
	}
	return closed
}

func mergeOptions(groups ...[]completiondata.Option) []completiondata.Option {
	merged := make([]completiondata.Option, 0)
	for _, group := range groups {
		merged = append(merged, group...)
	}
	return uniqueOptions(merged)
}

func uniqueOptions(options []completiondata.Option) []completiondata.Option {
	byName := make(map[string]completiondata.Option)
	for _, option := range options {
		existing, found := byName[option.Name]
		if found {
			if len(existing.Values) == 0 {
				existing.Values = option.Values
			}
			existing.File = existing.File || option.File
			byName[option.Name] = existing
			continue
		}
		byName[option.Name] = option
	}
	names := make([]string, 0, len(byName))
	for name := range byName {
		names = append(names, name)
	}
	sort.Strings(names)
	unique := make([]completiondata.Option, 0, len(names))
	for _, name := range names {
		unique = append(unique, byName[name])
	}
	return unique
}
