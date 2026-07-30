package main

import (
	"context"
	"os"
	"runtime"
	"strconv"
	"strings"
)

type HostInfo struct {
	OperatingSystem      string
	Architecture         string
	Processor            string
	Microarchitecture    string
	ProcessorFeatures    map[string]bool
	DetectionDescription string
	VendorID             string
	CPUFamily            int
	CPUModel             int
	CPUFamilyDetected    bool
	CPUModelDetected     bool
}

const validatedReferenceMicroarchitecture = "Meteor Lake"

func (host HostInfo) HaswellCompatible() bool {
	architecture := normalizeArchitecture(host.Architecture)
	return architecture == "amd64" &&
		host.ProcessorFeatures["avx2"] &&
		host.ProcessorFeatures["fma"]
}

type nativeHostDetector struct{}

func (nativeHostDetector) Detect(
	ctx context.Context,
	runner CommandRunner,
) HostInfo {
	host := HostInfo{
		OperatingSystem:   runtime.GOOS,
		Architecture:      runtime.GOARCH,
		ProcessorFeatures: make(map[string]bool),
	}
	switch runtime.GOOS {
	case "linux":
		detectLinuxHost(&host)
	case "darwin":
		detectDarwinHost(ctx, runner, &host)
	case "windows":
		host.Processor = strings.TrimSpace(os.Getenv("PROCESSOR_IDENTIFIER"))
		host.DetectionDescription = "Windows processor environment"
	}
	host.Microarchitecture = inferMicroarchitecture(host)
	return host
}

func detectLinuxHost(host *HostInfo) {
	data, err := os.ReadFile("/proc/cpuinfo")
	if err != nil {
		return
	}
	populateLinuxHost(host, string(data))
	host.DetectionDescription = "/proc/cpuinfo"
}

func populateLinuxHost(host *HostInfo, cpuInfo string) {
	for _, raw := range strings.Split(cpuInfo, "\n") {
		name, value, found := strings.Cut(raw, ":")
		if !found {
			continue
		}
		name = strings.TrimSpace(name)
		value = strings.TrimSpace(value)
		switch name {
		case "vendor_id":
			if host.VendorID == "" {
				host.VendorID = value
			}
		case "cpu family":
			if !host.CPUFamilyDetected {
				if family, parseErr := strconv.Atoi(value); parseErr == nil {
					host.CPUFamily = family
					host.CPUFamilyDetected = true
				}
			}
		case "model":
			if !host.CPUModelDetected {
				if model, parseErr := strconv.Atoi(value); parseErr == nil {
					host.CPUModel = model
					host.CPUModelDetected = true
				}
			}
		case "model name", "Hardware", "Processor":
			if host.Processor == "" && value != "" && !isNumeric(value) {
				host.Processor = value
			}
		case "flags", "Features":
			if len(host.ProcessorFeatures) == 0 {
				for _, feature := range strings.Fields(strings.ToLower(value)) {
					host.ProcessorFeatures[feature] = true
				}
			}
		}
	}
}

func detectDarwinHost(
	ctx context.Context,
	runner CommandRunner,
	host *HostInfo,
) {
	if output, err := runner.Run(ctx, "sysctl", "-n", "machdep.cpu.brand_string"); err == nil {
		host.Processor = strings.TrimSpace(string(output))
	}
	if host.Processor == "" {
		if output, err := runner.Run(ctx, "sysctl", "-n", "hw.model"); err == nil {
			host.Processor = strings.TrimSpace(string(output))
		}
	}
	for _, key := range []string{"machdep.cpu.features", "machdep.cpu.leaf7_features"} {
		output, err := runner.Run(ctx, "sysctl", "-n", key)
		if err != nil {
			continue
		}
		for _, feature := range strings.Fields(strings.ToLower(string(output))) {
			host.ProcessorFeatures[strings.TrimSuffix(feature, ".0")] = true
		}
	}
	host.DetectionDescription = "sysctl"
}

func inferMicroarchitecture(host HostInfo) string {
	model := strings.ToLower(host.Processor)
	switch {
	case strings.Contains(model, "znver3") ||
		strings.Contains(model, "zen 3") ||
		strings.Contains(model, "zen3"):
		return "AMD Zen 3"
	case isAMDZen3(host):
		return "AMD Zen 3"
	case strings.Contains(model, "meteor lake"):
		return "Meteor Lake"
	case strings.Contains(model, "ultra") &&
		(strings.Contains(model, " 125") ||
			strings.Contains(model, " 135") ||
			strings.Contains(model, " 155") ||
			strings.Contains(model, " 165") ||
			strings.Contains(model, " 185")):
		return "Meteor Lake"
	case strings.Contains(model, "emerald rapids"):
		return "Emerald Rapids"
	case strings.Contains(model, "haswell"):
		return "Haswell"
	case strings.Contains(model, "apple m"):
		return "Apple Silicon"
	default:
		return ""
	}
}

