package main

import (
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
)

//go:generate go run . __generate-completion-manifest --root ../.. --output launcher/scbolt/completion_manifest.json

const completionManifestSchemaVersion = 1

type completionManifest struct {
	SchemaVersion int                 `json:"schema_version"`
	Help          string              `json:"help,omitempty"`
	Commands      []completionCommand `json:"commands"`
	Modules       []string            `json:"modules"`
	GlobalOptions []completionOption  `json:"global_options"`
}

type completionCommand struct {
	Name           string             `json:"name"`
	Description    string             `json:"description,omitempty"`
	Kind           string             `json:"kind"`
	AcceptsModules bool               `json:"accepts_modules,omitempty"`
	Options        []completionOption `json:"options,omitempty"`
}

type completionOption struct {
	Name   string   `json:"name"`
	Values []string `json:"values,omitempty"`
	File   bool     `json:"file,omitempty"`
}

//go:embed completion_manifest.json
var embeddedCompletionManifest []byte

var (
	manifestOnce sync.Once
	manifestData completionManifest
	manifestErr  error
)

func handleLauncherCommand(args []string) (bool, error) {
	if len(args) == 0 {
		return false, nil
	}
	switch args[0] {
	case "diagnostics":
		for _, argument := range args[1:] {
			if isHelpToken(argument) {
				fmt.Print(launcherDiagnosticsHelp)
				return true, nil
			}
		}
		return false, nil
	case "completion":
		if len(args) == 2 && (args[1] == "--help" || args[1] == "help") {
			fmt.Print("usage: scbolt completion bash|zsh|fish|powershell\n")
			return true, nil
		}
		if len(args) != 2 {
			return true, errors.New(
				"usage: scbolt completion bash|zsh|fish|powershell",
			)
		}
		script, err := completionScript(args[1])
		if err != nil {
			return true, err
		}
		fmt.Print(script)
		return true, nil
	case "install":
		for _, argument := range args[1:] {
			if argument == "--help" || argument == "-h" || argument == "help" {
				fmt.Print(launcherInstallHelp)
				return true, nil
			}
		}
		return false, nil
	case "__complete":
		candidates, err := completeInvocation(args[1:])
		if err != nil {
			return true, err
		}
		for _, candidate := range candidates {
			fmt.Println(candidate)
		}
		return true, nil
	case "__generate-completion-manifest":
		if err := generateCompletionManifest(args[1:]); err != nil {
			return true, fmt.Errorf("generate completion manifest: %w", err)
		}
		return true, nil
	default:
		return false, nil
	}
}

const launcherInstallHelp = `usage: scbolt install [BACKEND] [--all] [--env=NAME]

Install a scBOLT runtime backend.

Arguments
  BACKEND                conda, mamba, micromamba, or docker

Options
  --all                  install all runtime environments without prompts
  --env=NAME             install one environment; can be repeated
  --backend=BACKEND      alternate syntax for selecting BACKEND
  --scbolt-image=IMAGE   override the Docker image
  --help                 display this help
`

func printLauncherHelp() {
	manifest, err := loadCompletionManifest()
	if err != nil || strings.TrimSpace(manifest.Help) == "" {
		fmt.Println("usage: scbolt <command...> [options]")
		fmt.Println()
		fmt.Println("Use 'scbolt help' for detailed command help.")
		return
	}
	help := strings.Replace(
		manifest.Help,
		"\n\nDownload\n",
		"\n  install                 install a runtime backend\n"+
			"  completion              generate shell completion\n\nDownload\n",
		1,
	)
	fmt.Print(styleLauncherHelp(help, manifest.Commands, isTerminal(os.Stdout)))
}

func styleLauncherHelp(
	help string,
	commands []completionCommand,
	interactive bool,
) string {
	if !interactive {
		return help
	}

	const (
		bold  = "\x1b[1m"
		green = "\x1b[0;32m"
		reset = "\x1b[0m"
	)
	commandNames := make(map[string]struct{}, len(commands))
	for _, command := range commands {
		commandNames[command.Name] = struct{}{}
	}

	lines := strings.Split(help, "\n")
	for index, line := range lines {
		if launcherHelpHeading(lines, index, commandNames) {
			lines[index] = bold + line + reset
			continue
		}
		if len(line) == 0 || (line[0] != ' ' && line[0] != '\t') {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) == 0 {
			continue
		}
		name := fields[0]
		if _, found := commandNames[name]; !found {
			continue
		}
		start := strings.Index(line, name)
		lines[index] = line[:start] + green + name + reset + line[start+len(name):]
	}

	styled := strings.Join(lines, "\n")
	return strings.Replace(
		styled,
		"<command...>",
		green+"<command...>"+reset,
		1,
	)
}

