"""Pure helpers for ``scripts/validate-tb-port.sh``.

The bash driver shells out to subcommands here for parsing the experiment
metadata returned by ``bn experiments show <task> --format json`` and for
rewriting the upstream Terminal Bench ``solution.sh``. Keeping logic in
Python makes the helper unit-testable without invoking Docker or ``bn``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

SUPPORTED_VERIFIER_HEADS = ("pytest", "bash")

SOLUTION_PRELUDE = """#!/usr/bin/env bash
set -euo pipefail

if ! command -v python >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  python() { python3 "$@"; }
fi

if ! command -v pip >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  pip() { python3 -m pip "$@"; }
fi

"""


def select_verifier_command(experiment: dict) -> str:
    """Return the script command Bunsen runs as the Tests Pass verifier.

    Prefers the criterion with id ``tests-pass``; falls back to the first
    ``type: script`` criterion. Raises if no script criterion exists.
    """
    evaluation = experiment.get("evaluation") or {}
    criteria = evaluation.get("criteria") or []
    script_criteria = [c for c in criteria if isinstance(c, dict) and c.get("type") == "script"]
    if not script_criteria:
        raise ValueError(
            "No script criterion found in evaluation.criteria — "
            "validate-tb-port can only validate experiments whose Tests Pass "
            "scorer is a shell command."
        )
    primary = next(
        (c for c in script_criteria if c.get("id") == "tests-pass"),
        script_criteria[0],
    )
    cmd = (primary.get("run") or "").strip()
    if not cmd:
        raise ValueError(
            f"Script criterion {primary.get('id')!r} is missing a non-empty 'run' field."
        )
    return cmd


def validate_verifier_command(cmd: str) -> None:
    """Reject verifier shapes the helper does not know how to drive.

    Supported heads:
      * ``pytest <args>`` — image's default Python; pytest is pip-installed at run time.
      * ``bash <path>``   — image already has whatever the script needs (e.g. a baked venv).
    """
    head = cmd.split(maxsplit=1)[0] if cmd else ""
    if head not in SUPPORTED_VERIFIER_HEADS:
        supported = ", ".join(f"{p!r} <args>" for p in SUPPORTED_VERIFIER_HEADS)
        raise ValueError(
            f"Unsupported verifier command: {cmd!r}. "
            f"validate-tb-port supports: {supported}."
        )


def collect_workspace_sources(
    experiment: dict, experiment_dir: Path | None = None
) -> list[tuple[str, str, str]]:
    """Return staging instructions as ``(kind, source_path, target)`` tuples.

    Prefers the pre-resolved ``workspaceSources`` array that ``bn experiments
    show`` populates (already absolute paths, normalized type). Falls back to
    parsing ``experiment.workspace.sources`` so the function is testable
    without ``bn``. Returns ``[("path", <experiment_dir>/workspace, "")]`` if
    no sources are declared but a ``workspace/`` directory exists, mirroring
    Bunsen's own default-workspace behaviour.
    """
    resolved = experiment.get("workspaceSources")
    if isinstance(resolved, list) and resolved:
        out: list[tuple[str, str, str]] = []
        for src in resolved:
            kind = src.get("type")
            source_path = src.get("sourcePath", "")
            target = src.get("target") or ""
            if kind not in ("path", "image"):
                raise ValueError(f"Unknown workspace source type: {kind!r}")
            if not source_path:
                raise ValueError(f"Workspace source missing sourcePath: {src!r}")
            out.append((kind, source_path, target))
        return out

    workspace = experiment.get("workspace") or {}
    raw_sources = workspace.get("sources") or []
    if raw_sources:
        if experiment_dir is None:
            raise ValueError(
                "experiment_dir is required when resolving raw workspace.sources"
            )
        experiment_dir = experiment_dir.resolve()
        out = []
        for entry in raw_sources:
            target = entry.get("target") or ""
            if "path" in entry:
                source_path = (experiment_dir / entry["path"]).resolve()
                out.append(("path", str(source_path), target))
            elif "imagePath" in entry:
                out.append(("image", entry["imagePath"], target))
            else:
                raise ValueError(
                    f"Workspace source entry must have 'path' or 'imagePath': {entry!r}"
                )
        return out

    if experiment_dir is not None:
        default_workspace = experiment_dir.resolve() / "workspace"
        if default_workspace.is_dir():
            return [("path", str(default_workspace), "")]
    return []


def rewrite_solution(src: str) -> str:
    """Adapt an upstream Terminal Bench ``solution.sh`` for the Bunsen runtime.

    Strips the original shebang, rewrites ``/app`` -> ``/workspace`` and
    ``/tests/`` -> ``/bunsen/verifiers/``, and prepends a fixed prelude that
    ensures ``python``/``pip`` resolve when the image only ships ``python3``.
    """
    if src.startswith("#!"):
        src = "".join(src.splitlines(keepends=True)[1:])
    src = src.replace("/app", "/workspace")
    src = src.replace("/tests/", "/bunsen/verifiers/")
    return SOLUTION_PRELUDE + src.lstrip("\n")


def build_summary(experiment: dict) -> dict[str, str]:
    """Extract the metadata fields ``validate-tb-port.sh`` needs into a flat dict."""
    image_cfg = (experiment.get("environment") or {}).get("image") or {}
    base_image = image_cfg.get("base") or ""
    has_dockerfile = bool(experiment.get("hasDockerfile"))
    platforms = (experiment.get("environment") or {}).get("platforms") or []
    platform = platforms[0] if platforms else ""
    experiment_dir = experiment.get("dir") or ""
    verifiers_path = experiment.get("verifiersPath") or ""

    verifier_command = select_verifier_command(experiment)
    validate_verifier_command(verifier_command)

    return {
        "BASE_IMAGE": base_image,
        "HAS_DOCKERFILE": "1" if has_dockerfile else "0",
        "PLATFORM": platform,
        "EXPERIMENT_DIR": experiment_dir,
        "VERIFIERS_DIR": verifiers_path,
        "VERIFIER_COMMAND": verifier_command,
    }


def _read_experiment_json(stream) -> dict:
    payload = json.load(stream)
    if isinstance(payload, dict) and "experiment" in payload:
        return payload["experiment"]
    return payload


def _cmd_summary(args: argparse.Namespace) -> int:
    experiment = _read_experiment_json(sys.stdin)
    for key, value in build_summary(experiment).items():
        sys.stdout.write(f"{key}={shlex.quote(value)}\n")
    return 0


def _cmd_workspace_sources(args: argparse.Namespace) -> int:
    experiment = _read_experiment_json(sys.stdin)
    for kind, source, target in collect_workspace_sources(experiment):
        sys.stdout.write(f"{kind}\t{source}\t{target}\n")
    return 0


def _cmd_rewrite_solution(args: argparse.Namespace) -> int:
    src = Path(args.src).read_text()
    Path(args.dst).write_text(rewrite_solution(src))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("summary", help="Emit shell KEY=VALUE lines for experiment metadata")
    p.set_defaults(func=_cmd_summary)

    p = sub.add_parser("workspace-sources", help="Emit one TSV row per workspace source")
    p.set_defaults(func=_cmd_workspace_sources)

    p = sub.add_parser("rewrite-solution", help="Rewrite upstream solution.sh into <dst>")
    p.add_argument("src")
    p.add_argument("dst")
    p.set_defaults(func=_cmd_rewrite_solution)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
