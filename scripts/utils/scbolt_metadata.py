#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from scbolt import cli
from scbolt.runtime import format_duration

Status = Literal["done", "stale", "pending", "untracked"]
State = tuple[Status, str, list[Path], list[Path]]
ProgressRecord = dict[str, str | list[str]]
RuntimeEnvironments = dict[str, dict[str, object]]
RuntimeBackend = Literal["conda", "mamba", "micromamba", "docker"]
SolutionStatus = Literal["global", "partial", "failed"]
MAX_DISPLAYED_LABELS = 8


def sidecar_path(target: Path) -> Path:
    if target.exists() and target.is_dir():
        return target / ".scbolt.json"
    return target.with_suffix(".scbolt.json")


def normalize_value(value: str) -> str:
    return value.strip()


def parse_parameter(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"invalid parameter assignment: {value}")
    name, raw_value = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError(f"invalid parameter assignment: {value}")
    return name, normalize_value(raw_value)


def parse_parameters(values: list[str]) -> dict[str, str]:
    return dict(parse_parameter(value) for value in values)


def add_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--backend",
        dest="runtime_backend",
        choices=["conda", "mamba", "micromamba", "docker"],
        default="conda",
    )
    parser.add_argument("--container-engine", default="docker")
    parser.add_argument("--container-image", default="")


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve()


def digest(data: object) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def config_hash(parameters: dict[str, str]) -> str:
    return digest(parameters)


def runtime_hash(runtime_environments: RuntimeEnvironments) -> str:
    return digest(runtime_environments)


def metadata_hash(
    parameters: dict[str, str],
    runtime_backend: RuntimeBackend,
    container: dict[str, object],
    runtime_environments: RuntimeEnvironments,
) -> str:
    return digest(
        {
            "sensitive_parameters": parameters,
            "runtime_backend": runtime_backend,
            "container": container,
            "runtime_environments": runtime_environments,
        }
    )


def conda_package_source(package: dict[str, object]) -> str:
    channel = str(package.get("channel", ""))
    platform = str(package.get("platform", ""))
    if channel == "pypi" or platform == "pypi":
        return "pip"
    return "conda"


def normalize_package_name(name: str, source: str) -> str:
    normalized = name.strip().lower()
    if source == "pip":
        normalized = re.sub(r"[-_.]+", "-", normalized)
    return normalized


def conda_base_from_executable(executable: str) -> Path | None:
    path = Path(executable).expanduser()
    if path.name != "conda" or path.parent.name not in {"bin", "condabin"}:
        return None
    return path.parent.parent


def local_conda_env_prefix(env: str) -> Path | None:
    executable = os.environ.get("CONDA_EXE")
    if not executable:
        return None

    base = conda_base_from_executable(executable)
    if base is None:
        return None

    candidates = [base / "envs" / env]
    if base.name == env:
        candidates.append(base)

    for candidate in candidates:
        if (candidate / "conda-meta").is_dir():
            return candidate
    return None


def conda_channel_label(channel: str) -> str:
    if not channel:
        return ""

    parsed = urlparse(channel)
    if parsed.netloc == "conda.anaconda.org":
        parts = [part for part in parsed.path.split("/") if part]
        return parts[0] if parts else ""

    if parsed.netloc == "repo.anaconda.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "pkgs":
            return f"{parts[0]}/{parts[1]}"

    parts = [part for part in channel.rstrip("/").split("/") if part]
    if parts and parts[-1] in {"linux-64", "noarch", "osx-64", "osx-arm64", "win-64"}:
        parts.pop()
    return parts[-1] if parts else channel


def site_packages_dirs(prefix: Path) -> list[Path]:
    candidates = list((prefix / "lib").glob("python*/site-packages"))
    candidates.append(prefix / "Lib" / "site-packages")
    paths = []
    seen = set()
    for path in candidates:
        if not path.is_dir():
            continue
        try:
            real_path = path.resolve()
        except OSError:
            real_path = path
        if real_path in seen:
            continue
        seen.add(real_path)
        paths.append(path)
    return paths


def dist_info_metadata(path: Path) -> tuple[str, str] | None:
    name = ""
    version = ""
    try:
        with path.open(errors="replace") as file:
            for line in file:
                if not line.strip():
                    break
                key, separator, value = line.partition(":")
                if not separator:
                    continue
                if key == "Name":
                    name = value.strip()
                elif key == "Version":
                    version = value.strip()
                if name and version:
                    return name, version
    except OSError:
        return None
    return None


def dist_info_installer(path: Path) -> str:
    try:
        return (path.parent / "INSTALLER").read_text().strip().lower()
    except OSError:
        return ""


