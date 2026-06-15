import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "convert-terminal-bench.py"
SPEC = importlib.util.spec_from_file_location("convert_terminal_bench", MODULE_PATH)
convert_terminal_bench = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(convert_terminal_bench)


class BreakSystemPackagesTests(unittest.TestCase):
    def test_only_opted_in_base_images_keep_break_system_packages(self):
        self.assertTrue(
            convert_terminal_bench.should_use_break_system_packages("ubuntu:24.04")
        )

    def test_non_opted_in_base_images_do_not_assume_flag_support(self):
        self.assertFalse(
            convert_terminal_bench.should_use_break_system_packages(
                "debian:bullseye-slim"
            )
        )
        self.assertFalse(
            convert_terminal_bench.should_use_break_system_packages(
                "debian:bookworm-slim"
            )
        )
        self.assertFalse(
            convert_terminal_bench.should_use_break_system_packages(
                "localstack/localstack:4.3"
            )
        )

    def test_adapt_dockerfile_skips_break_system_packages_for_bullseye(self):
        dockerfile_data = {
            "apt": [],
            "pip": [],
            "base_image": "debian:bullseye-slim",
            "copies": [],
            "workdir": "/app",
            "content": "FROM debian:bullseye-slim\nWORKDIR /app\n",
        }

        adapted = convert_terminal_bench.adapt_dockerfile(
            task_id="qemu-startup",
            task_dir=Path("/tmp"),
            dockerfile_data=dockerfile_data,
            test_deps=[],
            overrides={},
        )

        self.assertIn(
            "RUN apt-get update && apt-get install -y python3 python3-pip",
            adapted,
        )
        self.assertIn("RUN pip3 install pytest", adapted)
        self.assertNotIn("--break-system-packages", adapted)

    def test_adapt_dockerfile_keeps_break_system_packages_for_ubuntu_24(self):
        dockerfile_data = {
            "apt": [],
            "pip": [],
            "base_image": "ubuntu:24.04",
            "copies": [],
            "workdir": "/app",
            "content": "FROM ubuntu:24.04\nWORKDIR /app\n",
        }

        adapted = convert_terminal_bench.adapt_dockerfile(
            task_id="prove-plus-comm",
            task_dir=Path("/tmp"),
            dockerfile_data=dockerfile_data,
            test_deps=[],
            overrides={},
        )

        self.assertIn("RUN pip3 install --break-system-packages pytest", adapted)

    def test_adapt_dockerfile_bootstraps_pip_before_injected_pytest_install(self):
        dockerfile_data = {
            "apt": [],
            "pip": [],
            "base_image": "ubuntu:24.04",
            "copies": [],
            "workdir": "/app",
            "content": (
                "FROM ubuntu:24.04\n"
                "WORKDIR /app\n"
                "RUN apt update -y\n"
                "RUN apt install -y curl\n"
                "RUN apt install -y python3-pip\n"
            ),
        }

        adapted = convert_terminal_bench.adapt_dockerfile(
            task_id="chess-best-move",
            task_dir=Path("/tmp"),
            dockerfile_data=dockerfile_data,
            test_deps=[],
            overrides={},
        )

        bootstrap = (
            "RUN apt-get update && apt-get install -y python3 python3-pip "
            "&& rm -rf /var/lib/apt/lists/*"
        )
        pytest_install = "RUN pip3 install --break-system-packages pytest"

        self.assertIn(bootstrap, adapted)
        self.assertIn(pytest_install, adapted)
        self.assertLess(adapted.index(bootstrap), adapted.index(pytest_install))

    def test_adapt_dockerfile_does_not_duplicate_bootstrap_after_multiline_apt(self):
        dockerfile_data = {
            "apt": [],
            "pip": [],
            "base_image": "ubuntu:24.04",
            "copies": [],
            "workdir": "/app",
            "content": (
                "FROM ubuntu:24.04\n"
                "RUN apt-get update && apt-get install -y \\\n"
                "    curl \\\n"
                "    python3 \\\n"
                "    python3-pip && \\\n"
                "    rm -rf /var/lib/apt/lists/*\n"
                "WORKDIR /app\n"
            ),
        }

        adapted = convert_terminal_bench.adapt_dockerfile(
            task_id="extract-safely",
            task_dir=Path("/tmp"),
            dockerfile_data=dockerfile_data,
            test_deps=[],
            overrides={},
        )

        bootstrap = (
            "RUN apt-get update && apt-get install -y python3 python3-pip "
            "&& rm -rf /var/lib/apt/lists/*"
        )
        self.assertEqual(adapted.count(bootstrap), 0)

    def test_adapt_dockerfile_reduces_aggressive_git_gc(self):
        dockerfile_data = {
            "apt": [],
            "pip": [],
            "base_image": "ubuntu:24.04",
            "copies": [],
            "workdir": "/app",
            "content": (
                "FROM ubuntu:24.04\n"
                "RUN git clone https://example.com/repo /app/repo && \\\n"
                "    cd /app/repo && \\\n"
                "    git gc --prune=now --aggressive\n"
            ),
        }

        adapted = convert_terminal_bench.adapt_dockerfile(
            task_id="example",
            task_dir=Path("/tmp"),
            dockerfile_data=dockerfile_data,
            test_deps=[],
            overrides={},
        )

        self.assertIn("git gc --prune=now", adapted)
        self.assertNotIn("git gc --prune=now --aggressive", adapted)

    def test_generate_experiment_yaml_applies_timeout_override(self):
        experiment = convert_terminal_bench.generate_experiment_yaml(
            task_id="qemu-alpine-ssh",
            task_data={
                "instruction": "Boot the image and start ssh.",
                "category": "system-administration",
                "difficulty": "medium",
                "max_agent_timeout_sec": 900,
            },
            dockerfile_data={},
            test_deps=[],
            overrides={
                "custom_dockerfile": True,
                "timeout": 1800,
                "score_in_agent_container": True,
            },
            has_workspace_dir=False,
            verifier_run="pytest /bunsen/verifiers/test_outputs.py -v",
        )

        self.assertEqual(experiment["run"], {"timeout": "30m"})
        self.assertEqual(experiment["evaluation"]["container"], "agent")

    def test_generate_experiment_yaml_includes_workspace_sources_override(self):
        experiment = convert_terminal_bench.generate_experiment_yaml(
            task_id="chess-best-move",
            task_data={
                "instruction": "The file chess_board.png has an image of a chess board.",
                "category": "games",
                "difficulty": "medium",
            },
            dockerfile_data={},
            test_deps=[],
            overrides={
                "custom_dockerfile": True,
                "workspace": {
                    "sources": [
                        {
                            "image_path": "/app/chess_board.png",
                            "target": "chess_board.png",
                        }
                    ]
                },
            },
            has_workspace_dir=False,
            verifier_run="pytest /bunsen/verifiers/test_outputs.py -v",
        )

        # Legacy `image_path` overrides are normalized to v1 `imagePath`.
        self.assertEqual(
            experiment["workspace"],
            {
                "sources": [
                    {
                        "imagePath": "/app/chess_board.png",
                        "target": "chess_board.png",
                    }
                ]
            },
        )

    def test_generate_experiment_yaml_includes_platforms_override(self):
        experiment = convert_terminal_bench.generate_experiment_yaml(
            task_id="eval-mteb",
            task_data={
                "instruction": "Evaluate a model.",
                "category": "data-science",
                "difficulty": "medium",
            },
            dockerfile_data={},
            test_deps=[],
            overrides={
                "custom_dockerfile": True,
                "platforms": ["linux/amd64"],
            },
            has_workspace_dir=False,
            verifier_run="pytest /bunsen/verifiers/test_outputs.py -v",
        )

        self.assertEqual(experiment["environment"]["platforms"], ["linux/amd64"])

    def test_generate_experiment_yaml_includes_extract_safely_workspace_sources(self):
        experiment = convert_terminal_bench.generate_experiment_yaml(
            task_id="extract-safely",
            task_data={
                "instruction": "Extract the solution from /app/archive.tar.",
                "category": "security",
                "difficulty": "easy",
            },
            dockerfile_data={},
            test_deps=[],
            overrides={
                "custom_dockerfile": True,
                "workspace": {
                    "sources": [
                        {
                            "image_path": "/app/archive.tar",
                            "target": "archive.tar",
                        },
                        {
                            "image_path": "/app/system_logs.dat",
                            "target": "system_logs.dat",
                        },
                    ]
                },
            },
            has_workspace_dir=False,
            verifier_run="pytest /bunsen/verifiers/test_outputs.py -v",
        )

        self.assertEqual(
            experiment["workspace"],
            {
                "sources": [
                    {
                        "imagePath": "/app/archive.tar",
                        "target": "archive.tar",
                    },
                    {
                        "imagePath": "/app/system_logs.dat",
                        "target": "system_logs.dat",
                    },
                ]
            },
        )


class VerifierTimeoutRewriteTests(unittest.TestCase):
    def test_rewrite_verifier_subprocess_timeouts_uses_override(self):
        verifier = (
            "run_result = subprocess.run(\n"
            "    [\"/workspace/a.out\"],\n"
            "    capture_output=True,\n"
            "    timeout=90,\n"
            ")\n"
        )

        rewritten = convert_terminal_bench.rewrite_verifier_subprocess_timeouts(
            verifier,
            {"verifier_subprocess_timeout": 180},
        )

        self.assertIn("timeout=180", rewritten)
        self.assertNotIn("timeout=90", rewritten)

    def test_rewrite_verifier_subprocess_timeouts_no_override_leaves_text(self):
        verifier = "subprocess.run([\"cmd\"], timeout=90)\n"

        rewritten = convert_terminal_bench.rewrite_verifier_subprocess_timeouts(
            verifier,
            {},
        )

        self.assertEqual(rewritten, verifier)


if __name__ == "__main__":
    unittest.main()