func launcherHelpHeading(
	lines []string,
	index int,
	commandNames map[string]struct{},
) bool {
	line := lines[index]
	if line == "" || line[0] == ' ' || line[0] == '\t' ||
		strings.HasPrefix(line, "usage:") || index+1 >= len(lines) {
		return false
	}
	next := lines[index+1]
	if next == "" || (next[0] != ' ' && next[0] != '\t') {
		return false
	}
	fields := strings.Fields(next)
	if len(fields) == 0 {
		return false
	}
	if strings.HasPrefix(fields[0], "--") {
		return true
	}
	_, found := commandNames[fields[0]]
	return found
}

func loadCompletionManifest() (completionManifest, error) {
	manifestOnce.Do(func() {
		manifestErr = json.Unmarshal(
			embeddedCompletionManifest,
			&manifestData,
		)
		if manifestErr == nil && manifestData.SchemaVersion != completionManifestSchemaVersion {
			manifestErr = fmt.Errorf(
				"unsupported completion manifest schema: %d",
				manifestData.SchemaVersion,
			)
		}
	})
	return manifestData, manifestErr
}

func completeInvocation(args []string) ([]string, error) {
	index := -1
	words := make([]string, 0)
	for position := 0; position < len(args); position++ {
		switch args[position] {
		case "--index":
			if position+1 >= len(args) {
				return nil, errors.New("missing completion cursor index")
			}
			parsed, err := strconv.Atoi(args[position+1])
			if err != nil {
				return nil, fmt.Errorf("invalid completion cursor index: %w", err)
			}
			index = parsed
			position++
		case "--":
			words = append(words, args[position+1:]...)
			position = len(args)
		default:
			return nil, fmt.Errorf("unsupported completion argument: %s", args[position])
		}
	}
	if len(words) == 0 {
		words = []string{"scbolt", ""}
	}
	if index < 0 {
		index = len(words) - 1
	}
	for len(words) <= index {
		words = append(words, "")
	}
	manifest, err := loadCompletionManifest()
	if err != nil {
		return nil, err
	}
	return completeWords(manifest, words, index), nil
}

func completeWords(
	manifest completionManifest,
	words []string,
	index int,
) []string {
	if index < 1 || index >= len(words) {
		return nil
	}
	current := words[index]
	command, commandIndex := findCompletionCommand(manifest, words, index)
	if command == nil {
		candidates := commandNames(manifest)
		candidates = append(candidates, optionNames(manifest.GlobalOptions)...)
		return matchingCandidates(candidates, current)
	}

	if command.Name == "completion" && index > commandIndex {
		return matchingCandidates(
			[]string{"bash", "zsh", "fish", "powershell"},
			current,
		)
	}
	if command.Name == "help" && index > commandIndex {
		return matchingCandidates(commandNames(manifest), current)
	}

	target := completionTarget(manifest, *command, words, commandIndex, index)
	options := completionOptions(manifest, *command, target)
	if option, value, attached := attachedCompletionOption(options, current); attached {
		return completeOptionValue(
			manifest,
			option,
			value,
			option.Name,
			words,
		)
	}
	if index > 0 {
		if option, found := separatedCompletionOption(options, words[index-1]); found {
			return completeOptionValue(
				manifest,
				option,
				current,
				"",
				words,
			)
		}
	}
	if strings.HasPrefix(current, "-") {
		return matchingCandidates(optionNames(options), current)
	}
	if command.Name == "install" &&
		index > commandIndex &&
		!installBackendBeforeCursor(words, commandIndex, index) {
		return matchingCandidates(installBackendNames, current)
	}

	if command.AcceptsModules {
		candidates := append([]string{}, manifest.Modules...)
		candidates = append(candidates, optionNames(options)...)
		return matchingCandidates(candidates, current)
	}
	return matchingCandidates(optionNames(options), current)
}

