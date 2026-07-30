package main

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

var scboltModules = []string{
	"load-genome", "load-fastq", "load-matrix", "load-signatures", "load-cc", "load-go",
	"alignment", "cellranger", "star", "qc", "velocyto",
	"filtering", "normalization", "clustering", "dea", "scoring", "goea", "annotation",
	"velocity", "potency", "cotan", "cellrank", "stream", "knnsc", "macrostates",
	"bin-cells", "bin-macrostates", "bin-dea", "bin-consensus", "binarization",
	"spec", "max-nodes-soft", "max-consts-soft", "max-nodes-relaxed",
	"max-nodes-seed", "max-nodes-lock", "bn-min", "bn-submin", "bn-diverse",
}

var scboltCommands = append(
	[]string{
		"init", "help", "version", "config", "progress", "check", "diagnostics",
		"dry-run", "clean", "install", "completion",
	},
	scboltModules...,
)

var (
	interruptPattern = regexp.MustCompile(
		`Error 130(?:$|[^0-9])|KeyboardInterrupt|(?:^|[^[:alpha:]])Interrupt(?:$|[^[:alpha:]])`,
	)
	terminationPattern = regexp.MustCompile(`Error 143(?:$|[^0-9])`)
	timeoutPattern     = regexp.MustCompile(
		`Error 124(?:$|[^0-9])|user-defined time limit reached|timed out|timeout`,
	)
	rulePattern  = regexp.MustCompile(` - RULE - `)
	stalePattern = regexp.MustCompile(
		` - WARNING - (?:stale|untracked|missing module metadata)`,
	)
	inferenceRulePattern = regexp.MustCompile(
		` - RULE - (max-nodes-soft|max-consts-soft|max-nodes-relaxed|max-nodes-seed|max-nodes-lock|bn-min|bn-submin|bn-diverse)(?:[ \r\n]|$)`,
	)
)

type localCLI struct {
	root    string
	config  config
	runtime *localRuntime
}

type translatedArguments struct {
	makeArgs       []string
	positionals    []string
	params         string
	projectRoot    string
	paramsFromCLI  string
	paramsFromMake string
}

func runLocal(root string, cfg config, args []string) (int, error) {
	cli := &localCLI{root: root, config: cfg}
	return cli.run(args)
}

func (cli *localCLI) run(args []string) (int, error) {
	if len(args) == 0 || isHelpToken(args[0]) {
		return cli.runTopLevelHelp()
	}

	leading, remaining, err := splitLeadingArguments(args)
	if err != nil {
		return 2, err
	}
	if len(remaining) == 0 {
		return cli.runTopLevelHelp()
	}
	command := remaining[0]
	commandArgs := remaining[1:]
	if command == "macrostate" {
		command = "macrostates"
	}

	switch command {
	case "", "help", "-h", "--help":
		return cli.runTopLevelHelp()
	case "version":
		printLauncherVersion()
		return 0, nil
	case "clean":
		return cli.runClean(leading, commandArgs)
	case "progress":
		return cli.runProgress(leading, commandArgs)
	case "check", "dry-run", "config":
		return cli.runDiagnostic(command, leading, commandArgs)
	default:
		if !containsString(scboltModules, command) {
			printFailureStatus(command)
			if suggestion := closestChoice(command, scboltCommands); suggestion != "" {
				fmt.Fprintf(os.Stderr, "did you mean: scbolt %s\n", suggestion)
			}
			return 2, nil
		}
		return cli.runModule(command, leading, commandArgs)
	}
}

func (cli *localCLI) getRuntime(projectRoot string) (*localRuntime, error) {
	if cli.runtime == nil {
		local, err := newLocalRuntime(cli.root, cli.config)
		if err != nil {
			return nil, err
		}
		cli.runtime = local
	}
	cli.runtime.projectRoot = projectRoot
	return cli.runtime, nil
}

func splitLeadingArguments(args []string) ([]string, []string, error) {
	leading := make([]string, 0)
	for index := 0; index < len(args); index++ {
		argument := args[index]
		switch {
		case takesSeparatedGlobalValue(argument):
			if index+1 >= len(args) {
				return nil, nil, fmt.Errorf("Missing value for %s", argument)
			}
			leading = append(leading, argument, args[index+1])
			index++
		case argument == "--trust-existing" || argument == "--raw":
			leading = append(leading, argument)
		case strings.HasPrefix(argument, "--trust-existing="):
			return nil, nil, errors.New(
				"Unsupported scbolt option with value: --trust-existing; use '--trust-existing' without a value",
			)
		case strings.HasPrefix(argument, "--raw="):
			return nil, nil, errors.New(
				"Unsupported scbolt option with value: --raw; use '--raw' without a value",
			)
		case argument == "--level" || strings.HasPrefix(argument, "--level="):
			return nil, nil, errors.New(
				"Unsupported scbolt option: --level; use '--raw' to display the raw config listing",
			)
		case strings.HasPrefix(argument, "--") && strings.Contains(argument, "="):
			leading = append(leading, argument)
		case strings.Contains(argument, "="):
			leading = append(leading, argument)
		case strings.HasPrefix(argument, "--"):
			return nil, nil, unsupportedOptionError("global", argument)
		default:
			return leading, args[index:], nil
		}
	}
	return leading, nil, nil
}

