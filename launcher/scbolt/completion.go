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

	"github.com/bnediction/scbolt/launcher/internal/completiondata"
)

//go:generate go run ../generate-completion --root ../.. --output launcher/scbolt/completion_manifest.json

//go:embed completion_manifest.json
var embeddedCompletionManifest []byte

var (
	manifestOnce sync.Once
	manifestData completiondata.Manifest
	manifestErr  error
)

func handleLauncherCommand(args []string) (bool, error) {
	if len(args) == 0 {
		return false, nil
	}
	switch args[0] {
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
	default:
		return false, nil
	}
}

const launcherInstallHelp = `usage: scbolt install --backend=docker [options]

Install the standalone scBOLT launcher and Docker backend.

Options
  --backend=docker               select the Docker runtime backend
  --scbolt-image=<image>         override the scBOLT container image
  --scbolt-container-engine=<e>  select Docker or a compatible engine
  --help                         display this help
`

func completionManifest() (completiondata.Manifest, error) {
	manifestOnce.Do(func() {
		manifestErr = json.Unmarshal(
			embeddedCompletionManifest,
			&manifestData,
		)
		if manifestErr == nil && manifestData.SchemaVersion != completiondata.SchemaVersion {
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
	manifest, err := completionManifest()
	if err != nil {
		return nil, err
	}
	return completeWords(manifest, words, index), nil
}

func completeWords(
	manifest completiondata.Manifest,
	words []string,
	index int,
) []string {
	if index < 1 || index >= len(words) {
		return nil
	}
	current := words[index]
	command, commandIndex := completionCommand(manifest, words, index)
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

	if command.AcceptsModules {
		candidates := append([]string{}, manifest.Modules...)
		candidates = append(candidates, optionNames(options)...)
		return matchingCandidates(candidates, current)
	}
	return matchingCandidates(optionNames(options), current)
}

func completionCommand(
	manifest completiondata.Manifest,
	words []string,
	index int,
) (*completiondata.Command, int) {
	commands := make(map[string]*completiondata.Command)
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
	manifest completiondata.Manifest,
	command completiondata.Command,
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
	manifest completiondata.Manifest,
	command completiondata.Command,
	target string,
) []completiondata.Option {
	options := append([]completiondata.Option{}, manifest.GlobalOptions...)
	options = append(options, command.Options...)
	if target != "" && target != command.Name {
		if targetCommand := commandByName(manifest, target); targetCommand != nil {
			options = append(options, targetCommand.Options...)
		}
	}
	return uniqueCompletionOptions(options)
}

func attachedCompletionOption(
	options []completiondata.Option,
	current string,
) (completiondata.Option, string, bool) {
	for _, option := range options {
		if !strings.HasSuffix(option.Name, "=") {
			continue
		}
		if strings.HasPrefix(current, option.Name) {
			return option, strings.TrimPrefix(current, option.Name), true
		}
	}
	return completiondata.Option{}, "", false
}

func separatedCompletionOption(
	options []completiondata.Option,
	previous string,
) (completiondata.Option, bool) {
	for _, option := range options {
		if strings.TrimSuffix(option.Name, "=") == previous && strings.HasSuffix(option.Name, "=") {
			return option, true
		}
	}
	return completiondata.Option{}, false
}

func completeOptionValue(
	manifest completiondata.Manifest,
	option completiondata.Option,
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
		values = completeFiles(prefix)
	}
	values = matchingCandidates(values, prefix)
	if attachedPrefix != "" {
		for index := range values {
			values[index] = attachedPrefix + values[index]
		}
	}
	return values
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
	if directory == "." && !strings.ContainsAny(prefix, `/\\`) {
		directory = "."
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
	manifest completiondata.Manifest,
	name string,
) *completiondata.Command {
	for index := range manifest.Commands {
		if manifest.Commands[index].Name == name {
			return &manifest.Commands[index]
		}
	}
	return nil
}

func commandNames(manifest completiondata.Manifest) []string {
	names := make([]string, 0, len(manifest.Commands))
	for _, command := range manifest.Commands {
		names = append(names, command.Name)
	}
	return names
}

func optionMap(options []completiondata.Option) map[string]completiondata.Option {
	mapped := make(map[string]completiondata.Option)
	for _, option := range options {
		mapped[option.Name] = option
	}
	return mapped
}

func optionNames(options []completiondata.Option) []string {
	names := make([]string, 0, len(options))
	for _, option := range options {
		names = append(names, option.Name)
	}
	return names
}

func uniqueCompletionOptions(options []completiondata.Option) []completiondata.Option {
	byName := optionMap(options)
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
complete -o bashdefault -o default -F _scbolt_go_complete scbolt
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