func installBackendBeforeCursor(
	words []string,
	commandIndex int,
	cursorIndex int,
) bool {
	for position := commandIndex + 1; position < cursorIndex; position++ {
		word := words[position]
		if isInstallBackend(word) ||
			strings.HasPrefix(word, "--backend=") ||
			strings.HasPrefix(strings.ToUpper(word), "BACKEND=") {
			return true
		}
		if word == "--backend" && position+1 < cursorIndex {
			return true
		}
	}
	return false
}

func findCompletionCommand(
	manifest completionManifest,
	words []string,
	index int,
) (*completionCommand, int) {
	commands := make(map[string]*completionCommand)
	for commandIndex := range manifest.Commands {
		command := &manifest.Commands[commandIndex]
		commands[command.Name] = command
	}
	globalOptions := optionMap(manifest.GlobalOptions)
	for position := 1; position < index; position++ {
		word := words[position]
		if command, found := commands[word]; found {
			return command, position
		}
		if strings.HasPrefix(word, "--") && !strings.Contains(word, "=") {
			if option, found := globalOptions[word+"="]; found && option.Name != "" {
				position++
			}
		}
	}
	return nil, -1
}

func completionTarget(
	manifest completionManifest,
	command completionCommand,
	words []string,
	commandIndex int,
	cursorIndex int,
) string {
	if !command.AcceptsModules {
		if command.Kind == "module" {
			return command.Name
		}
		return ""
	}
	modules := make(map[string]bool)
	for _, module := range manifest.Modules {
		modules[module] = true
	}
	for position := commandIndex + 1; position < cursorIndex; position++ {
		if modules[words[position]] {
			return words[position]
		}
	}
	return ""
}

func completionOptions(
	manifest completionManifest,
	command completionCommand,
	target string,
) []completionOption {
	options := append([]completionOption{}, manifest.GlobalOptions...)
	options = append(options, command.Options...)
	if target != "" && target != command.Name {
		if targetCommand := commandByName(manifest, target); targetCommand != nil {
			options = append(options, targetCommand.Options...)
		}
	}
	return uniqueCompletionOptions(options)
}

func attachedCompletionOption(
	options []completionOption,
	current string,
) (completionOption, string, bool) {
	for _, option := range options {
		if !strings.HasSuffix(option.Name, "=") {
			continue
		}
		if strings.HasPrefix(current, option.Name) {
			return option, strings.TrimPrefix(current, option.Name), true
		}
	}
	return completionOption{}, "", false
}

func separatedCompletionOption(
	options []completionOption,
	previous string,
) (completionOption, bool) {
	for _, option := range options {
		if strings.TrimSuffix(option.Name, "=") == previous && strings.HasSuffix(option.Name, "=") {
			return option, true
		}
	}
	return completionOption{}, false
}

func completeOptionValue(
	manifest completionManifest,
	option completionOption,
	prefix string,
	attachedPrefix string,
	words []string,
) []string {
	values := append([]string{}, option.Values...)
	switch option.Name {
	case "--backend=":
		values = []string{"conda", "mamba", "micromamba", "docker"}
	case "--logging=":
		values = []string{"true", "false"}
	case "--references=":
		values = completionReferences(words)
	case "--reset-target=", "--target=", "--trust-target=":
		values = manifest.Modules
	}
	if option.File {
		values = append(values, completeFiles(prefix)...)
	}
	values = matchingCandidatesInOrder(values, prefix)
	if attachedPrefix != "" {
		for index := range values {
			values[index] = attachedPrefix + values[index]
		}
	}
	return values
}

func matchingCandidatesInOrder(candidates []string, prefix string) []string {
	seen := make(map[string]bool)
	matches := make([]string, 0)
	for _, candidate := range candidates {
		if candidate == "" || seen[candidate] || !strings.HasPrefix(candidate, prefix) {
			continue
		}
		seen[candidate] = true
		matches = append(matches, candidate)
	}
	return matches
}

func completionReferences(words []string) []string {
	args := words
	if len(args) > 0 {
		args = args[1:]
	}
	params := paramsPathFromArgs(args)
	if params == "" {
		return nil
	}
	conditions := strings.Fields(readConfigVariable(params, "CONDITIONS"))
	if len(conditions) > 1 {
		conditions = append(conditions, "integrated")
	}
	return conditions
}