func takesSeparatedGlobalValue(argument string) bool {
	switch argument {
	case "--params", "--references", "--reset-target", "--trust-target",
		"--old-file", "--logging", "--target", "--backend":
		return true
	default:
		return false
	}
}

func (cli *localCLI) translate(command string, args []string) (translatedArguments, error) {
	translated := translatedArguments{}
	for index := 0; index < len(args); index++ {
		argument := args[index]
		valueFor := func(option string) (string, error) {
			if strings.HasPrefix(argument, option+"=") {
				return strings.TrimPrefix(argument, option+"="), nil
			}
			if index+1 >= len(args) {
				return "", fmt.Errorf("Missing value for %s", option)
			}
			index++
			return args[index], nil
		}

		switch {
		case argument == "--params" || strings.HasPrefix(argument, "--params="):
			value, err := valueFor("--params")
			if err != nil {
				return translated, err
			}
			translated.paramsFromCLI = value
		case argument == "--references" || strings.HasPrefix(argument, "--references="):
			value, err := valueFor("--references")
			if err != nil {
				return translated, err
			}
			translated.makeArgs = append(translated.makeArgs, "REFERENCES="+value)
		case argument == "--reset-target" || strings.HasPrefix(argument, "--reset-target="):
			value, err := valueFor("--reset-target")
			if err != nil {
				return translated, err
			}
			translated.makeArgs = append(translated.makeArgs, "CLI_RESET_TARGETS+="+value)
		case argument == "--trust-target" || strings.HasPrefix(argument, "--trust-target="):
			value, err := valueFor("--trust-target")
			if err != nil {
				return translated, err
			}
			translated.makeArgs = append(translated.makeArgs, "CLI_TRUST_TARGETS+="+value)
		case argument == "--trust-existing":
			translated.makeArgs = append(translated.makeArgs, "TRUST_EXISTING=true")
		case strings.HasPrefix(argument, "--trust-existing="):
			return translated, errors.New(
				"Unsupported scbolt option with value: --trust-existing; use '--trust-existing' without a value",
			)
		case argument == "--old-file" || strings.HasPrefix(argument, "--old-file="):
			value, err := valueFor("--old-file")
			if err != nil {
				return translated, err
			}
			translated.makeArgs = append(translated.makeArgs, "CLI_OLD_FILES+="+value)
		case argument == "--logging" || strings.HasPrefix(argument, "--logging="):
			value, err := valueFor("--logging")
			if err != nil {
				return translated, err
			}
			translated.makeArgs = append(translated.makeArgs, "LOGGING="+value)
		case argument == "--target" || strings.HasPrefix(argument, "--target="):
			value, err := valueFor("--target")
			if err != nil {
				return translated, err
			}
			translated.makeArgs = append(translated.makeArgs, "TARGET="+value)
		case argument == "--backend" || strings.HasPrefix(argument, "--backend="):
			value, err := valueFor("--backend")
			if err != nil {
				return translated, err
			}
			if !containsString([]string{"conda", "mamba", "micromamba", "docker"}, value) {
				return translated, fmt.Errorf("Unsupported backend: %s", value)
			}
			translated.makeArgs = append(translated.makeArgs, "BACKEND="+value)
		case argument == "--raw":
			translated.makeArgs = append(translated.makeArgs, "CONFIG_RAW=true")
		case strings.HasPrefix(argument, "--raw="):
			return translated, errors.New(
				"Unsupported scbolt option with value: --raw; use '--raw' without a value",
			)
		case argument == "--level" || strings.HasPrefix(argument, "--level="):
			return translated, errors.New(
				"Unsupported scbolt option: --level; use '--raw' to display the raw config listing",
			)
		case strings.EqualFold(assignmentName(argument), "RESET_TARGET"):
			translated.makeArgs = append(translated.makeArgs, "RESET_TARGET="+assignmentValue(argument))
		case strings.EqualFold(assignmentName(argument), "TRUST_TARGET"):
			translated.makeArgs = append(translated.makeArgs, "TRUST_TARGET="+assignmentValue(argument))
		case strings.EqualFold(assignmentName(argument), "TRUST_EXISTING"):
			translated.makeArgs = append(translated.makeArgs, "TRUST_EXISTING="+assignmentValue(argument))
		case strings.EqualFold(assignmentName(argument), "OLD_FILES"):
			translated.makeArgs = append(translated.makeArgs, "OLD_FILES="+assignmentValue(argument))
		case strings.EqualFold(assignmentName(argument), "OLD_FILE"):
			translated.makeArgs = append(translated.makeArgs, "CLI_OLD_FILES+="+assignmentValue(argument))
		case strings.HasPrefix(argument, "--") && strings.Contains(argument, "="):
			name, value, _ := strings.Cut(argument, "=")
			translated.makeArgs = append(
				translated.makeArgs,
				optionMakeVariable(name)+"="+value,
			)
		case strings.HasPrefix(argument, "PARAMS="):
			translated.paramsFromMake = strings.TrimPrefix(argument, "PARAMS=")
		case strings.Contains(argument, "="):
			translated.makeArgs = append(translated.makeArgs, argument)
		case strings.HasPrefix(argument, "--"):
			return translated, unsupportedOptionError(command, argument)
		default:
			translated.positionals = append(translated.positionals, argument)
		}
	}

	translated.params = translated.paramsFromCLI
	if translated.params == "" {
		translated.params = translated.paramsFromMake
	}
	if translated.params == "" {
		translated.params = resolveProjectParams()
	}
	if projectFile := findProjectFileFromCwd(); projectFile != "" {
		translated.projectRoot = filepath.Dir(projectFile)
	}
	return translated, nil
}