def local_conda_runtime_environment(env: str) -> dict[str, object] | None:
    prefix = local_conda_env_prefix(env)
    if prefix is None:
        return None

    packages: dict[str, dict[str, str]] = {}
    conda_name_by_pip_name: dict[str, str] = {}

    for path in sorted((prefix / "conda-meta").glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

        raw_name = data.get("name")
        if not raw_name:
            continue

        name = normalize_package_name(str(raw_name), "conda")
        conda_name_by_pip_name[normalize_package_name(str(raw_name), "pip")] = name

        record = {
            "version": str(data.get("version", "")),
            "source": "conda",
        }
        build = data.get("build") or data.get("build_string")
        if build:
            record["build"] = str(build)

        channel = conda_channel_label(str(data.get("channel", "")))
        if channel:
            record["channel"] = channel

        packages[name] = record

    for site_packages in site_packages_dirs(prefix):
        for metadata in sorted(site_packages.glob("*.dist-info/METADATA")):
            installer = dist_info_installer(metadata)
            if installer != "pip":
                continue

            parsed = dist_info_metadata(metadata)
            if parsed is None:
                continue

            raw_name, version = parsed
            name = normalize_package_name(raw_name, "pip")
            conda_name = conda_name_by_pip_name.get(name)
            if conda_name is not None:
                packages.pop(conda_name, None)
            elif name in packages:
                continue

            packages[name] = {
                "version": version,
                "source": "pip",
                "channel": "pypi",
            }

    return {
        "name": env,
        "packages": packages,
    }


@lru_cache(maxsize=None)
def container_metadata(
    backend: RuntimeBackend,
    container_engine: str,
    container_image: str,
) -> dict[str, object]:
    if backend != "docker":
        return {}

    if os.environ.get("SCBOLT_IN_DOCKER") == "true":
        return {
            "engine": container_engine,
            "image": container_image or os.environ.get("SCBOLT_IMAGE", ""),
            "id": os.environ.get("SCBOLT_IMAGE_ID", ""),
            "repo_digests": os.environ.get("SCBOLT_IMAGE_REPO_DIGESTS", "").split(),
        }

    if not container_image:
        return {
            "engine": container_engine,
            "image": container_image,
            "error": "missing image",
        }

    result = subprocess.run(
        [
            container_engine,
            "image",
            "inspect",
            container_image,
            "--format",
            "{{json .}}",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        return {
            "engine": container_engine,
            "image": container_image,
            "error": message or "container image inspect failed",
        }

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return {
            "engine": container_engine,
            "image": container_image,
            "error": f"cannot parse container image metadata: {error}",
        }

    return {
        "engine": container_engine,
        "image": container_image,
        "id": data.get("Id", ""),
        "repo_digests": data.get("RepoDigests") or [],
    }


@lru_cache(maxsize=None)
def runtime_environment(
    env: str,
    backend: RuntimeBackend,
    container_engine: str,
    container_image: str,
) -> dict[str, object]:
    if backend == "docker":
        if os.environ.get("SCBOLT_IN_DOCKER") == "true":
            command = ["micromamba", "list", "-n", env, "--json"]
        else:
            if not container_image:
                return {
                    "name": env,
                    "error": "missing container image",
                    "packages": {},
                }
            command = [
                container_engine,
                "run",
                "--rm",
                "--entrypoint",
                "micromamba",
                container_image,
                "list",
                "-n",
                env,
                "--json",
            ]
    else:
        local_environment = local_conda_runtime_environment(env)
        if local_environment is not None:
            return local_environment
        command_name = "conda" if backend == "conda" else backend
        command = [command_name, "list", "-n", env, "--json"]

    result = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        return {
            "name": env,
            "error": message or "conda list failed",
            "packages": {},
        }

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return {
            "name": env,
            "error": f"cannot parse conda environment: {error}",
            "packages": {},
        }

    packages: dict[str, dict[str, str]] = {}
    for package in data:
        if not isinstance(package, dict):
            continue
        raw_name = package.get("name")
        if not raw_name:
            continue
        source = conda_package_source(package)
        name = normalize_package_name(str(raw_name), source)
        record = {
            "version": str(package.get("version", "")),
            "source": source,
        }
        build = package.get("build_string")
        if source == "conda" and build:
            record["build"] = str(build)
        channel = package.get("channel")
        if channel:
            record["channel"] = str(channel)
        packages[name] = record

    return {
        "name": env,
        "packages": packages,
    }


def runtime_environments(
    envs: list[str],
    *,
    backend: RuntimeBackend,
    container_engine: str,
    container_image: str,
    strict: bool = False,
) -> RuntimeEnvironments:
    environments = {
        env: runtime_environment(env, backend, container_engine, container_image)
        for env in unique_values(envs)
    }
    if strict:
        errors = [
            f"{env}: {snapshot['error']}"
            for env, snapshot in environments.items()
            if "error" in snapshot
        ]
        if errors:
            raise SystemExit(
                "cannot inspect runtime environment(s): " + "; ".join(errors)
            )
    return environments


def package_label(package: object) -> str:
    if not isinstance(package, dict):
        return "(missing)"
    version = str(package.get("version", ""))
    build = str(package.get("build", ""))
    source = str(package.get("source", ""))
    if build:
        return f"{version} {build}"
    if source == "pip":
        return f"{version} pip"
    return version


def runtime_changes(
    stored: dict[str, object],
    current_backend: RuntimeBackend,
    current_container: dict[str, object],
    current_runtime: RuntimeEnvironments,
) -> list[str]:
    if not current_runtime:
        return []

    stored_backend = stored.get("runtime_backend")
    if stored_backend is not None and stored_backend != current_backend:
        return [f"runtime backend: {stored_backend} -> {current_backend}"]

    if current_backend == "docker":
        stored_container = stored.get("container")
        if not isinstance(stored_container, dict):
            return ["container metadata missing"]
        if current_container != stored_container:
            stored_image = stored_container.get("image", "(missing)")
            current_image = current_container.get("image", "(missing)")
            if stored_image != current_image:
                return [f"container image: {stored_image} -> {current_image}"]
            return [f"container image changed: {current_image}"]

    stored_runtime = stored.get("runtime_environments")
    if not isinstance(stored_runtime, dict):
        return ["runtime metadata missing"]

    messages = []
    for env, current in current_runtime.items():
        stored_env = stored_runtime.get(env)
        if not isinstance(stored_env, dict):
            messages.append(f"runtime drift: {env} (missing stored environment)")
            continue
        if "error" in current:
            messages.append(f"runtime drift: {env} (current environment unavailable)")
            continue

        current_packages = current.get("packages")
        stored_packages = stored_env.get("packages")
        if not isinstance(current_packages, dict) or not isinstance(
            stored_packages, dict
        ):
            messages.append(f"runtime drift: {env} (invalid stored environment)")
            continue

        package_changes = []
        package_names = sorted(set(current_packages) | set(stored_packages))
        for package_name in package_names:
            current_package = current_packages.get(package_name)
            stored_package = stored_packages.get(package_name)
            if current_package == stored_package:
                continue
            package_changes.append(
                f"{package_name}: {package_label(stored_package)} -> "
                f"{package_label(current_package)}"
            )

        if package_changes:
            visible = package_changes[:8]
            if len(package_changes) > len(visible):
                visible.append(f"{len(package_changes) - len(visible)} more package(s)")
            messages.append(f"runtime drift: {env}; {'; '.join(visible)}")

    return messages


def read_metadata(path: Path) -> dict[str, object] | None:
    try:
        with path.open() as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def solution_payload(
    status: SolutionStatus | None,
    kept: int | None,
    total: int | None,
    forwarded_from: str | None,
) -> dict[str, object] | None:
    if status is None:
        if kept is not None or total is not None or forwarded_from is not None:
            raise SystemExit("solution metadata require --solution-status")
        return None

    payload: dict[str, object] = {"status": status}
    if kept is not None:
        payload["kept"] = kept
    if total is not None:
        payload["total"] = total
    if kept is not None and total is not None:
        payload["coverage"] = f"{kept}/{total}"
    if forwarded_from is not None:
        payload["forwarded_from"] = forwarded_from
    return payload


def solution_label(solution: dict[str, object]) -> str:
    status = str(solution.get("status", ""))
    coverage = solution.get("coverage")
    if coverage:
        return f"{status} ({coverage})"

    kept = solution.get("kept")
    total = solution.get("total")
    if kept is not None and total is not None:
        return f"{status} ({kept}/{total})"
    if kept is not None:
        return f"{status} ({kept})"
    return status


def partial_solution_message(solution: dict[str, object]) -> str:
    coverage = solution.get("coverage")
    if coverage:
        return f"partial solution: {coverage}"

    kept = solution.get("kept")
    total = solution.get("total")
    if kept is not None and total is not None:
        return f"partial solution: {kept}/{total}"
    if kept is not None:
        return f"partial solution: {kept}"
    return "partial solution"


def read_solution(target: Path) -> dict[str, object] | None:
    metadata = read_metadata(sidecar_path(target))
    if metadata is None:
        return None

    solution = metadata.get("solution")
    return solution if isinstance(solution, dict) else None


def changed_parameters(
    stored: dict[str, object],
    current: dict[str, str],
) -> list[tuple[str, str, str]]:
    stored_params = stored.get("sensitive_parameters")
    if not isinstance(stored_params, dict):
        return []

    changes = []
    for name, current_value in current.items():
        stored_value = str(stored_params.get(name, ""))
        if stored_value != current_value:
            changes.append((name, stored_value, current_value))
    return changes


def format_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def format_target_label(path: Path) -> str:
    formatted = format_path(path)
    parts = Path(formatted).parts
    if "omics" in parts:
        omics_index = parts.index("omics")
        omics_parts = parts[omics_index + 1 :]
        if len(omics_parts) >= 3:
            if omics_parts[0] in {
                "count",
                "prep",
                "clust",
                "annot",
                "dea",
                "scoring",
                "goea",
            }:
                candidate = omics_parts[1]
                if candidate in {"geo", "filter", "norm"} or Path(candidate).suffix:
                    return ""
                return candidate
            if omics_parts[0] == "trajectories" and len(omics_parts) >= 4:
                return omics_parts[2]
            if omics_parts[0] == "mstates" and len(omics_parts) >= 4:
                return omics_parts[2]
        return ""

    reference_output_dirs = {
        "annot",
        "clust",
        "count",
        "dea",
        "fastq",
        "goea",
        "mstates",
        "prep",
        "scoring",
        "traj",
        "trajectories",
    }

    for index, part in enumerate(parts[:-1]):
        if parts[index + 1] in reference_output_dirs:
            return part
    return formatted


def unique_values(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def format_labels(labels: list[str], all_labels: list[str]) -> str:
    labels = unique_values(labels)
    if not labels or set(labels) == set(all_labels):
        return ""
    if len(labels) > MAX_DISPLAYED_LABELS:
        hidden = len(labels) - MAX_DISPLAYED_LABELS
        labels = labels[:MAX_DISPLAYED_LABELS] + [f"{hidden} more output(s)"]
    return f" ({', '.join(labels)})"


def format_parameter_value(name: str, value: str) -> str:
    if not name.startswith("TIMEOUT_"):
        return value

    match = re.fullmatch(r"([1-9][0-9]*)s", value)
    if not match:
        return value

    seconds = int(match.group(1))
    if seconds < 60:
        return value
    return f"{value} ({format_duration(seconds)})"


def format_change_messages(
    grouped_changes: dict[str, dict[str, dict[str, list[str]]]],
    all_labels: list[str],
) -> list[str]:
    messages = []

    for name, current_groups in grouped_changes.items():
        for current_value, stored_groups in current_groups.items():
            formatted_current_value = format_parameter_value(name, current_value)
            if len(stored_groups) == 1:
                stored_value, labels = next(iter(stored_groups.items()))
                label = format_labels(labels, all_labels)
                formatted_stored_value = format_parameter_value(name, stored_value)
                messages.append(
                    f"{name}: {formatted_stored_value} -> "
                    f"{formatted_current_value}{label}"
                )
                continue

            stored_values = []
            for stored_value, labels in stored_groups.items():
                label = format_labels(labels, all_labels)
                formatted_stored_value = format_parameter_value(name, stored_value)
                stored_values.append(
                    f"{formatted_stored_value} -> {formatted_current_value}{label}"
                )
            messages.append(f"{name}: {', '.join(stored_values)}")

    return messages


def format_grouped_messages(
    grouped_messages: dict[str, list[str]],
    all_labels: list[str],
) -> list[str]:
    messages = []

    for message, labels in grouped_messages.items():
        messages.append(f"{message}{format_labels(labels, all_labels)}")

    return messages


def format_target_state_label(
    module: str,
    selected_targets: list[Path],
    all_targets: list[Path],
) -> str:
    if not selected_targets:
        return ""

    multiple_targets = len(all_targets) > 1
    all_labels = unique_values(
        [format_target_label(target) for target in all_targets]
        if multiple_targets
        else []
    )
    labels = (
        [format_target_label(target) for target in selected_targets]
        if multiple_targets
        else []
    )
    return f"{module}{format_labels(labels, all_labels)}"


def format_missing_message(
    module: str,
    missing_targets: list[Path],
    all_targets: list[Path],
) -> str:
    if not missing_targets:
        return ""

    label = format_target_state_label(module, missing_targets, all_targets)
    return f"{label} (missing output)"


def target_exists(target: Path) -> bool:
    return target.exists() or target.is_symlink()


def state_for_targets(
    *,
    module: str,
    targets: list[Path],
    parameters: dict[str, str],
    runtime_envs: list[str] | None = None,
    runtime_backend: RuntimeBackend = "conda",
    container_engine: str = "docker",
    container_image: str = "",
    old_files: set[Path] | None = None,
    check_runtime: bool = True,
) -> State:
    if not targets:
        return "pending", f"{module} (no target registered)", [], []

    old_files = old_files or set()
    missing = [target for target in targets if not target_exists(target)]
    if len(missing) == len(targets):
        return "pending", format_missing_message(module, missing, targets), [], missing

    runtime_envs = runtime_envs or []
    if not check_runtime:
        runtime_envs = []
    current_container = container_metadata(
        runtime_backend,
        container_engine,
        container_image,
    )
    current_runtime = runtime_environments(
        runtime_envs,
        backend=runtime_backend,
        container_engine=container_engine,
        container_image=container_image,
    )

    if not parameters and not current_runtime:
        if missing:
            return (
                "pending",
                format_missing_message(module, missing, targets),
                [],
                missing,
            )
        return "done", f"{module} (no sensitive parameters)", [], []

    expected_config_hash = config_hash(parameters)
    expected_metadata_hash = metadata_hash(
        parameters,
        runtime_backend,
        current_container,
        current_runtime,
    )
    stale_targets: list[Path] = []
    untracked_targets: list[Path] = []
    grouped_messages: dict[str, list[str]] = {}
    grouped_changes: dict[str, dict[str, dict[str, list[str]]]] = {}
    trusted_old = 0
    multiple_targets = len(targets) > 1
    all_labels = unique_values(
        [format_target_label(target) for target in targets] if multiple_targets else []
    )

    for target in targets:
        if not target_exists(target):
            continue

        if normalize_path(target) in old_files:
            trusted_old += 1
            continue

        label = format_target_label(target) if multiple_targets else ""
        sidecar = sidecar_path(target)
        metadata = read_metadata(sidecar)
        if metadata is None:
            untracked_targets.append(target)
            grouped_messages.setdefault("metadata missing", [])
            if label:
                grouped_messages["metadata missing"].append(label)
            continue

        solution = metadata.get("solution")
        partial_solution = (
            isinstance(solution, dict) and solution.get("status") == "partial"
        )
        stored_hash = (
            metadata.get("metadata_hash")
            if current_runtime
            else metadata.get("config_hash")
        )
        expected_hash = (
            expected_metadata_hash if current_runtime else expected_config_hash
        )
        stored_module = metadata.get("module")
        metadata_mismatch = stored_module != module or stored_hash != expected_hash
        if partial_solution or metadata_mismatch:
            stale_targets.append(target)

            if partial_solution and isinstance(solution, dict):
                message = partial_solution_message(solution)
                grouped_messages.setdefault(message, [])
                if label:
                    grouped_messages[message].append(label)

            if metadata_mismatch:
                changes = changed_parameters(metadata, parameters)
                changes_messages = runtime_changes(
                    metadata,
                    runtime_backend,
                    current_container,
                    current_runtime,
                )
                if changes:
                    for name, stored_value, current_value in changes:
                        grouped_changes.setdefault(name, {})
                        grouped_changes[name].setdefault(current_value, {})
                        grouped_changes[name][current_value].setdefault(
                            stored_value, []
                        )
                        if label:
                            grouped_changes[name][current_value][stored_value].append(
                                label
                            )
                for message in changes_messages:
                    grouped_messages.setdefault(message, [])
                    if label:
                        grouped_messages[message].append(label)
                if not changes and not changes_messages:
                    grouped_messages.setdefault("configuration hash mismatch", [])
                    if label:
                        grouped_messages["configuration hash mismatch"].append(label)

    if stale_targets:
        messages = format_grouped_messages(grouped_messages, all_labels)
        messages.extend(format_change_messages(grouped_changes, all_labels))
        unique_messages = unique_values(messages)
        return (
            "stale",
            f"{module} ({'; '.join(unique_messages)})",
            stale_targets,
            missing,
        )

    if untracked_targets:
        labels = grouped_messages.get("metadata missing", [])
        return "untracked", f"{module}{format_labels(labels, all_labels)}", [], missing

    if missing:
        return "pending", format_missing_message(module, missing, targets), [], missing

    if trusted_old:
        suffix = "old file" if trusted_old == 1 else "old files"
        return "done", f"{module} ({suffix})", [], []

    return "done", f"{module} (configuration up to date)", [], []


def done_targets_for_targets(
    *,
    module: str,
    targets: list[Path],
    parameters: dict[str, str],
    runtime_envs: list[str] | None = None,
    runtime_backend: RuntimeBackend = "conda",
    container_engine: str = "docker",
    container_image: str = "",
    old_files: set[Path] | None = None,
    check_runtime: bool = True,
) -> list[Path]:
    old_files = old_files or set()
    existing_targets = [target for target in targets if target_exists(target)]
    runtime_envs = runtime_envs or []
    if not check_runtime:
        runtime_envs = []
    current_container = container_metadata(
        runtime_backend,
        container_engine,
        container_image,
    )
    current_runtime = runtime_environments(
        runtime_envs,
        backend=runtime_backend,
        container_engine=container_engine,
        container_image=container_image,
    )

    if not parameters and not current_runtime:
        return existing_targets

    expected_hash = (
        metadata_hash(parameters, runtime_backend, current_container, current_runtime)
        if current_runtime
        else config_hash(parameters)
    )
    done_targets = []
    for target in existing_targets:
        if normalize_path(target) in old_files:
            done_targets.append(target)
            continue

        metadata = read_metadata(sidecar_path(target))
        if metadata is None:
            continue

        solution = metadata.get("solution")
        if isinstance(solution, dict) and solution.get("status") == "partial":
            continue

        stored_hash = (
            metadata.get("metadata_hash")
            if current_runtime
            else metadata.get("config_hash")
        )
        if metadata.get("module") == module and stored_hash == expected_hash:
            done_targets.append(target)

    return done_targets


def write_metadata(args: argparse.Namespace) -> None:
    parameters = parse_parameters(args.param)
    solution = solution_payload(
        args.solution_status,
        args.solution_kept,
        args.solution_total,
        args.solution_forwarded_from,
    )
    current_container = container_metadata(
        args.runtime_backend,
        args.container_engine,
        args.container_image,
    )
    if args.runtime_backend == "docker" and "error" in current_container:
        raise SystemExit(
            "cannot inspect container image: " + str(current_container["error"])
        )
    current_runtime = runtime_environments(
        args.runtime_env,
        backend=args.runtime_backend,
        container_engine=args.container_engine,
        container_image=args.container_image,
        strict=True,
    )
    parameter_hash = config_hash(parameters)
    current_runtime_hash = runtime_hash(current_runtime) if current_runtime else ""
    current_metadata_hash = metadata_hash(
        parameters,
        args.runtime_backend,
        current_container,
        current_runtime,
    )

    for target in args.target:
        target_path = Path(target)
        if not target_exists(target_path):
            raise SystemExit(f"target not found: {target}")

        sidecar = sidecar_path(target_path)
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "module": args.module,
            "target": str(target_path),
            "scbolt_git_hash": args.git_hash,
            "params_file": args.params_file,
            "sensitive_parameters": parameters,
            "runtime_backend": args.runtime_backend,
            "container": current_container,
            "runtime_environments": current_runtime,
            "runtime_hash": current_runtime_hash,
            "metadata_hash": current_metadata_hash,
            "config_hash": parameter_hash,
        }
        if solution is not None:
            payload["solution"] = solution
        with sidecar.open("w") as file:
            json.dump(payload, file, indent=2, sort_keys=True)
            file.write("\n")


def print_solution(args: argparse.Namespace) -> None:
    solution = read_solution(Path(args.target))
    if solution is None:
        return

    if args.field == "json":
        print(json.dumps(solution, sort_keys=True))
    elif args.field == "label":
        print(solution_label(solution))
    elif args.field == "status":
        print(solution.get("status", ""))
    elif args.field == "kept":
        value = solution.get("kept")
        if value is not None:
            print(value)
    elif args.field == "total":
        value = solution.get("total")
        if value is not None:
            print(value)
    elif args.field == "coverage":
        value = solution.get("coverage")
        if value is not None:
            print(value)
    elif args.field == "forwarded-from":
        value = solution.get("forwarded_from")
        if value is not None:
            print(value)


def print_state(args: argparse.Namespace) -> None:
    parameters = parse_parameters(args.param)
    targets = [Path(target) for target in args.target]
    old_files = {normalize_path(Path(path)) for path in args.old_file}
    status, message, stale_targets, missing_targets = state_for_targets(
        module=args.module,
        targets=targets,
        parameters=parameters,
        runtime_envs=args.runtime_env,
        runtime_backend=args.runtime_backend,
        container_engine=args.container_engine,
        container_image=args.container_image,
        old_files=old_files,
        check_runtime=True,
    )
    done_targets = done_targets_for_targets(
        module=args.module,
        targets=targets,
        parameters=parameters,
        runtime_envs=args.runtime_env,
        runtime_backend=args.runtime_backend,
        container_engine=args.container_engine,
        container_image=args.container_image,
        old_files=old_files,
        check_runtime=True,
    )
    fields = progress_fields_from_state(
        module=args.module,
        targets=targets,
        status=status,
        message=message,
        done_targets=done_targets,
        stale_targets=stale_targets,
        missing_targets=missing_targets,
    )
    stale_label = str(fields["stale-label"])
    pending_message = str(fields["pending-message"])
    pending_label = str(fields["pending-label"])

    if args.field == "status":
        print(status)
    elif args.field == "message":
        print(message)
    elif args.field == "progress":
        for name, value in fields.items():
            print(f"{name}\t{value}")
    elif args.field == "pending-message":
        if pending_message:
            print(pending_message)
    elif args.field == "pending-label":
        if pending_label:
            print(pending_label)
    elif args.field == "pending-targets":
        for target in missing_targets:
            print(target)
    elif args.field == "stale-label":
        if stale_label:
            print(stale_label)
    elif args.field == "cleanup-paths":
        for target in stale_targets:
            print(target)
            print(sidecar_path(target))
    elif args.field == "stale-targets":
        for target in stale_targets:
            print(target)
    elif args.field == "stale-cleanup":
        for target in stale_targets:
            print(target)
            print(sidecar_path(target))
    elif args.field == "sidecars":
        for target in targets:
            print(sidecar_path(target))
    else:
        print(f"{status}\t{message}")


def progress_fields(
    *,
    module: str,
    targets: list[Path],
    parameters: dict[str, str],
    runtime_envs: list[str],
    runtime_backend: RuntimeBackend,
    container_engine: str,
    container_image: str,
    old_files: set[Path],
    check_runtime: bool,
) -> dict[str, str]:
    status, message, stale_targets, missing_targets = state_for_targets(
        module=module,
        targets=targets,
        parameters=parameters,
        runtime_envs=runtime_envs,
        runtime_backend=runtime_backend,
        container_engine=container_engine,
        container_image=container_image,
        old_files=old_files,
        check_runtime=check_runtime,
    )
    done_targets = done_targets_for_targets(
        module=module,
        targets=targets,
        parameters=parameters,
        runtime_envs=runtime_envs,
        runtime_backend=runtime_backend,
        container_engine=container_engine,
        container_image=container_image,
        old_files=old_files,
        check_runtime=check_runtime,
    )
    return progress_fields_from_state(
        module=module,
        targets=targets,
        status=status,
        message=message,
        done_targets=done_targets,
        stale_targets=stale_targets,
        missing_targets=missing_targets,
    )


def progress_fields_from_state(
    *,
    module: str,
    targets: list[Path],
    status: Status,
    message: str,
    done_targets: list[Path],
    stale_targets: list[Path],
    missing_targets: list[Path],
) -> dict[str, str]:
    stale_label = format_target_state_label(module, stale_targets, targets)
    if status == "stale" and "partial solution" in message:
        stale_label = message

    return {
        "status": status,
        "message": message,
        "done-label": format_target_state_label(module, done_targets, targets),
        "stale-label": stale_label,
        "pending-message": format_missing_message(module, missing_targets, targets),
        "pending-label": format_target_state_label(module, missing_targets, targets),
    }


def read_progress_manifest(path: Path) -> list[ProgressRecord]:
    records: list[ProgressRecord] = []
    current: ProgressRecord | None = None

    with path.open() as file:
        for raw_line in file:
            line = raw_line.rstrip("\n")
            if not line:
                continue

            key, _, value = line.partition("\t")
            if key == "module":
                if current is not None:
                    records.append(current)
                current = {
                    "module": value,
                    "targets": [],
                    "params": [],
                    "runtime_envs": [],
                    "deps": "",
                }
            elif current is None:
                raise SystemExit("invalid progress manifest: entry before module")
            elif key == "target":
                current_targets = current["targets"]
                assert isinstance(current_targets, list)
                current_targets.append(value)
            elif key == "param":
                current_params = current["params"]
                assert isinstance(current_params, list)
                current_params.append(value)
            elif key == "runtime-env":
                current_runtime_envs = current["runtime_envs"]
                assert isinstance(current_runtime_envs, list)
                current_runtime_envs.append(value)
            elif key == "deps":
                current["deps"] = value
            elif key == "end":
                records.append(current)
                current = None
            else:
                raise SystemExit(f"invalid progress manifest entry: {key}")

    if current is not None:
        records.append(current)

    return records


def print_batch_progress(args: argparse.Namespace) -> None:
    old_files = {normalize_path(Path(path)) for path in args.old_file}
    records = read_progress_manifest(Path(args.manifest))

    for record in records:
        module = str(record["module"])
        targets = [Path(target) for target in record["targets"]]
        parameters = parse_parameters(list(record["params"]))
        runtime_envs = list(record["runtime_envs"])
        fields = progress_fields(
            module=module,
            targets=targets,
            parameters=parameters,
            runtime_envs=runtime_envs,
            runtime_backend=args.runtime_backend,
            container_engine=args.container_engine,
            container_image=args.container_image,
            old_files=old_files,
            check_runtime=not args.skip_runtime,
        )
        fields["deps"] = str(record["deps"])
        for name, value in fields.items():
            print(f"{module}\t{name}\t{value}")


def print_batch_clean(args: argparse.Namespace) -> None:
    old_files = {normalize_path(Path(path)) for path in args.old_file}
    records = read_progress_manifest(Path(args.manifest))

    for record in records:
        module = str(record["module"])
        targets = [Path(target) for target in record["targets"]]
        parameters = parse_parameters(list(record["params"]))
        runtime_envs = list(record["runtime_envs"])
        status, _message, stale_targets, _missing_targets = state_for_targets(
            module=module,
            targets=targets,
            parameters=parameters,
            runtime_envs=runtime_envs,
            runtime_backend=args.runtime_backend,
            container_engine=args.container_engine,
            container_image=args.container_image,
            old_files=old_files,
        )

        print(f"{module}\tstatus\t{status}")
        print(f"{module}\tdeps\t{record['deps']}")

        for target in stale_targets:
            print(f"{module}\tstale-output\t{target}")
        for target in stale_targets:
            print(f"{module}\tstale-cleanup\t{target}")
            print(f"{module}\tstale-cleanup\t{sidecar_path(target)}")

        for target in targets:
            print(f"{module}\toutput\t{target}")
        for target in targets:
            print(f"{module}\tsidecar\t{sidecar_path(target)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        formatter_class=cli.HelpFormatter,
        prog=Path(__file__).name,
        description="Manage scBOLT output metadata sidecars.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    write = subparsers.add_parser(
        "write",
        formatter_class=cli.HelpFormatter,
        help="write metadata sidecars",
    )
    write.add_argument("--module", required=True)
    write.add_argument("--target", action="append", required=True)
    write.add_argument("--params-file", required=True)
    write.add_argument("--git-hash", required=True)
    write.add_argument("--param", action="append", default=[])
    write.add_argument(
        "--solution-status",
        choices=["global", "partial", "failed"],
        default=None,
    )
    write.add_argument("--solution-kept", type=int, default=None)
    write.add_argument("--solution-total", type=int, default=None)
    write.add_argument("--solution-forwarded-from", default=None)
    write.add_argument("--runtime-env", action="append", default=[])
    add_runtime_arguments(write)
    write.set_defaults(func=write_metadata)

    solution = subparsers.add_parser(
        "solution",
        formatter_class=cli.HelpFormatter,
        help="read solution metadata from a sidecar",
    )
    solution.add_argument("--target", required=True)
    solution.add_argument(
        "--field",
        choices=[
            "json",
            "label",
            "status",
            "kept",
            "total",
            "coverage",
            "forwarded-from",
        ],
        default="label",
    )
    solution.set_defaults(func=print_solution)

    state = subparsers.add_parser(
        "state",
        formatter_class=cli.HelpFormatter,
        help="compare metadata sidecars",
    )
    state.add_argument("--module", required=True)
    state.add_argument("--target", action="append", default=[])
    state.add_argument("--old-file", action="append", default=[])
    state.add_argument("--param", action="append", default=[])
    state.add_argument("--runtime-env", action="append", default=[])
    add_runtime_arguments(state)
    state.add_argument(
        "--field",
        choices=[
            "all",
            "status",
            "message",
            "progress",
            "pending-message",
            "pending-label",
            "pending-targets",
            "stale-label",
            "cleanup-paths",
            "stale-targets",
            "stale-cleanup",
            "sidecars",
        ],
        default="all",
    )
    state.set_defaults(func=print_state)

    batch_progress = subparsers.add_parser(
        "batch-progress",
        formatter_class=cli.HelpFormatter,
        help="compare metadata sidecars for progress reports",
    )
    batch_progress.add_argument("--manifest", required=True)
    batch_progress.add_argument("--old-file", action="append", default=[])
    batch_progress.add_argument("--skip-runtime", action="store_true")
    add_runtime_arguments(batch_progress)
    batch_progress.set_defaults(func=print_batch_progress)

    batch_clean = subparsers.add_parser(
        "batch-clean",
        formatter_class=cli.HelpFormatter,
        help="compare metadata sidecars for stale output cleanup",
    )
    batch_clean.add_argument("--manifest", required=True)
    batch_clean.add_argument("--old-file", action="append", default=[])
    add_runtime_arguments(batch_clean)
    batch_clean.set_defaults(func=print_batch_clean)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