func completeFiles(prefix string) []string {
	directory := filepath.Dir(prefix)
	base := filepath.Base(prefix)
	if prefix == "" {
		directory = "."
		base = ""
	} else if strings.HasSuffix(prefix, "/") || strings.HasSuffix(prefix, "\\") {
		directory = filepath.Clean(prefix)
		base = ""
	}
	entries, err := os.ReadDir(directory)
	if err != nil {
		return nil
	}
	candidates := make([]string, 0)
	for _, entry := range entries {
		if !strings.HasPrefix(entry.Name(), base) {
			continue
		}
		candidate := entry.Name()
		if directory != "." {
			candidate = filepath.Join(directory, candidate)
		}
		if entry.IsDir() {
			candidate += string(filepath.Separator)
		}
		candidates = append(candidates, candidate)
	}
	sort.Strings(candidates)
	return candidates
}

func commandByName(
	manifest completionManifest,
	name string,
) *completionCommand {
	for index := range manifest.Commands {
		if manifest.Commands[index].Name == name {
			return &manifest.Commands[index]
		}
	}
	return nil
}

func commandNames(manifest completionManifest) []string {
	names := make([]string, 0, len(manifest.Commands))
	for _, command := range manifest.Commands {
		names = append(names, command.Name)
	}
	return names
}

func optionMap(options []completionOption) map[string]completionOption {
	mapped := make(map[string]completionOption)
	for _, option := range options {
		mapped[option.Name] = option
	}
	return mapped
}

func optionNames(options []completionOption) []string {
	names := make([]string, 0, len(options))
	for _, option := range options {
		names = append(names, option.Name)
	}
	return names
}

func uniqueCompletionOptions(options []completionOption) []completionOption {
	byName := optionMap(options)
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

func matchingCandidates(candidates []string, prefix string) []string {
	seen := make(map[string]bool)
	matches := make([]string, 0)
	for _, candidate := range candidates {
		if candidate == "" || seen[candidate] || !strings.HasPrefix(candidate, prefix) {
			continue
		}
		seen[candidate] = true
		matches = append(matches, candidate)
	}
	sort.Strings(matches)
	return matches
}

func completionScript(shell string) (string, error) {
	switch strings.ToLower(shell) {
	case "bash":
		return bashCompletionScript, nil
	case "zsh":
		return zshCompletionScript, nil
	case "fish":
		return fishCompletionScript, nil
	case "powershell", "pwsh":
		return powershellCompletionScript, nil
	default:
		return "", fmt.Errorf("unsupported completion shell: %s", shell)
	}
}

const bashCompletionScript = `# shellcheck shell=bash
_scbolt_go_complete() {
    local reply
    COMPREPLY=()
    while IFS= read -r reply; do
        COMPREPLY+=("${reply}")
    done < <(command scbolt __complete --index "${COMP_CWORD}" -- "${COMP_WORDS[@]}")
    for reply in "${COMPREPLY[@]}"; do
        if [[ "${reply}" == *= || "${reply}" == */ ]]; then
            compopt -o nospace 2>/dev/null || true
            break
        fi
    done
}
complete -F _scbolt_go_complete scbolt
`

const zshCompletionScript = `#compdef scbolt
_scbolt_go_complete() {
    local -a replies
    replies=("${(@f)$(command scbolt __complete --index $((CURRENT - 1)) -- "${words[@]}")}")
    compadd -Q -a replies
}
compdef _scbolt_go_complete scbolt
`

const fishCompletionScript = `function __scbolt_go_complete
    set -l words (commandline -opc)
    set -l current (commandline -ct)
    set -a words $current
    set -l index (math (count $words) - 1)
    command scbolt __complete --index $index -- $words
end
complete -c scbolt -f -a '(__scbolt_go_complete)'
`

const powershellCompletionScript = `Register-ArgumentCompleter -Native -CommandName scbolt -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)

    $words = @($commandAst.CommandElements | ForEach-Object { $_.Extent.Text })
    if ($words.Count -eq 0) {
        $words = @('scbolt')
    }
    if ($wordToComplete -eq '' -or $words[-1] -ne $wordToComplete) {
        $words += $wordToComplete
    }
    $index = $words.Count - 1

    & scbolt __complete --index $index -- @words | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new(
            $_,
            $_,
            [System.Management.Automation.CompletionResultType]::ParameterValue,
            $_
        )
    }
}
`