func optionMakeVariable(option string) string {
	name := strings.TrimPrefix(option, "--")
	name = strings.ReplaceAll(name, "-", "_")
	return strings.ToUpper(name)
}

func assignmentName(argument string) string {
	name, _, found := strings.Cut(argument, "=")
	if !found {
		return ""
	}
	return name
}

func assignmentValue(argument string) string {
	_, value, _ := strings.Cut(argument, "=")
	return value
}

func readProjectParams(projectFile string) string {
	data, err := os.ReadFile(projectFile)
	if err != nil {
		return ""
	}
	for _, raw := range strings.Split(string(data), "\n") {
		line := strings.TrimSpace(raw)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "PARAMS") {
			if name, value, found := strings.Cut(line, "="); found && strings.TrimSpace(name) == "PARAMS" {
				return strings.TrimSpace(value)
			}
		}
		return line
	}
	return ""
}

func requireParamsFile(params string) error {
	if params == "" {
		return errors.New(
			"No parameter file found.\n\nRun:\n  scbolt init <params.mk>\nor:\n  scbolt <target> --params=<file>",
		)
	}
	path := params
	if !filepath.IsAbs(path) {
		workingDirectory, _ := os.Getwd()
		path = filepath.Join(workingDirectory, path)
	}
	if !exists(path) {
		return fmt.Errorf("Parameter file not found: %s", params)
	}
	if filepath.Ext(params) != ".mk" {
		return fmt.Errorf("Parameter file must have a .mk extension: %s", params)
	}
	return nil
}

func (cli *localCLI) runTopLevelHelp() (int, error) {
	arguments := []string{"help", "SCBOLT_CLI=true"}
	if params := optionalParamsAssignment(); params != "" {
		arguments = append(arguments, params)
	}
	return cli.runMakeAttached("", arguments, false)
}

func optionalParamsAssignment() string {
	params := resolveProjectParams()
	if params == "" {
		return ""
	}
	path := params
	if !filepath.IsAbs(path) {
		workingDirectory, _ := os.Getwd()
		path = filepath.Join(workingDirectory, path)
	}
	if exists(path) {
		return "PARAMS=" + params
	}
	return ""
}

func (cli *localCLI) runMakeHelp(command string) (int, error) {
	arguments := []string{command, "HELP=true", "SCBOLT_CLI=true"}
	if params := optionalParamsAssignment(); params != "" {
		arguments = append(arguments, params)
	}
	return cli.runMakeAttached("", arguments, false)
}