func isAMDZen3(host HostInfo) bool {
	if !strings.EqualFold(host.VendorID, "AuthenticAMD") ||
		!host.CPUFamilyDetected || !host.CPUModelDetected ||
		host.CPUFamily != 25 {
		return false
	}
	model := host.CPUModel
	return model <= 0x0f ||
		(model >= 0x20 && model <= 0x2f) ||
		(model >= 0x30 && model <= 0x3f) ||
		(model >= 0x40 && model <= 0x4f) ||
		(model >= 0x50 && model <= 0x5f)
}

func microarchitectureQualification(microarchitecture string) (bool, string) {
	switch microarchitecture {
	case validatedReferenceMicroarchitecture:
		return true, "Canonical reference processor profile."
	case "AMD Zen 3":
		return true, "Strict numerical profile validated against the canonical references."
	default:
		return false, ""
	}
}

func numericalArchitectureContract(
	host HostInfo,
) (string, DiagnosticStatus, string) {
	switch host.Microarchitecture {
	case validatedReferenceMicroarchitecture:
		return "strict validated (canonical)", DiagnosticOK,
			"Canonical bonesistools golden reference architecture."
	case "AMD Zen 3":
		return "strict validated", DiagnosticOK,
			"The bonesistools strict golden contract is validated on AMD Zen 3."
	case "Emerald Rapids":
		return "portable", DiagnosticWarning,
			"Strict numerical divergences are documented; bonesistools uses its portable contract."
	}

	switch strings.ToLower(host.OperatingSystem) {
	case "darwin", "windows":
		return "portable", DiagnosticWarning,
			"bonesistools uses its portable golden contract on macOS and Windows."
	default:
		return "not yet qualified", DiagnosticWarning,
			"This numerical architecture has not yet received a strict compatibility qualification."
	}
}

func collectHostDiagnostics(collection *diagnosticCollection) {
	host := collection.host
	collection.report.Add(Diagnostic{
		Section: "Host",
		Name:    "operating system",
		Value:   displayOperatingSystem(host.OperatingSystem),
		Status:  DiagnosticOK,
	})
	collection.report.Add(Diagnostic{
		Section: "Host",
		Name:    "architecture",
		Value:   normalizeArchitecture(host.Architecture),
		Status:  DiagnosticOK,
	})
	if host.Processor == "" {
		collection.report.Add(Diagnostic{
			Section: "Host",
			Name:    "processor",
			Value:   "unknown",
			Status:  DiagnosticWarning,
			Detail:  "The exact processor model could not be detected.",
		})
	} else {
		collection.report.Add(Diagnostic{
			Section: "Host",
			Name:    "processor",
			Value:   host.Processor,
			Status:  DiagnosticOK,
		})
	}
	if host.Microarchitecture == "" {
		collection.report.Add(Diagnostic{
			Section: "Host",
			Name:    "CPU microarchitecture",
			Value:   "unknown",
			Status:  DiagnosticWarning,
			Detail: "Exact microarchitecture detection is optional; exact numerical " +
				"identity cannot be inferred from this host report.",
		})
	} else {
		validated, detail := microarchitectureQualification(host.Microarchitecture)
		status := DiagnosticOK
		if !validated {
			status = DiagnosticWarning
			detail = host.Microarchitecture +
				" differs from the validated Meteor Lake and AMD Zen 3 " +
				"processor profiles. " +
				"This does not imply different scientific conclusions."
		}
		collection.report.Add(Diagnostic{
			Section: "Host",
			Name:    "CPU microarchitecture",
			Value:   host.Microarchitecture,
			Status:  status,
			Detail:  detail,
		})
	}

	if host.HaswellCompatible() {
		collection.report.Add(Diagnostic{
			Section: "Host",
			Name:    "OpenBLAS Haswell profile",
			Value:   "compatible",
			Status:  DiagnosticOK,
			Detail:  "Required AVX2 and FMA processor features were detected.",
		})
	} else {
		collection.report.Add(Diagnostic{
			Section: "Host",
			Name:    "OpenBLAS Haswell profile",
			Value:   "compatibility not detected",
			Status:  DiagnosticWarning,
			Detail: "The Haswell OpenBLAS profile requires an amd64 processor with " +
				"AVX2 and FMA support.",
		})
	}
}

func normalizeArchitecture(architecture string) string {
	switch strings.ToLower(strings.TrimSpace(architecture)) {
	case "x86_64", "x86-64", "amd64":
		return "amd64"
	case "aarch64", "arm64":
		return "arm64"
	default:
		return strings.ToLower(strings.TrimSpace(architecture))
	}
}

func displayOperatingSystem(operatingSystem string) string {
	switch strings.ToLower(operatingSystem) {
	case "linux":
		return "Linux"
	case "darwin":
		return "macOS"
	case "windows":
		return "Windows"
	default:
		return operatingSystem
	}
}

func isNumeric(value string) bool {
	if value == "" {
		return false
	}
	for _, character := range value {
		if character < '0' || character > '9' {
			return false
		}
	}
	return true
}
