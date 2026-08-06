
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from scbolt import cli

script_name = Path(__file__).name


@dataclass(frozen=True)
class PackageSpec:
    name: str
    version: str | None = None
    build: str | None = None
    source: str = "conda"


@dataclass(frozen=True)
class InstalledEnvironment:
    packages: dict[str, PackageSpec]
    distributions: dict[str, metadata.Distribution]


def normalize_name(name: str) -> str:
    return name.strip().lower()


def normalize_pip_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", normalize_name(name))


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
        if (
            in_pip
            and line.startswith("      - ")
            and (spec := parse_pip_spec(line[8:].strip()))
        ):
            specs.append(spec)

    return name, specs


def site_package_paths(prefix: Path) -> list[Path]:
    candidates = [
        *sorted(prefix.glob("lib/python*/site-packages")),
        prefix / "lib" / "site-packages",
        prefix / "Lib" / "site-packages",
    ]
    return [path for path in candidates if path.is_dir()]


def installed_environment(prefix: Path) -> InstalledEnvironment:
    conda_meta = prefix / "conda-meta"
    if not conda_meta.is_dir():
        raise FileNotFoundError(f"conda metadata not found: {conda_meta}")

    packages = {}
    for record_path in sorted(conda_meta.glob("*.json")):
        item = json.loads(record_path.read_text())
        name = normalize_name(item["name"])
        packages[name] = PackageSpec(
            name=name,
            version=item.get("version"),
            build=item.get("build") or item.get("build_string"),
            source="conda",
        )

    distributions = {}
    paths = site_package_paths(prefix)
    for distribution in metadata.distributions(path=[str(path) for path in paths]):
        distribution_name = distribution.metadata.get("Name")
        if not distribution_name:
            continue
        name = normalize_pip_name(distribution_name)
        distributions[name] = distribution
        if name not in packages:
            packages[name] = PackageSpec(
                name=name,
                version=distribution.version,
                source="pip",
            )
    return InstalledEnvironment(packages, distributions)


def lookup_package(
    packages: dict[str, PackageSpec], spec: PackageSpec
) -> PackageSpec | None:
    if spec.source == "pip":
        return packages.get(normalize_pip_name(spec.name))
    return packages.get(spec.name)


def matches_version_constraint(actual: str | None, expected: str) -> bool:
    if actual is None:
        return False
    if any(character in expected for character in "*?["):
        return fnmatch.fnmatchcase(actual, expected)
    return actual == expected or actual.startswith(f"{expected}.")


def matches_build_constraint(actual: str | None, expected: str) -> bool:
    return actual is not None and fnmatch.fnmatchcase(actual, expected)


def compare_specs(
    expected: list[PackageSpec], installed: dict[str, PackageSpec]
) -> list[str]:
    warnings = []
    for spec in expected:
        package = lookup_package(installed, spec)
        if package is None:
            warnings.append(f"{spec.name}: missing")
            continue
        if spec.version and not matches_version_constraint(
            package.version, spec.version
        ):
            warnings.append(f"{spec.name}: {package.version}->{spec.version}")
            continue
        if (
            spec.build
            and package.source == "conda"
            and not matches_build_constraint(package.build, spec.build)
        ):
            warnings.append(f"{spec.name} build: {package.build}->{spec.build}")
    return warnings


def direct_url_commit(
    distributions: dict[str, metadata.Distribution], package: str
) -> str | None:
    distribution = distributions.get(normalize_pip_name(package))
    if distribution is None:
        return None
    text = distribution.read_text("direct_url.json")
    if not text:
        return None
    direct_url = json.loads(text)
    return direct_url.get("vcs_info", {}).get("commit_id")


def check_git_packages(
    env: str,
    specs: list[str],
    distributions: dict[str, metadata.Distribution],
) -> tuple[list[str], list[str]]:
    successes, warnings = [], []
    for spec in specs:
        package, expected = spec.split("=", 1)
        try:
            commit = direct_url_commit(distributions, package)
        except (OSError, json.JSONDecodeError):
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
    parser = argparse.ArgumentParser(
        prog=script_name,
        formatter_class=cli.HelpFormatter,
    )
    parser.add_argument("--env", required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--yaml", type=Path, required=True)
    parser.add_argument("--git-package", action="append", default=[])
    args = parser.parse_args()

    if not args.yaml.is_file():
        emit(
            "warning",
            [f"{args.env} environment: unverifiable (yaml not found: {args.yaml})"],
        )
        return 0

    name, expected = read_environment_yaml(args.yaml)
    if name != args.env:
        emit(
            "warning",
            [f"{args.env} environment: name differs from yaml ({name})"],
        )

    try:
        installed = installed_environment(args.prefix)
    except (OSError, json.JSONDecodeError, KeyError) as error:
        emit(
            "failure", [f"{args.env} environment: invalid ({error})"]
        )
        return 1

    warnings = compare_specs(expected, installed.packages)
    if warnings:
        details = "; ".join(warnings[:5])
        extra = f"; +{len(warnings) - 5} more" if len(warnings) > 5 else ""
        emit("warning", [f"{args.env} environment: drifted ({details}{extra})"])
    else:
        emit("success", [f"{args.env} environment: ready"])

    successes, git_warnings = check_git_packages(
        args.env,
        args.git_package,
        installed.distributions,
    )
    emit("success", successes)
    emit("warning", git_warnings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