func (cli *localCLI) runClean(leading []string, args []string) (int, error) {
	if hasHelpRequest(args) {
		return cli.runMakeHelp("clean")
	}
	cleanAll := false
	cleanStale := false
	cleanForce := false
	filtered := make([]string, 0, len(args))
	for _, argument := range args {
		switch argument {
		case "--all":
			cleanAll = true
		case "--stale":
			cleanStale = true
		case "--force":
			cleanForce = true
		default:
			if strings.HasPrefix(argument, "--all=") ||
				strings.HasPrefix(argument, "--stale=") ||
				strings.HasPrefix(argument, "--force=") {
				name := strings.SplitN(argument, "=", 2)[0]
				return 2, fmt.Errorf(
					"Unsupported scbolt option with value: %s; use '%s' without a value",
					name,
					name,
				)
			}
			filtered = append(filtered, argument)
		}
	}
	translated, err := cli.translate("clean", append(leading, filtered...))
	if err != nil {
		return 2, err
	}
	if cleanAll && len(translated.positionals) > 0 {
		return 2, errors.New("Use either '--all' or explicit modules, not both")
	}
	if cleanAll {
		translated.makeArgs = append(translated.makeArgs, "CLEAN_TARGET=all")
	} else if cleanStale {
		translated.makeArgs = append(translated.makeArgs, "CLEAN_STALE=true")
		if len(translated.positionals) > 0 {
			translated.makeArgs = append(
				translated.makeArgs,
				"CLEAN_TARGET="+strings.Join(translated.positionals, " "),
			)
		}
	} else if len(translated.positionals) > 0 {
		translated.makeArgs = append(
			translated.makeArgs,
			"CLEAN_TARGET="+strings.Join(translated.positionals, " "),
		)
	}
	if cleanForce {
		translated.makeArgs = append(translated.makeArgs, "CLEAN_FORCE=true")
	}
	return cli.runMakeWithParams(translated, translated.makeArgs, false)
}

func (cli *localCLI) runProgress(leading []string, args []string) (int, error) {
	if hasHelpRequest(args) {
		return cli.runMakeHelp("progress")
	}
	progressAll := false
	filtered := make([]string, 0, len(args))
	for _, argument := range args {
		if argument == "--all" {
			progressAll = true
		} else if strings.HasPrefix(argument, "--all=") {
			return 2, errors.New(
				"Unsupported scbolt option with value: --all; use '--all' without a value",
			)
		} else {
			filtered = append(filtered, argument)
		}
	}
	translated, err := cli.translate("progress", append(leading, filtered...))
	if err != nil {
		return 2, err
	}
	if progressAll {
		translated.makeArgs = append(translated.makeArgs, "PROGRESS_ALL=true")
	}
	if len(translated.positionals) > 0 {
		translated.makeArgs = append(
			translated.makeArgs,
			"TARGET="+strings.Join(translated.positionals, " "),
		)
	}
	return cli.runMakeWithParams(translated, translated.makeArgs, false)
}

func (cli *localCLI) runDiagnostic(
	command string,
	leading []string,
	args []string,
) (int, error) {
	if hasHelpRequest(args) {
		return cli.runMakeHelp(command)
	}
	configDefault := false
	filtered := append([]string{}, args...)
	if command == "config" {
		filtered = filtered[:0]
		for _, argument := range args {
			if argument == "--default" {
				configDefault = true
			} else if strings.HasPrefix(argument, "--default=") {
				return 2, errors.New(
					"Unsupported scbolt option with value: --default; use '--default' without a value",
				)
			} else {
				filtered = append(filtered, argument)
			}
		}
	}
	translated, err := cli.translate(command, append(leading, filtered...))
	if err != nil {
		return 2, err
	}
	if command == "dry-run" && len(translated.positionals) == 0 &&
		!hasAssignment(translated.makeArgs, "TARGET") {
		return 2, errors.New(
			"Missing module for scbolt dry-run.\nUsage: scbolt dry-run <module>\nRun 'scbolt dry-run --help' for details",
		)
	}
	if command == "config" && len(translated.positionals) > 0 {
		target := translated.positionals[0]
		translated.makeArgs = append(
			[]string{"TARGET=" + target},
			append(translated.positionals[1:], translated.makeArgs...)...,
		)
	}
	if configDefault {
		arguments := append([]string{"config", "DEFAULT_CONFIG=true"}, translated.makeArgs...)
		return cli.runMakeAttached(translated.projectRoot, arguments, false)
	}
	if command == "check" && len(translated.positionals) > 0 {
		target := translated.positionals[0]
		arguments := []string{"check", "TARGET=" + target}
		arguments = append(arguments, translated.positionals[1:]...)
		arguments = append(arguments, translated.makeArgs...)
		return cli.runMakeWithParams(translated, arguments, true)
	}
	if command != "config" && command != "check" && len(translated.positionals) > 0 {
		target := translated.positionals[0]
		arguments := []string{command, "TARGET=" + target}
		arguments = append(arguments, translated.positionals[1:]...)
		arguments = append(arguments, translated.makeArgs...)
		return cli.runMakeWithParams(translated, arguments, false)
	}
	arguments := append([]string{command}, translated.makeArgs...)
	return cli.runMakeWithParams(translated, arguments, command == "check")
}

