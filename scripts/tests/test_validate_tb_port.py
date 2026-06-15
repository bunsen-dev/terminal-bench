"""Tests for `scripts/validate_tb_port_lib.py`.

These exercise the pure-Python pieces the bash driver shells out to:
verifier-command selection, workspace-source resolution, and solution
rewriting. They cover the simple pytest TB port shape and the native-fork
shape (image-backed sources, `bash run_tests.sh` verifier) plus the failure
modes the helper is supposed to surface clearly.
"""

import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "validate_tb_port_lib.py"
SPEC = importlib.util.spec_from_file_location("validate_tb_port_lib", MODULE_PATH)
validate_tb_port_lib = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_tb_port_lib)


def _simple_pytest_port() -> dict:
    """Mechanically-converted TB port: single pytest criterion, local workspace."""
    return {
        "version": "v1",
        "name": "raman-fitting",
        "task": {"prompt": "..."},
        "environment": {"image": {"base": "bunsen/headless"}},
        "evaluation": {
            "container": "dedicated",
            "criteria": [
                {
                    "id": "tests-pass",
                    "title": "Tests Pass",
                    "type": "script",
                    "scores": [0, 1],
                    "timeout": "3m",
                    "run": "pytest /bunsen/verifiers/test_outputs.py -v",
                }
            ],
        },
        "workspace": {"sources": [{"path": "./workspace"}]},
        "dir": "/tmp/raman-fitting",
        "verifiersPath": "/tmp/raman-fitting/verifiers",
        "hasDockerfile": False,
        "workspaceSources": [
            {
                "type": "path",
                "sourcePath": "/tmp/raman-fitting/workspace",
                "target": None,
                "original": {"path": "./workspace"},
                "index": 0,
            }
        ],
    }


def _native_fork_imagepath() -> dict:
    """Native fork: image-backed workspace source + bash run_tests.sh verifier."""
    return {
        "version": "v1",
        "name": "train-fasttext",
        "task": {"prompt": "..."},
        "environment": {"image": {"base": "bunsen/headless"}, "platforms": ["linux/amd64"]},
        "evaluation": {
            "container": "dedicated",
            "criteria": [
                {
                    "id": "tests-pass",
                    "title": "Tests Pass",
                    "type": "script",
                    "scores": [0, 1],
                    "timeout": "4m",
                    "run": "bash /bunsen/verifiers/run_tests.sh",
                }
            ],
        },
        "workspace": {"sources": [{"imagePath": "/app/data", "target": "data"}]},
        "dir": "/tmp/train-fasttext",
        "verifiersPath": "/tmp/train-fasttext/verifiers",
        "hasDockerfile": True,
        "workspaceSources": [
            {
                "type": "image",
                "sourcePath": "/app/data",
                "target": "data",
                "original": {"imagePath": "/app/data", "target": "data"},
                "index": 0,
            }
        ],
    }


class SelectVerifierCommandTests(unittest.TestCase):
    def test_picks_tests_pass_pytest_command_for_simple_port(self):
        cmd = validate_tb_port_lib.select_verifier_command(_simple_pytest_port())
        self.assertEqual(cmd, "pytest /bunsen/verifiers/test_outputs.py -v")

    def test_picks_bash_run_tests_for_native_fork(self):
        cmd = validate_tb_port_lib.select_verifier_command(_native_fork_imagepath())
        self.assertEqual(cmd, "bash /bunsen/verifiers/run_tests.sh")

    def test_prefers_tests_pass_id_over_first_script_criterion(self):
        experiment = {
            "evaluation": {
                "criteria": [
                    {"id": "preflight", "type": "script", "run": "echo skip"},
                    {"id": "tests-pass", "type": "script", "run": "pytest -v"},
                ]
            }
        }
        self.assertEqual(
            validate_tb_port_lib.select_verifier_command(experiment),
            "pytest -v",
        )

    def test_falls_back_to_first_script_criterion_when_no_tests_pass(self):
        experiment = {
            "evaluation": {
                "criteria": [
                    {"id": "lint", "type": "script", "run": "ruff check ."},
                    {"id": "judge", "type": "judge", "instructions": "..."},
                ]
            }
        }
        self.assertEqual(
            validate_tb_port_lib.select_verifier_command(experiment),
            "ruff check .",
        )

    def test_raises_when_no_script_criterion(self):
        experiment = {
            "evaluation": {
                "criteria": [{"id": "judge", "type": "judge", "instructions": "..."}]
            }
        }
        with self.assertRaisesRegex(ValueError, "No script criterion"):
            validate_tb_port_lib.select_verifier_command(experiment)

    def test_raises_when_run_field_is_empty(self):
        experiment = {
            "evaluation": {
                "criteria": [{"id": "tests-pass", "type": "script", "run": "  "}]
            }
        }
        with self.assertRaisesRegex(ValueError, "missing a non-empty 'run'"):
            validate_tb_port_lib.select_verifier_command(experiment)


