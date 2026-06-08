#!/usr/bin/env python

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import argparse
import json
import re
import subprocess
import sys

script_name = Path(__file__).name


@dataclass(frozen=True)
class PackageSpec:
    name: str
    version: str | None = None
    build: str | None = None
    source: str = "conda"


def normalize_name(name: str) -> str:
    return name.strip().lower()


def normalize_pip_name(name: str) -> str:
    return normalize_name(name).replace("_", "-")


def parse_conda_spec(spec: str) -> PackageSpec | None:
    if not spec or spec.startswith("#"):
        return None
    parts = spec.split("=")
    name = parts[0].strip()
    if not name:
        return None
    return PackageSpec(
        name=normalize_name(name),
        version=parts[1].strip() or None if len(parts) > 1 else None,
        build=parts[2].strip() or None if len(parts) > 2 else None,
        source="conda",
    )


def parse_pip_spec(spec: str) -> PackageSpec | None:
    if not spec or spec.startswith("#"):
        return None
    match = re.match(r"^([A-Za-z0-9_.-]+)==([^ ;]+)", spec)
    if not match:
        return PackageSpec(name=normalize_pip_name(spec), source="pip")
    return PackageSpec(
        name=normalize_pip_name(match.group(1)),
        version=match.group(2),
        source="pip",
    )


def read_environment_yaml(path: Path) -> tuple[str | None, list[PackageSpec]]:
    name = None
    specs = []
    in_dependencies = False
    in_pip = False

    for raw_line in path.read_text().splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("name:"):
            name = stripped.split(":", 1)[1].strip()
            continue
        if stripped == "dependencies:":
            in_dependencies = True
            in_pip = False
            continue
        if not in_dependencies:
            continue
        if line.startswith("  - "):
            value = line[4:].strip()
            in_pip = value == "pip:"
            if not in_pip and (spec := parse_conda_spec(value)) is not None:
                specs.append(spec)
            continue
        if in_pip and line.startswith("      - "):
            if spec := parse_pip_spec(line[8:].strip()):
                specs.append(spec)

    return name, specs


def run_json(command: list[str]) -> object:
    output = subprocess.check_output(command, text=True)
    return json.loads(output)


def installed_packages(env: str) -> dict[str, PackageSpec]:
    data = run_json(["conda", "list", "-n", env, "--json"])
    packages = {}
    for item in data:
        source = (
            "pip"
            if item.get("channel") == "pypi" or item.get("platform") == "pypi"
            else "conda"
        )
        name = (
            normalize_pip_name(item["name"])
            if source == "pip"
            else normalize_name(item["name"])
        )
        packages[name] = PackageSpec(
            name=name,
            version=item.get("version"),
            build=item.get("build_string"),
            source=source,
        )
    return packages


def lookup_package(
    packages: dict[str, PackageSpec], spec: PackageSpec
) -> PackageSpec | None:
    if spec.source == "pip":
        return packages.get(normalize_pip_name(spec.name))
    return packages.get(spec.name)


def compare_specs(
    expected: list[PackageSpec], installed: dict[str, PackageSpec]
) -> list[str]:
    warnings = []
    for spec in expected:
        package = lookup_package(installed, spec)
        if package is None:
            warnings.append(f"{spec.name}: missing")
            continue
        if spec.version and package.version != spec.version:
            warnings.append(f"{spec.name}: {package.version}->{spec.version}")
            continue
        if spec.build and package.source == "conda" and package.build != spec.build:
            warnings.append(f"{spec.name} build: {package.build}->{spec.build}")
    return warnings


def direct_url_commit(env: str, package: str) -> str | None:
    code = (
        "from importlib import metadata; import json, sys; "
        "dist = metadata.distribution(sys.argv[1]); "
        "text = dist.read_text('direct_url.json'); "
        "print(json.loads(text).get('vcs_info', {}).get('commit_id', '') if text else '')"
    )
    output = subprocess.check_output(
        [
            "conda",
            "run",
            "--no-capture-output",
            "-n",
            env,
            "python",
            "-c",
            code,
            package,
        ],
        text=True,
    )
    return output.strip() or None


def check_git_packages(env: str, specs: list[str]) -> tuple[list[str], list[str]]:
    successes, warnings = [], []
    for spec in specs:
        package, expected = spec.split("=", 1)
        try:
            commit = direct_url_commit(env, package)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            warnings.append(f"git package commit not verifiable: {package} (env={env})")
            continue
        if commit == expected:
            successes.append(
                f"conda environment git package valid: {package}={expected} (env={env})"
            )
        elif commit:
            warnings.append(
                f"conda environment git package differs: {package}={commit} "
                f"(expected: {expected}, env={env})"
            )
        else:
            warnings.append(
                f"conda environment git package has no recorded commit: {package} (env={env})"
            )
    return successes, warnings


def emit(status: str, messages: list[str]) -> None:
    for message in messages:
        print(f"{status}\t{message}")


def main() -> int:
    parser = argparse.ArgumentParser(prog=script_name)
    parser.add_argument("--env", required=True)
    parser.add_argument("--yaml", type=Path, required=True)
    parser.add_argument("--git-package", action="append", default=[])
    args = parser.parse_args()

    if not args.yaml.is_file():
        emit(
            "warning",
            [f"conda environment yaml not found: {args.yaml} (env={args.env})"],
        )
        return 0

    name, expected = read_environment_yaml(args.yaml)
    if name != args.env:
        emit(
            "warning",
            [f"conda environment name differs from yaml: {args.env} != {name}"],
        )

    try:
        installed = installed_packages(args.env)
    except subprocess.CalledProcessError as error:
        emit(
            "failure", [f"conda environment cannot be inspected: {args.env} ({error})"]
        )
        return 1

    warnings = compare_specs(expected, installed)
    if warnings:
        details = "; ".join(warnings[:5])
        extra = f"; +{len(warnings) - 5} more" if len(warnings) > 5 else ""
        emit("warning", [f"conda environment mismatch: {args.env} ({details}{extra})"])
    else:
        emit("success", [f"conda environment matches yaml: {args.env}"])

    successes, git_warnings = check_git_packages(args.env, args.git_package)
    emit("success", successes)
    emit("warning", git_warnings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
