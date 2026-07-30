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
)

var (
	commandPattern   = regexp.MustCompile(`^  ([a-z][a-z0-9-]*)[[:space:]]{2,}(.+)$`)
	parameterPattern = regexp.MustCompile(`^  ([A-Za-z][A-Za-z0-9_.-]*)[[:space:]]+(.+)$`)
	optionPattern    = regexp.MustCompile(`^  (--[a-z][a-z0-9-]*(?:=<[^>]+>)?)[[:space:]]+(.+)$`)
	ansiPattern      = regexp.MustCompile(`\x1b\[[0-9;]*m`)
)

var moduleAcceptingCommands = map[string]bool{
	"check":    true,
	"clean":    true,
	"config":   true,
	"dry-run":  true,
	"progress": true,
}

var modulesWithoutDedicatedHelp = map[string]bool{
	"load-genome":     true,
	"load-signatures": true,
	"load-cc":         true,
	"load-go":         true,
}

var fileOptions = map[string]bool{
	"--binarization-file=": true,
	"--macrostate-files=":  true,
	"--old-file=":          true,
	"--config=":            true,
	"--params=":            true,
	"--prior-knowledge=":   true,
	"--project-dir=":       true,
	"--resources-dir=":     true,
	"--spec-file=":         true,
	"--star-whitelist=":    true,
}

var clingoConfigurations = []string{
	"auto",
	"frumpy",
	"jumpy",
	"tweety",
	"handy",
	"crafty",
	"trendy",
	"many",
}

var clingoStrategies = []string{
	"bb",
	"bb,lin",
	"bb,hier",
	"bb,inc",
	"bb,dec",
	"usc",
	"usc,oll",
	"usc,one",
	"usc,k",
	"usc,pmres",
}

var priorKnowledgeValues = []string{
	"dorothea",
	"collectri",
}

var organismValues = []string{
	"mouse",
	"human",
}