class ValidateVerifierCommandTests(unittest.TestCase):
    def test_accepts_pytest(self):
        validate_tb_port_lib.validate_verifier_command(
            "pytest /bunsen/verifiers/test_outputs.py -v"
        )

    def test_accepts_bash_run_tests(self):
        validate_tb_port_lib.validate_verifier_command(
            "bash /bunsen/verifiers/run_tests.sh"
        )

    def test_rejects_unsupported_head_with_precise_message(self):
        with self.assertRaises(ValueError) as ctx:
            validate_tb_port_lib.validate_verifier_command("node /verify.js")
        message = str(ctx.exception)
        self.assertIn("Unsupported verifier command", message)
        self.assertIn("'node /verify.js'", message)
        self.assertIn("pytest", message)
        self.assertIn("bash", message)

    def test_rejects_empty_command(self):
        with self.assertRaises(ValueError):
            validate_tb_port_lib.validate_verifier_command("")


class CollectWorkspaceSourcesTests(unittest.TestCase):
    def test_uses_resolved_workspace_sources_for_simple_port(self):
        sources = validate_tb_port_lib.collect_workspace_sources(_simple_pytest_port())
        self.assertEqual(
            sources,
            [("path", "/tmp/raman-fitting/workspace", "")],
        )

    def test_uses_resolved_workspace_sources_for_image_path_native_fork(self):
        sources = validate_tb_port_lib.collect_workspace_sources(_native_fork_imagepath())
        self.assertEqual(sources, [("image", "/app/data", "data")])

    def test_falls_back_to_raw_workspace_sources_when_resolved_missing(self):
        with tempfile.TemporaryDirectory() as td:
            experiment_dir = Path(td)
            (experiment_dir / "workspace").mkdir()
            experiment = {
                "workspace": {
                    "sources": [
                        {"path": "./workspace", "target": "src"},
                        {"imagePath": "/opt/data", "target": "data"},
                    ]
                }
            }
            sources = validate_tb_port_lib.collect_workspace_sources(
                experiment, experiment_dir
            )
            expected_path = str((experiment_dir / "workspace").resolve())
            self.assertEqual(
                sources,
                [
                    ("path", expected_path, "src"),
                    ("image", "/opt/data", "data"),
                ],
            )

    def test_falls_back_to_default_workspace_dir_when_no_sources_declared(self):
        with tempfile.TemporaryDirectory() as td:
            experiment_dir = Path(td)
            (experiment_dir / "workspace").mkdir()
            sources = validate_tb_port_lib.collect_workspace_sources(
                {}, experiment_dir
            )
            self.assertEqual(
                sources,
                [("path", str((experiment_dir / "workspace").resolve()), "")],
            )

    def test_returns_empty_when_no_sources_and_no_default_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            sources = validate_tb_port_lib.collect_workspace_sources({}, Path(td))
            self.assertEqual(sources, [])

    def test_raises_for_unknown_resolved_source_type(self):
        experiment = {
            "workspaceSources": [
                {"type": "ftp", "sourcePath": "ftp://x", "target": ""}
            ]
        }
        with self.assertRaisesRegex(ValueError, "Unknown workspace source type"):
            validate_tb_port_lib.collect_workspace_sources(experiment)

    def test_raises_for_raw_source_missing_path_and_imagePath(self):
        with tempfile.TemporaryDirectory() as td:
            experiment = {"workspace": {"sources": [{"target": "data"}]}}
            with self.assertRaisesRegex(ValueError, "must have 'path' or 'imagePath'"):
                validate_tb_port_lib.collect_workspace_sources(experiment, Path(td))


class RewriteSolutionTests(unittest.TestCase):
    def test_strips_shebang_and_rewrites_app_paths(self):
        src = (
            "#!/bin/bash\n"
            "set -e\n"
            "ls /app/data\n"
            "cd /app && cp /tests/expected.txt /app/out.txt\n"
        )
        out = validate_tb_port_lib.rewrite_solution(src)
        self.assertTrue(out.startswith("#!/usr/bin/env bash\nset -euo pipefail\n"))
        self.assertNotIn("#!/bin/bash", out)
        self.assertIn("ls /workspace/data", out)
        self.assertIn("cd /workspace", out)
        self.assertIn("/bunsen/verifiers/expected.txt", out)
        self.assertNotIn("/app/", out)
        self.assertNotIn("/tests/", out)

    def test_handles_solution_without_shebang(self):
        out = validate_tb_port_lib.rewrite_solution("echo hi /app\n")
        self.assertIn("echo hi /workspace", out)