func (cli *localCLI) runModule(
	module string,
	leading []string,
	args []string,
) (int, error) {
	if hasHelpRequest(args) {
		filtered := dropHelpArguments(args)
		translated, err := cli.translate(module, append(leading, filtered...))
		if err != nil {
			return 2, err
		}
		arguments := []string{"module-help", "TARGET=" + module}
		arguments = append(arguments, translated.makeArgs...)
		arguments = append(arguments, "SCBOLT_CLI=true")
		return cli.runMakeWithParams(translated, arguments, false)
	}

	translated, err := cli.translate(module, append(leading, args...))
	if err != nil {
		return 2, err
	}
	if err := requireParamsFile(translated.params); err != nil {
		return 1, err
	}
	label := module
	if len(translated.positionals) > 0 {
		label += " " + strings.Join(translated.positionals, " ")
	}
	label = cli.targetLabelWithReferences(translated, label)
	arguments := append([]string{module}, translated.positionals...)
	arguments = append(arguments, translated.makeArgs...)
	return cli.runMakeBuild(translated, label, arguments)
}

func (cli *localCLI) runMakeWithParams(
	translated translatedArguments,
	arguments []string,
	filterErrors bool,
) (int, error) {
	if err := requireParamsFile(translated.params); err != nil {
		return 1, err
	}
	arguments = append(arguments, "PARAMS="+translated.params)
	return cli.runMakeAttached(translated.projectRoot, arguments, filterErrors)
}

func (cli *localCLI) runMakeAttached(
	projectRoot string,
	arguments []string,
	filterErrors bool,
) (int, error) {
	local, err := cli.getRuntime(projectRoot)
	if err != nil {
		return 1, err
	}
	command := local.makeCommand(arguments...)
	terminal, terminalErr := openTerminalInput()
	if terminalErr == nil {
		command.Stdin = terminal
		if terminal != os.Stdin {
			defer terminal.Close()
		}
	} else {
		command.Stdin = os.Stdin
	}
	command.Stdout = os.Stdout
	var stderr *makeOutputWriter
	if filterErrors {
		stderr = newMakeOutputWriter(os.Stderr)
		command.Stderr = stderr
	} else {
		command.Stderr = os.Stderr
	}
	result, err := runManagedProcess(command)
	if stderr != nil {
		_ = stderr.flush()
	}
	return result.status, err
}

func (cli *localCLI) runMakeCapture(
	projectRoot string,
	arguments ...string,
) (string, error) {
	local, err := cli.getRuntime(projectRoot)
	if err != nil {
		return "", err
	}
	command := local.makeCommand(arguments...)
	var stdout bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = io.Discard
	if err := command.Run(); err != nil {
		return "", err
	}
	return stdout.String(), nil
}

func (cli *localCLI) runMakeBuild(
	translated translatedArguments,
	label string,
	arguments []string,
) (int, error) {
	local, err := cli.getRuntime(translated.projectRoot)
	if err != nil {
		return 1, err
	}
	workflowArguments := append([]string{}, arguments...)
	makeArguments := append([]string{}, workflowArguments...)
	makeArguments = append(makeArguments, "PARAMS="+translated.params)
	terminal, terminalErr := openTerminalInput()
	interactive := terminalErr == nil
	if interactive {
		makeArguments = append(makeArguments, "SCBOLT_INTERACTIVE=true")
	}
	command := local.makeCommand(makeArguments...)
	if interactive {
		command.Stdin = terminal
		if terminal != os.Stdin {
			defer terminal.Close()
		}
	} else {
		command.Stdin = os.Stdin
	}
	stdout := newMakeOutputWriter(os.Stdout)
	stderr := newMakeOutputWriter(os.Stderr)
	command.Stdout = stdout
	command.Stderr = stderr
	restoreTerminal := local.hideControlCharacters(terminal, interactive)
	defer restoreTerminal()

	started := time.Now()
	result, runErr := runManagedProcess(command)
	_ = stdout.flush()
	_ = stderr.flush()
	if runErr != nil {
		return 1, runErr
	}
	stdoutSummary := stdout.summary()
	stderrSummary := stderr.summary()
	finalStatus := classifyBuildStatus(result, stderrSummary)
	if (finalStatus == 130 || finalStatus == 143) && interactive {
		clearTerminalLine(terminal)
	} else if needsOutputNewline(stdoutSummary, stderrSummary) {
		fmt.Println()
	}

	elapsed := time.Since(started)
	if elapsed < time.Second {
		elapsed = time.Second
	}
	switch finalStatus {
	case 0:
		if stdoutSummary.rule {
			printSuccessStatus(label)
		} else if stdoutSummary.stale {
			printWarningStatus("already built", label)
		} else {
			printWarningStatus(
				"up to date",
				cli.targetLabelWithIntermediateStatus(
					translated,
					label,
					workflowArguments,
				),
			)
		}
	case 124:
		printWarningStatus("reached time limit", label)
	case 130, 143:
		printWarning("interrupted by user (" + label + ")")
		interruptedModule := stdoutSummary.inferenceModule
		if interruptedModule == "" {
			interruptedModule = label
		}
		cli.finalizeInterruptedResults(
			translated,
			interruptedModule,
			formatElapsedDuration(elapsed),
			workflowArguments,
		)
		cli.printKeptIntermediateResults(
			translated,
			stdoutSummary.inferenceModule,
			label,
			workflowArguments,
		)
	default:
		printFailureStatus(label)
	}
	return result.status, nil
}

