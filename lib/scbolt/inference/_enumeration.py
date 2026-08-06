"""Checkpoint primitives for long-running Boolean-network enumeration."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ENUMERATION_CHECKPOINT_SCHEMA = 1
ENUMERATION_CHECKPOINT_FILE = ".enumeration-checkpoint.json"
ENUMERATION_TEMP_PREFIX = ".solution-"
SignedEdge = tuple[str, str, int]


@dataclass(frozen=True)
class EnumerationRecovery:
    """Describe complete outputs recovered before enumeration."""

    solution_directories: tuple[Path, ...]
    discarded_directories: tuple[Path, ...]
    elapsed_seconds: float
    reset_reason: str | None = None


class BooleanNetworkEnumerationCheckpoint:
    """Manage atomic numbered outputs and resumable enumeration metadata."""

    def __init__(
        self,
        outdir: str | Path,
        *,
        config_formats: Sequence[str],
        graph_formats: Sequence[str],
        fingerprint: str,
    ) -> None:
        self.outdir = Path(outdir)
        self.config_formats = tuple(config_formats)
        self.graph_formats = tuple(graph_formats)
        self.fingerprint = fingerprint
        self.checkpoint_file = self.outdir / ENUMERATION_CHECKPOINT_FILE

    def prepare(self, *, force_restart: bool = False) -> EnumerationRecovery:
        """Validate a checkpoint and recover its contiguous solution prefix."""

        self.outdir.mkdir(parents=True, exist_ok=True)
        metadata, reset_reason = self._read_metadata()
        if force_restart:
            reset_reason = "requested rebuild"
        elif metadata is not None and metadata.get("fingerprint") != self.fingerprint:
            reset_reason = "enumeration inputs changed"

        if reset_reason is not None:
            self._clear_outputs()
            self.outdir.mkdir(parents=True, exist_ok=True)
            metadata = None

        self._remove_temporary_directories()
        complete, discarded = self._recover_solution_prefix()
        elapsed_seconds = self._metadata_elapsed(metadata)
        if metadata is None and complete:
            elapsed_seconds = self._estimate_elapsed(complete)

        self.write_state(
            solution_count=len(complete),
            elapsed_seconds=elapsed_seconds,
        )
        return EnumerationRecovery(
            solution_directories=complete,
            discarded_directories=discarded,
            elapsed_seconds=elapsed_seconds,
            reset_reason=reset_reason,
        )

    @contextmanager
    def atomic_solution_directory(self, index: int) -> Iterator[Path]:
        """Yield a temporary output directory and publish it atomically."""

        if index < 1:
            raise ValueError("Boolean-network solution index must be positive")

        destination = self.outdir / str(index)
        temporary = self.outdir / f"{ENUMERATION_TEMP_PREFIX}{index}.tmp"
        if destination.exists():
            raise FileExistsError(destination)
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir(parents=True)
        try:
            yield temporary
            os.replace(temporary, destination)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    def write_state(self, *, solution_count: int, elapsed_seconds: float) -> None:
        """Persist checkpoint metadata with an atomic file replacement."""

        metadata = {
            "schema": ENUMERATION_CHECKPOINT_SCHEMA,
            "fingerprint": self.fingerprint,
            "solutions": solution_count,
            "elapsed_seconds": max(0.0, elapsed_seconds),
        }
        temporary = self.checkpoint_file.with_name(
            f"{self.checkpoint_file.name}.tmp"
        )
        temporary.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.checkpoint_file)

    def required_output_names(self) -> tuple[str, ...]:
        """Return files required for one complete numbered solution."""

        return (
            "model.bnet",
            "noi.txt",
            *(f"configs.{fmt}" for fmt in self.config_formats),
            *(f"ig.{fmt}" for fmt in self.graph_formats),
        )

    def _read_metadata(self) -> tuple[dict[str, Any] | None, str | None]:
        """Read valid checkpoint metadata or identify a corrupt checkpoint."""

        if not self.checkpoint_file.is_file():
            return None, None
        try:
            metadata = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, "invalid enumeration checkpoint"
        if not isinstance(metadata, dict):
            return None, "invalid enumeration checkpoint"
        if metadata.get("schema") != ENUMERATION_CHECKPOINT_SCHEMA:
            return None, "unsupported enumeration checkpoint"
        return metadata, None

    def _clear_outputs(self) -> None:
        """Remove generated enumeration outputs before a fresh rebuild."""

        shutil.rmtree(self.outdir, ignore_errors=True)

    def _remove_temporary_directories(self) -> None:
        """Remove unpublished solution directories left by interruptions."""

        for path in self.outdir.glob(f"{ENUMERATION_TEMP_PREFIX}*.tmp"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)

    def _recover_solution_prefix(self) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
        """Keep the complete contiguous numbered prefix and discard its tail."""

        numbered = sorted(
            (
                (int(path.name), path)
                for path in self.outdir.iterdir()
                if path.is_dir() and path.name.isdigit()
            ),
            key=lambda item: item[0],
        )
        required = self.required_output_names()
        complete = []
        discarded = []
        expected_index = 1
        invalid_tail = False

        for index, path in numbered:
            is_complete = all((path / name).is_file() for name in required)
            if invalid_tail or index != expected_index or not is_complete:
                invalid_tail = True
                discarded.append(path)
                shutil.rmtree(path)
                continue
            complete.append(path)
            expected_index += 1

        return tuple(complete), tuple(discarded)

    @staticmethod
    def _metadata_elapsed(metadata: Mapping[str, Any] | None) -> float:
        """Return a valid persisted elapsed duration."""

        if metadata is None:
            return 0.0
        elapsed = metadata.get("elapsed_seconds", 0.0)
        if not isinstance(elapsed, (int, float)) or elapsed < 0:
            return 0.0
        return float(elapsed)

    @staticmethod
    def _estimate_elapsed(solution_directories: Sequence[Path]) -> float:
        """Estimate legacy checkpoint time from complete output timestamps."""

        timestamps = [
            path.stat().st_mtime
            for directory in solution_directories
            for path in directory.iterdir()
            if path.is_file()
        ]
        if len(timestamps) < 2:
            return 0.0
        return max(timestamps) - min(timestamps)


def enumeration_fingerprint(
    files: Iterable[str | Path],
    settings: Mapping[str, Any],
) -> str:
    """Hash enumeration inputs and solution-space settings."""

    digest = hashlib.sha256()
    digest.update(f"scbolt-enumeration-{ENUMERATION_CHECKPOINT_SCHEMA}\n".encode())
    digest.update(
        json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()
    )
    for value in files:
        path = Path(value)
        digest.update(f"\n{path.name}\0".encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def build_subset_minimal_blockers(
    influence_graphs: Iterable[Collection[SignedEdge]],
) -> str:
    """Build ASP constraints excluding known graphs and their supergraphs."""

    graphs = tuple(dict.fromkeys(frozenset(graph) for graph in influence_graphs))
    if not graphs:
        return ""

    rules = [
        "scbolt_checkpoint_present(L,N,S) :- clause(N,C,L,S)",
        (
            "scbolt_checkpoint_missing(I) :- "
            "scbolt_checkpoint_edge(I,L,N,S), "
            "not scbolt_checkpoint_present(L,N,S)"
        ),
        (
            ":- scbolt_checkpoint_solution(I), "
            "not scbolt_checkpoint_missing(I)"
        ),
    ]
    for index, graph in enumerate(graphs, start=1):
        rules.append(f"scbolt_checkpoint_solution({index})")
        for source, target, sign in sorted(graph):
            if sign not in {-1, 1}:
                raise ValueError(f"unsupported influence edge sign: {sign}")
            source_symbol = json.dumps(source, ensure_ascii=True)
            target_symbol = json.dumps(target, ensure_ascii=True)
            rules.append(
                "scbolt_checkpoint_edge"
                f"({index},{source_symbol},{target_symbol},{sign})"
            )
    return ".\n".join(rules) + "."


def elapsed_since(started_at: float, previous_elapsed: float = 0.0) -> float:
    """Return cumulative active enumeration time."""

    return previous_elapsed + max(0.0, time.monotonic() - started_at)