class BuildSummaryTests(unittest.TestCase):
    def test_simple_pytest_port_summary(self):
        summary = validate_tb_port_lib.build_summary(_simple_pytest_port())
        self.assertEqual(summary["BASE_IMAGE"], "bunsen/headless")
        self.assertEqual(summary["HAS_DOCKERFILE"], "0")
        self.assertEqual(summary["PLATFORM"], "")
        self.assertEqual(summary["EXPERIMENT_DIR"], "/tmp/raman-fitting")
        self.assertEqual(summary["VERIFIERS_DIR"], "/tmp/raman-fitting/verifiers")
        self.assertEqual(
            summary["VERIFIER_COMMAND"],
            "pytest /bunsen/verifiers/test_outputs.py -v",
        )

    def test_native_fork_summary_flags_dockerfile_and_platform(self):
        summary = validate_tb_port_lib.build_summary(_native_fork_imagepath())
        self.assertEqual(summary["HAS_DOCKERFILE"], "1")
        self.assertEqual(summary["PLATFORM"], "linux/amd64")
        self.assertEqual(
            summary["VERIFIER_COMMAND"], "bash /bunsen/verifiers/run_tests.sh"
        )

    def test_summary_propagates_unsupported_verifier_failure(self):
        experiment = _simple_pytest_port()
        experiment["evaluation"]["criteria"][0]["run"] = "node /verify.js"
        with self.assertRaisesRegex(ValueError, "Unsupported verifier command"):
            validate_tb_port_lib.build_summary(experiment)


class CliEntrypointTests(unittest.TestCase):
    """Smoke-test the subcommands the bash driver actually invokes."""

    def _run_subcommand(self, argv: list[str], stdin_payload: str) -> str:
        captured_out = io.StringIO()
        original_stdin = validate_tb_port_lib.sys.stdin
        original_stdout = validate_tb_port_lib.sys.stdout
        try:
            validate_tb_port_lib.sys.stdin = io.StringIO(stdin_payload)
            validate_tb_port_lib.sys.stdout = captured_out
            rc = validate_tb_port_lib.main(argv)
        finally:
            validate_tb_port_lib.sys.stdin = original_stdin
            validate_tb_port_lib.sys.stdout = original_stdout
        self.assertEqual(rc, 0)
        return captured_out.getvalue()

    def test_summary_subcommand_emits_shell_quoted_pairs(self):
        wrapped = json.dumps({"kind": "experiment", "experiment": _native_fork_imagepath()})
        out = self._run_subcommand(["summary"], wrapped)
        # Output is sourced via `eval` in bash, so single-quoting must survive.
        self.assertIn("BASE_IMAGE=bunsen/headless\n", out)
        self.assertIn("HAS_DOCKERFILE=1\n", out)
        self.assertIn("PLATFORM=linux/amd64\n", out)
        self.assertIn(
            "VERIFIER_COMMAND='bash /bunsen/verifiers/run_tests.sh'\n",
            out,
        )

    def test_workspace_sources_subcommand_emits_tsv_for_image_source(self):
        wrapped = json.dumps({"kind": "experiment", "experiment": _native_fork_imagepath()})
        out = self._run_subcommand(["workspace-sources"], wrapped)
        self.assertEqual(out, "image\t/app/data\tdata\n")

    def test_rewrite_solution_subcommand_writes_dst(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "solution.sh"
            dst = Path(td) / "rewritten.sh"
            src.write_text("#!/bin/bash\necho /app/data\n")
            captured_out = io.StringIO()
            original_stdout = validate_tb_port_lib.sys.stdout
            try:
                validate_tb_port_lib.sys.stdout = captured_out
                rc = validate_tb_port_lib.main(
                    ["rewrite-solution", str(src), str(dst)]
                )
            finally:
                validate_tb_port_lib.sys.stdout = original_stdout
            self.assertEqual(rc, 0)
            self.assertIn("/workspace/data", dst.read_text())
            self.assertNotIn("#!/bin/bash", dst.read_text())


if __name__ == "__main__":
    unittest.main()