func classifyBuildStatus(result processResult, stderr makeOutputSummary) int {
	if result.interrupted {
		return 130
	}
	if stderr.interrupted {
		return 130
	}
	if stderr.terminated {
		return 143
	}
	if stderr.timedOut {
		return 124
	}
	return result.status
}

func needsOutputNewline(outputs ...makeOutputSummary) bool {
	for _, output := range outputs {
		if output.hasOutput && output.lastByte != '\n' {
			return true
		}
	}
	return false
}

func (local *localRuntime) hideControlCharacters(
	terminal *os.File,
	interactive bool,
) func() {
	if !interactive || terminal == nil {
		return func() {}
	}
	stty := filepath.Join(local.systemBinPath, executableFile("stty"))
	if !isExecutable(stty) {
		return func() {}
	}
	stateCommand := exec.Command(stty, "-g")
	stateCommand.Stdin = terminal
	state, err := stateCommand.Output()
	if err != nil {
		return func() {}
	}
	hideCommand := exec.Command(stty, "-echoctl")
	hideCommand.Stdin = terminal
	if hideCommand.Run() != nil {
		return func() {}
	}
	return func() {
		restore := exec.Command(stty, strings.TrimSpace(string(state)))
		restore.Stdin = terminal
		_ = restore.Run()
	}
}

func clearTerminalLine(terminal *os.File) {
	if terminal != nil {
		_, _ = terminal.WriteString("\r\x1b[2K")
	}
}

func (cli *localCLI) targetLabelWithReferences(
	translated translatedArguments,
	label string,
) string {
	arguments := []string{"__reference-context"}
	arguments = append(arguments, translated.makeArgs...)
	arguments = append(arguments, "PARAMS="+translated.params)
	context, err := cli.runMakeCapture(translated.projectRoot, arguments...)
	if err != nil {
		return label
	}
	values := make(map[string]string)
	for _, line := range strings.Split(context, "\n") {
		name, value, found := strings.Cut(line, "=")
		if found {
			values[name] = value
		}
	}
	references := normalizeReferences(values["REFERENCES"])
	defaults := normalizeReferences(values["REFERENCES_DEFAULT"])
	if references != "" && defaults != "" && references != defaults {
		return label + " (" + strings.Join(strings.Fields(references), ", ") + ")"
	}
	return label
}

func normalizeReferences(value string) string {
	return strings.Join(strings.Fields(strings.ReplaceAll(value, "+", " ")), " ")
}

func (cli *localCLI) targetLabelWithIntermediateStatus(
	translated translatedArguments,
	label string,
	arguments []string,
) string {
	module := strings.Fields(label)
	if len(module) == 0 || !containsString([]string{
		"max-nodes-soft", "max-consts-soft", "max-nodes-relaxed",
		"max-nodes-seed", "max-nodes-lock",
	}, module[0]) {
		return label
	}
	makeArguments := []string{
		"-s", "__intermediate-gene-selection-status",
		"PARAMS=" + translated.params,
		"INTERMEDIATE_GENE_SELECTION_MODULE=" + module[0],
	}
	makeArguments = append(makeArguments, makeAssignments(arguments)...)
	output, err := cli.runMakeCapture(translated.projectRoot, makeArguments...)
	if err == nil {
		if status := firstNonemptyLine(output); status != "" {
			return label + " (" + status + ")"
		}
	}
	return label
}