func generateCompletionManifest(arguments []string) error {
	flags := flag.NewFlagSet("__generate-completion-manifest", flag.ContinueOnError)
	root := flags.String("root", ".", "scBOLT repository root")
	output := flags.String(
		"output",
		"launcher/scbolt/completion_manifest.json",
		"generated manifest path",
	)
	configuration := flags.String(
		"config",
		"quickstart/scbolt.yml",
		"configuration file used to render module help",
	)
	if err := flags.Parse(arguments); err != nil {
		return err
	}

	absoluteRoot, err := filepath.Abs(*root)
	if err != nil {
		return err
	}
	manifest, err := generateManifest(absoluteRoot, *configuration)
	if err != nil {
		return err
	}

	encoded, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	encoded = append(encoded, '\n')

	outputPath := *output
	if !filepath.IsAbs(outputPath) {
		outputPath = filepath.Join(absoluteRoot, outputPath)
	}
	if err := os.MkdirAll(filepath.Dir(outputPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(outputPath, encoded, 0o644)
}

func generateManifest(root string, configuration string) (completionManifest, error) {
	topHelp, err := scboltOutput(root, "help", "--config", configuration)
	if err != nil {
		return completionManifest{}, err
	}
	topHelp = stripLauncherHelpCommands(topHelp)
	commands := parseCommands(topHelp)
	commands = appendLauncherCommands(commands)
	globalOptions := mergeOptions(
		parseHelpOptions(topHelp),
		[]completionOption{
			{Name: "--backend=", Values: []string{"conda", "mamba", "micromamba", "docker"}},
			{Name: "--logging=", Values: []string{"true", "false"}},
			{Name: "--organism=", Values: append([]string{}, organismValues...)},
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
				"--config",
				configuration,
			)
			if helpErr != nil {
				if !modulesWithoutDedicatedHelp[command.Name] {
					return completionManifest{}, helpErr
				}
				command.Options = append(
					[]completionOption{},
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
		case "diagnostics", "help", "version":
			command.Options = nil
		case "install":
			continue
		default:
			help, helpErr := scboltOutput(
				root,
				command.Name,
				"help",
				"--config",
				configuration,
			)
			if helpErr != nil {
				return completionManifest{}, helpErr
			}
			command.Options = parseHelpOptions(help)
		}
	}

	return completionManifest{
		SchemaVersion: completionManifestSchemaVersion,
		Help:          topHelp,
		Commands:      commands,
		Modules:       modules,
		GlobalOptions: globalOptions,
	}, nil
}

func stripLauncherHelpCommands(help string) string {
	lines := strings.Split(help, "\n")
	filtered := make([]string, 0, len(lines))
	for _, line := range lines {
		fields := strings.Fields(line)
		if len(fields) > 0 && fields[0] == "install" {
			continue
		}
		filtered = append(filtered, line)
	}
	return strings.Join(filtered, "\n")
}

func appendLauncherCommands(commands []completionCommand) []completionCommand {
	launcherCommand := completionCommand{
		Name:        "install",
		Description: "install a runtime backend",
		Kind:        "utility",
		Options: []completionOption{
			{Name: "--all"},
			{Name: "--backend=", Values: installBackendNames},
			{Name: "--completions"},
			{Name: "--env=", Values: installEnvironmentSuffixes},
			{Name: "--help"},
			{Name: "--scbolt-container-engine=", Values: []string{"docker", "podman"}},
			{Name: "--scbolt-image="},
		},
	}
	for index := range commands {
		if commands[index].Name == launcherCommand.Name {
			commands[index] = launcherCommand
			return commands
		}
	}
	return append(commands, launcherCommand)
}

func scboltOutput(root string, args ...string) (string, error) {
	executable, err := os.Executable()
	if err != nil {
		return "", err
	}
	command := exec.Command(executable, args...)
	command.Dir = root
	command.Env = append(
		os.Environ(),
		"MAKE_TERMOUT=",
		"SCBOLT_GENERATING_COMPLETION_MANIFEST=true",
		"SCBOLT_ROOT="+root,
	)
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
	return cleanScboltOutput(output.String()), nil
}

func cleanScboltOutput(output string) string {
	output = ansiPattern.ReplaceAllString(output, "")
	lines := strings.Split(output, "\n")
	cleaned := make([]string, 0, len(lines))
	for _, line := range lines {
		if strings.HasPrefix(line, "make") &&
			(strings.Contains(line, "Entering directory") ||
				strings.Contains(line, "Leaving directory")) {
			continue
		}
		cleaned = append(cleaned, line)
	}
	return strings.Join(cleaned, "\n")
}

func parseCommands(help string) []completionCommand {
	commands := make([]completionCommand, 0)
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
		commands = append(commands, completionCommand{
			Name:        match[1],
			Description: strings.TrimSpace(match[2]),
			Kind:        kind,
		})
	}
	return commands
}

func parseHelpOptions(help string) []completionOption {
	options := make([]completionOption, 0)
	scanner := bufio.NewScanner(strings.NewReader(help))
	for scanner.Scan() {
		match := optionPattern.FindStringSubmatch(scanner.Text())
		if len(match) == 0 || match[1] == "--<parameter>=<value>" {
			continue
		}
		name := normalizeOption(match[1])
		options = append(options, completionOption{
			Name: name,
			File: fileOptions[name],
		})
	}
	return uniqueOptions(options)
}

func parseParameterOptions(help string) []completionOption {
	options := make([]completionOption, 0)
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
		if match[1] == "configuration" {
			continue
		}
		publicKey := publicConfigurationKey(match[1])
		name := "--" + strings.NewReplacer("_", "-", ".", "-").Replace(publicKey) + "="
		internalName := internalConfigurationVariable(publicKey)
		options = append(options, completionOption{
			Name:   name,
			Values: parameterValues(internalName, match[2]),
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

func parameterValues(parameter string, hint string) []string {
	switch {
	case parameter == "PRIOR_KNOWLEDGE":
		return append([]string{}, priorKnowledgeValues...)
	case parameter == "ORGANISM":
		return append([]string{}, organismValues...)
	case strings.HasPrefix(parameter, "CLINGO_CONFIG_"):
		return append([]string{}, clingoConfigurations...)
	case strings.HasPrefix(parameter, "CLINGO_STRATEGY_"):
		return append([]string{}, clingoStrategies...)
	default:
		return closedValues(hint)
	}
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

func mergeOptions(groups ...[]completionOption) []completionOption {
	merged := make([]completionOption, 0)
	for _, group := range groups {
		merged = append(merged, group...)
	}
	return uniqueOptions(merged)
}

func uniqueOptions(options []completionOption) []completionOption {
	byName := make(map[string]completionOption)
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
	unique := make([]completionOption, 0, len(names))
	for _, name := range names {
		unique = append(unique, byName[name])
	}
	return unique
}
