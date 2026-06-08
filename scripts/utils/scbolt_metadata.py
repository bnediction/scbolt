#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal


Status = Literal["done", "stale", "pending", "untracked"]


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


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve()


def config_hash(parameters: dict[str, str]) -> str:
    payload = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def read_metadata(path: Path) -> dict[str, object] | None:
    try:
        with path.open() as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


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
    reference_output_dirs = {
        "clust",
        "count",
        "fastq",
        "mstates",
        "prep",
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
    return f" ({', '.join(labels)})"


def format_change_messages(
    grouped_changes: dict[str, dict[str, dict[str, list[str]]]],
    all_labels: list[str],
) -> list[str]:
    messages = []

    for name, current_groups in grouped_changes.items():
        for current_value, stored_groups in current_groups.items():
            if len(stored_groups) == 1:
                stored_value, labels = next(iter(stored_groups.items()))
                label = format_labels(labels, all_labels)
                messages.append(f"{name}: {stored_value} -> {current_value}{label}")
                continue

            stored_values = []
            for stored_value, labels in stored_groups.items():
                label = format_labels(labels, all_labels)
                stored_values.append(f"{stored_value} -> {current_value}{label}")
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


def target_exists(target: Path) -> bool:
    return target.exists() or target.is_symlink()


def state_for_targets(
    *,
    module: str,
    targets: list[Path],
    parameters: dict[str, str],
    old_files: set[Path] | None = None,
) -> tuple[Status, str, list[Path]]:
    if not targets:
        return "pending", f"{module} (no target registered)", []

    old_files = old_files or set()
    missing = [target for target in targets if not target_exists(target)]
    if missing:
        return "pending", f"{module} (missing output)", []

    if not parameters:
        return "done", f"{module} (no sensitive parameters)", []

    expected_hash = config_hash(parameters)
    stale_targets: list[Path] = []
    untracked_targets: list[Path] = []
    grouped_messages: dict[str, list[str]] = {}
    grouped_changes: dict[str, dict[str, dict[str, list[str]]]] = {}
    trusted_old = 0
    multiple_targets = len(targets) > 1
    all_labels = unique_values(
        [format_target_label(target) for target in targets]
        if multiple_targets
        else []
    )

    for target in targets:
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

        stored_hash = metadata.get("config_hash")
        stored_module = metadata.get("module")
        if stored_module != module or stored_hash != expected_hash:
            stale_targets.append(target)
            changes = changed_parameters(metadata, parameters)
            if changes:
                for name, stored_value, current_value in changes:
                    grouped_changes.setdefault(name, {})
                    grouped_changes[name].setdefault(current_value, {})
                    grouped_changes[name][current_value].setdefault(stored_value, [])
                    if label:
                        grouped_changes[name][current_value][stored_value].append(label)
            else:
                grouped_messages.setdefault("configuration hash mismatch", [])
                if label:
                    grouped_messages["configuration hash mismatch"].append(label)

    if stale_targets:
        messages = format_grouped_messages(grouped_messages, all_labels)
        messages.extend(format_change_messages(grouped_changes, all_labels))
        unique_messages = unique_values(messages)
        return "stale", f"{module} ({'; '.join(unique_messages)})", stale_targets

    if untracked_targets:
        labels = grouped_messages.get("metadata missing", [])
        return "untracked", f"{module}{format_labels(labels, all_labels)}", []

    if trusted_old:
        suffix = "old file" if trusted_old == 1 else "old files"
        return "done", f"{module} ({suffix})", []

    return "done", f"{module} (configuration up to date)", []


def write_metadata(args: argparse.Namespace) -> None:
    parameters = parse_parameters(args.param)
    metadata_hash = config_hash(parameters)

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
            "config_hash": metadata_hash,
        }
        with sidecar.open("w") as file:
            json.dump(payload, file, indent=2, sort_keys=True)
            file.write("\n")


def print_state(args: argparse.Namespace) -> None:
    parameters = parse_parameters(args.param)
    targets = [Path(target) for target in args.target]
    old_files = {normalize_path(Path(path)) for path in args.old_file}
    status, message, stale_targets = state_for_targets(
        module=args.module,
        targets=targets,
        parameters=parameters,
        old_files=old_files,
    )

    if args.field == "status":
        print(status)
    elif args.field == "message":
        print(message)
    elif args.field == "cleanup-paths":
        for target in stale_targets:
            print(target)
            print(sidecar_path(target))
    elif args.field == "sidecars":
        for target in targets:
            print(sidecar_path(target))
    else:
        print(f"{status}\t{message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description="Manage scBOLT output metadata sidecars.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    write = subparsers.add_parser("write", help="write metadata sidecars")
    write.add_argument("--module", required=True)
    write.add_argument("--target", action="append", required=True)
    write.add_argument("--params-file", required=True)
    write.add_argument("--git-hash", required=True)
    write.add_argument("--param", action="append", default=[])
    write.set_defaults(func=write_metadata)

    state = subparsers.add_parser("state", help="compare metadata sidecars")
    state.add_argument("--module", required=True)
    state.add_argument("--target", action="append", default=[])
    state.add_argument("--old-file", action="append", default=[])
    state.add_argument("--param", action="append", default=[])
    state.add_argument(
        "--field",
        choices=["all", "status", "message", "cleanup-paths", "sidecars"],
        default="all",
    )
    state.set_defaults(func=print_state)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