func (cli *localCLI) finalizeInterruptedResults(
	translated translatedArguments,
	module string,
	elapsed string,
	arguments []string,
) {
	makeArguments := []string{
		"-s", "__finalize-interrupted-gene-selection-results",
		"PARAMS=" + translated.params,
		"INTERRUPTED_TARGET=" + module,
		"INTERRUPTED_ELAPSED=" + elapsed,
	}
	makeArguments = append(makeArguments, makeAssignments(arguments)...)
	_, _ = cli.runMakeCapture(translated.projectRoot, makeArguments...)
}

func (cli *localCLI) printKeptIntermediateResults(
	translated translatedArguments,
	module string,
	label string,
	arguments []string,
) {
	if module == "" {
		return
	}
	makeArguments := []string{
		"-s", "__kept-gene-selection-results",
		"PARAMS=" + translated.params,
		"INTERRUPTED_INFERENCE_MODULE=" + module,
	}
	makeArguments = append(makeArguments, makeAssignments(arguments)...)
	output, err := cli.runMakeCapture(translated.projectRoot, makeArguments...)
	if err != nil {
		return
	}
	for _, line := range strings.Split(output, "\n") {
		parts := strings.SplitN(strings.TrimSpace(line), " ", 2)
		if len(parts) != 2 {
			continue
		}
		coverage := strings.TrimSuffix(
			strings.TrimPrefix(parts[1], "partial ("),
			")",
		)
		resultLabel := "kept partial solution"
		if parts[0] != label {
			resultLabel += " (" + parts[0] + ")"
		}
		printSuccess(resultLabel + ": " + coverage)
	}
}

func makeAssignments(arguments []string) []string {
	assignments := make([]string, 0)
	for _, argument := range arguments {
		if strings.Contains(argument, "=") {
			assignments = append(assignments, argument)
		}
	}
	return assignments
}

func lastInferenceModule(output string) string {
	matches := inferenceRulePattern.FindAllStringSubmatch(output, -1)
	if len(matches) == 0 {
		return ""
	}
	return matches[len(matches)-1][1]
}

func formatElapsedDuration(duration time.Duration) string {
	seconds := int64(duration.Round(time.Second) / time.Second)
	if seconds < 1 {
		seconds = 1
	}
	days := seconds / 86400
	seconds %= 86400
	hours := seconds / 3600
	seconds %= 3600
	minutes := seconds / 60
	seconds %= 60
	switch {
	case days > 0 && seconds > 0:
		return fmt.Sprintf("%dd%02dh%02dm%02ds", days, hours, minutes, seconds)
	case days > 0 && minutes > 0:
		return fmt.Sprintf("%dd%02dh%02dm", days, hours, minutes)
	case days > 0 && hours > 0:
		return fmt.Sprintf("%dd%02dh", days, hours)
	case days > 0:
		return fmt.Sprintf("%dd", days)
	case hours > 0 && seconds > 0:
		return fmt.Sprintf("%dh%02dm%02ds", hours, minutes, seconds)
	case hours > 0 && minutes > 0:
		return fmt.Sprintf("%dh%02dm", hours, minutes)
	case hours > 0:
		return fmt.Sprintf("%dh", hours)
	case minutes > 0 && seconds > 0:
		return fmt.Sprintf("%dm%02ds", minutes, seconds)
	case minutes > 0:
		return fmt.Sprintf("%dm", minutes)
	default:
		return fmt.Sprintf("%ds", seconds)
	}
}

func hasHelpRequest(arguments []string) bool {
	for _, argument := range arguments {
		if isHelpToken(argument) || argument == "HELP=true" {
			return true
		}
	}
	return false
}

func isHelpToken(argument string) bool {
	return argument == "help" || argument == "-h" || argument == "--help"
}

func dropHelpArguments(arguments []string) []string {
	filtered := make([]string, 0, len(arguments))
	for _, argument := range arguments {
		if !isHelpToken(argument) && argument != "HELP=true" {
			filtered = append(filtered, argument)
		}
	}
	return filtered
}

func hasAssignment(arguments []string, name string) bool {
	prefix := name + "="
	for _, argument := range arguments {
		if strings.HasPrefix(argument, prefix) && strings.TrimPrefix(argument, prefix) != "" {
			return true
		}
	}
	return false
}

