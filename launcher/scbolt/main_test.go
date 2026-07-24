package main

import (
	"reflect"
	"testing"
)

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