func unsupportedOptionError(command string, option string) error {
	choices := []string{
		"--params", "--references", "--reset-target", "--trust-target",
		"--trust-existing", "--old-file", "--logging", "--target", "--backend",
	}
	switch command {
	case "init":
		choices = append(choices, "--remove", "--show", "--help")
	case "clean":
		choices = append(choices, "--all", "--stale", "--force", "--help")
	case "progress":
		choices = append(choices, "--all", "--help")
	case "config":
		choices = append(choices, "--default", "--raw", "--help")
	default:
		choices = append(choices, "--help")
	}
	message := "Unsupported scbolt option: " + option
	if suggestion := closestChoice(option, choices); suggestion != "" {
		if command != "" && command != "global" {
			message += fmt.Sprintf("; did you mean: scbolt %s %s", command, suggestion)
		} else {
			message += "; did you mean: scbolt " + suggestion
		}
	}
	return errors.New(message)
}

func closestChoice(value string, choices []string) string {
	for _, choice := range choices {
		if strings.HasPrefix(choice, value) {
			return choice
		}
	}
	best := ""
	bestDistance := int(^uint(0) >> 1)
	for _, choice := range choices {
		distance := levenshtein(value, choice)
		if distance < bestDistance {
			best = choice
			bestDistance = distance
		}
	}
	maximum := 2
	if len(value) >= 8 {
		maximum = 3
	}
	if bestDistance <= maximum {
		return best
	}
	return ""
}

func levenshtein(left string, right string) int {
	previous := make([]int, len(right)+1)
	for index := range previous {
		previous[index] = index
	}
	for leftIndex, leftRune := range left {
		current := make([]int, len(right)+1)
		current[0] = leftIndex + 1
		for rightIndex, rightRune := range right {
			cost := 1
			if leftRune == rightRune {
				cost = 0
			}
			current[rightIndex+1] = minimum(
				previous[rightIndex+1]+1,
				current[rightIndex]+1,
				previous[rightIndex]+cost,
			)
		}
		previous = current
	}
	return previous[len(right)]
}

func minimum(values ...int) int {
	minimumValue := values[0]
	for _, value := range values[1:] {
		if value < minimumValue {
			minimumValue = value
		}
	}
	return minimumValue
}

func containsString(values []string, query string) bool {
	for _, value := range values {
		if value == query {
			return true
		}
	}
	return false
}

func firstNonemptyLine(value string) string {
	for _, line := range strings.Split(value, "\n") {
		if line = strings.TrimSpace(line); line != "" {
			return line
		}
	}
	return ""
}

func printSuccess(message string) {
	fmt.Printf("%s %s\n", statusIcon(os.Stdout, "✓", "\x1b[0;32m"), message)
}

func printWarning(message string) {
	printWarningTo(os.Stdout, message)
}

func printWarningTo(file *os.File, message string) {
	fmt.Fprintf(file, "%s %s\n", statusIcon(file, "⚠", "\x1b[0;33m"), message)
}

func printFailure(message string) {
	fmt.Fprintf(os.Stderr, "%s %s\n", statusIcon(os.Stderr, "✗", "\x1b[0;31m"), message)
}

func printSuccessStatus(label string) {
	fmt.Printf("%s completed: %s\n", statusIcon(os.Stdout, "✓", "\x1b[0;32m"), label)
}

func printWarningStatus(status string, label string) {
	fmt.Printf("%s %s: %s\n", statusIcon(os.Stdout, "⚠", "\x1b[0;33m"), status, label)
}

func printFailureStatus(label string) {
	fmt.Fprintf(os.Stderr, "%s failed: %s\n", statusIcon(os.Stderr, "✗", "\x1b[0;31m"), label)
}

func statusIcon(file *os.File, icon string, color string) string {
	return terminalColor(file, color) + icon + terminalReset(file)
}

func terminalColor(file *os.File, color string) string {
	if isTerminal(file) {
		return color
	}
	return ""
}

func terminalReset(file *os.File) string {
	if isTerminal(file) {
		return "\x1b[0m"
	}
	return ""
}

func isVersionInvocation(arguments []string) bool {
	return len(arguments) == 1 && (arguments[0] == "version" || arguments[0] == "--version")
}

func printLauncherVersion() {
	version := launcherVersion
	revision := sourceRevision
	if root, err := scboltRoot(); err == nil {
		if version == "dev" || version == "" {
			if data, readErr := os.ReadFile(filepath.Join(root, "VERSION")); readErr == nil {
				version = strings.TrimSpace(string(data))
			}
		}
		if revision == "unknown" || revision == "" {
			command := exec.Command("git", "-C", root, "rev-parse", "HEAD")
			if output, commandErr := command.Output(); commandErr == nil {
				revision = strings.TrimSpace(string(output))
			}
		}
	}
	if version == "" {
		version = "unknown"
	}
	if revision == "" {
		revision = "unknown"
	}
	fmt.Printf("scBOLT %s\n", version)
	fmt.Printf("Source revision: %s\n", revision)
}
