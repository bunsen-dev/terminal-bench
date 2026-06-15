# Terminal Bench Port Process

How we port [Terminal Bench](https://github.com/laude-institute/terminal-bench) experiments into Bunsen, and the adaptations required to make them work within Bunsen's architecture.

## Prerequisites

Clone the Terminal Bench repository:

```bash
git clone https://github.com/laude-institute/terminal-bench.git ~/code/terminal-bench
```

The conversion script reads from `~/code/terminal-bench/original-tasks/`.

## Running the Conversion

```bash
# Convert all generated tasks (preserves native Bunsen forks)
python scripts/convert-terminal-bench.py

# Re-convert specific task(s) in place
python scripts/convert-terminal-bench.py fix-pandas-version
python scripts/convert-terminal-bench.py fix-pandas-version cartpole-rl-training
```

When specific tasks are given, only those experiments are regenerated. The rest are left untouched.

## Gold Solution Validation

After converting a task, validate the port by running the upstream Terminal Bench
`solution.sh` against the Bunsen workspace and verifier:

```bash
scripts/validate-tb-port.sh --tb-root /path/to/terminal-bench/original-tasks raman-fitting
```

This stages the Bunsen workspace, adapts the upstream solution from `/app` to
`/workspace`, runs it in Docker, and then runs the Bunsen verifier unchanged.
If this passes, the port has a strong end-to-end fidelity check: the original
reference solution still satisfies the Bunsen task contract.

The helper drives off `bn experiments show <task> --format json`, so it
respects whatever the experiment actually declares:

- **`workspace.sources`** — both repo-local `path` entries and image-backed
  `imagePath` entries are staged into the temp workspace before the upstream
  solution runs. Native forks like `train-fasttext` that seed `/workspace/data`
  from the built image are validated with the same fidelity as simple ports.
- **Verifier command** — the Tests Pass `script` criterion's `run` command is
  executed verbatim. Both `pytest /bunsen/verifiers/test_outputs.py …` and
  `bash /bunsen/verifiers/run_tests.sh` are supported. Other shapes fail fast
  with a precise error rather than silently running the wrong thing.

For tasks with a custom experiment Dockerfile, build or otherwise provide the
correct image first, then pass it explicitly:

```bash
scripts/validate-tb-port.sh --tb-root /path/to/terminal-bench/original-tasks --image <built-image> fix-pandas-version
```

Notes:

- Pass the upstream Terminal Bench `original-tasks/` directory explicitly with
  `--tb-root`.
- This is a one-off validation helper for port fidelity. It does not yet
  integrate with `bn run` as a first-class Terminal Bench workflow.
- The pure-Python pieces live in `scripts/validate_tb_port_lib.py` and are
  covered by `scripts/tests/test_validate_tb_port.py`.

## Files

All porting tooling and configuration lives in this repo. The converter
writes into `experiments/` by default; override with `TB_SUITE_DIR`.

| File | Purpose |
|------|---------|
| `scripts/convert-terminal-bench.py` | Main conversion script |
| `scripts/validate-tb-port.sh` | Run upstream `solution.sh` against a Bunsen port and verifier |
| `scripts/tb-overrides.yaml` | Per-task configuration for cases the auto-converter can't handle |
| `scripts/tb-native-tasks.yaml` | Native Bunsen forks and notes about why they were forked |
| `experiments/` | Generated output (one experiment per task) |
| `bunsen-suite.yaml` | Suite manifest (consumed via Bunsen's suite system) |

## How Terminal Bench Works

Each TB task consists of:

- **`task.yaml`** — instruction, category, difficulty, timeouts
- **`Dockerfile`** — environment setup (base image, packages, file copies)
- **`tests/test_outputs.py`** — pytest-based verification script
- **`tests/`** — may also contain companion files (data, scripts, source code)
- **`run-tests.sh`** — test runner (installs deps, runs pytest). Some tasks (SWE-bench) use this as the primary verification mechanism.
- **`task-deps/`**, **`resources/`** — additional workspace files

At runtime, TB mounts:
- The workspace at `/app` (read-write)
- Tests at `/tests/` (read-write, via `TEST_DIR` env var)

## How Bunsen Works (Key Differences)

In Bunsen's scorer container:

| Mount | Path | Permissions | Purpose |
|-------|------|-------------|---------|
| Workspace | `/workspace` | **read-write** | Extracted copy of agent's final workspace |
| Verifiers | `/bunsen/verifiers` | **read-only** | Experiment verification scripts |
| Scorer output | `/bunsen/scorer-output` | read-write | Score/summary files |
| Run context | `/bunsen/run` | read-only | Diff, logs, traces |

The critical difference: **TB's test directory is read-write, but Bunsen's verifiers are read-only.** This means any TB test that writes to its own directory needs adaptation.

## Path Adaptations

The converter applies these path translations:

| Terminal Bench | Bunsen | Notes |
|----------------|--------|-------|
| `/app` | `/workspace` | Workspace root |
| `/tests/` | `/bunsen/verifiers/` | In path strings within test files |
| `os.environ["TEST_DIR"]` | `os.path.dirname(os.path.abspath(__file__))` | Test directory self-reference |
| `shutil.copytree` to test dir | `sys.path.insert(0, "/workspace")` | See [Read-Only Verifiers](#read-only-verifiers-adaptation) |

Additionally:
- Canary comments (`BENCHMARK DATA SHOULD NEVER APPEAR...`) are stripped
- TB-specific packages (`tmux`, `asciinema`, `screen`) are removed

## Read-Only Verifiers Adaptation

### Background

Some TB task authors stored their project source code inside the `tests/` directory and used a Dockerfile `COPY` to place it in the workspace at build time:

```dockerfile
# TB Dockerfile — source code lives in tests/src/, copied to workspace at build
COPY tests/src/ /app/src/
```

This is a quirk of TB's conventions: `tests/` is the only directory reliably available to both the Docker build and the test runner. Since TB mounts `tests/` as read-write at runtime, the test file could copy the agent's (potentially modified) workspace code back into the tests directory to import it:

```python
# Original TB test — copies workspace code into tests dir for importing
# (works because TB's /tests/ is read-write)
shutil.copytree("/app/src", os.environ["TEST_DIR"] + "/src")
sys.path.append(os.environ["TEST_DIR"] + "/src")
from src.module import something
```

### Why it breaks in Bunsen

In Bunsen, `/bunsen/verifiers` is mounted **read-only** in the scorer container. The `copytree` call fails because it can't write to the verifiers mount. Additionally, the converter was blindly copying everything from `tests/` to `verifiers/` — including `tests/src/` which is workspace content, not a test companion file — which caused a secondary `FileExistsError` even before hitting the read-only constraint.

### How the converter handles it

The converter applies two fixes:

1. **Test file adaptation:** Detects the `copytree`-to-test-dir pattern and replaces it with a direct Python import path pointing at the workspace:

   ```python
   # Bunsen adaptation — no file copying needed, just tell Python where to look
   sys.path.insert(0, "/workspace")
   from src.module import something
   ```

2. **Skipping workspace content in verifiers:** When copying files from `tests/` to `verifiers/`, the converter checks the Dockerfile for `COPY tests/<dir>/` commands. Any directory that the Dockerfile copies into the workspace is workspace content and is skipped — only actual test companion files (scripts, data, expected outputs) are copied to verifiers.

The source code directory (`tests/src/`) still exists in the experiment directory for the Dockerfile build context — it's just no longer duplicated into `verifiers/`.

### Affected experiments

Currently only `fix-pandas-version` uses this pattern. It was the only TB experiment with `shutil.copytree` in its test file.

## Three-Tier Task Classification

The overrides file (`scripts/tb-overrides.yaml`) classifies tasks into three tiers:

### Tier 1: Simple Tasks

Use `environment.packages` in experiment.yaml. No custom Dockerfile needed.

```yaml
# scripts/tb-overrides.yaml
openssl-selfsigned-cert:
  extra_apt: [openssl]
```

Generated structure:
```
hello-world/
  experiment.yaml      # includes environment.packages
  verifiers/
    test_outputs.py
```

### Tier 2: Workspace Setup Tasks

Use `environment.packages` + `environment.workspace_setup` shell commands. For tasks needing git repos, config scripts, or complex initialization.

```yaml
# scripts/tb-overrides.yaml
fix-git:
  extra_apt: [git]
  extra_workspace_files:
    - src: "setup.sh"
      dst: "setup.sh"
    - src: "resources"
      dst: "resources"
  environment:
    workspace_setup: |
      cd /workspace && bash /workspace/setup.sh
  workspace_setup_timeout: 120
```

### Tier 3: Custom Dockerfile

For tasks with non-standard base images, heavy builds, or complex environment setup. Set `custom_dockerfile: true` in overrides.

```yaml
# scripts/tb-overrides.yaml
fix-pandas-version:
  custom_dockerfile: true
  test_pip: [packaging==21.3]
```

If the Dockerfile produces immutable starter files that must be present in `/workspace` at runtime, declare explicit image-backed workspace sources:

```yaml
path-tracing:
  custom_dockerfile: true
  workspace:
    sources:
      - image_path: /app/image.ppm
        target: image.ppm
```

Generated structure:
```
fix-pandas-version/
  experiment.yaml
  Dockerfile           # Adapted from TB's Dockerfile
  verifiers/
    test_outputs.py
```

**Dockerfile adaptations:**
- Base images mapped from TB registry images to standard Docker images (e.g., `ghcr.io/laude-institute/t-bench/python-3-13:20250620` to `python:3.13-slim-bookworm`)
- `pytest` + test dependencies injected if not present
- Per-task `extra_apt` packages injected into generated Dockerfiles when the mapped base image is missing TB-provided tooling
- Non-Python base images get `python3-pip` when needed; `--break-system-packages` is only added for base images explicitly opted into that behavior in the converter (currently `ubuntu:24.04`)
- `/app` build semantics preserved when the upstream task relies on them
- Dockerfile build steps can stay on TB-native `/app`; tasks that declare `workspace.sources` import those exact image-backed files into Bunsen's runtime `/workspace`
- Verifiers should treat `/workspace-source` as the immutable seeded-input path and `/workspace` as the mutable final workspace
- If an expensive artifact is immutable and the verifier does not care whether the agent produced it, prebuild it in the image and seed it into `/workspace` with `workspace.sources` instead of paying that cost during every run

### SWE-bench Tasks (Tier 3 Special Case)

SWE-bench tasks use `create_empty_workspace: true` + `environment.workspace_setup` to clone repositories at setup time, and shell verifier scripts (from `run-tests.sh`) instead of pytest.

```yaml
swe-bench-astropy-1:
  custom_dockerfile: true
  create_empty_workspace: true
  environment:
    workspace_setup: |
      git clone https://github.com/astropy/astropy.git /workspace/astropy
      cd /workspace/astropy && git reset --hard d16bfe05...
  workspace_setup_timeout: 300
```

## Overrides Reference

All fields in `scripts/tb-overrides.yaml`:

| Field | Type | Description |
|-------|------|-------------|
| `skip` | bool | Skip this task entirely |
| `skip_reason` | string | Why it's skipped |
| `dir_name` | string | TB directory name if different from task ID |
| `custom_dockerfile` | bool | Generate adapted Dockerfile (Tier 3) |
| `create_empty_workspace` | bool | Start with empty workspace (for git clone tasks) |
| `environment` | object | Experiment-shaped environment overrides (for example `workspace_setup`) |
| `workspace_setup_timeout` | int | Timeout for setup commands (seconds) |
| `extra_apt` | list | Additional apt packages |
| `extra_pip` | list | Additional pip packages |
| `test_pip` | list | Override auto-detected test pip deps |
| `workspace` | object | Experiment-shaped workspace overrides (for example `sources`) |
| `timeout` | int | Override agent timeout (seconds) |
| `criterion_timeout` | int | Override `Tests Pass` criterion timeout (seconds) |
| `verifier_subprocess_timeout` | int | Override `timeout=...` values inside copied pytest verifiers |
| `description` | string | Override auto-generated description |
| `platforms` | list[str] | Restrict supported run platforms for the generated experiment |
| `extra_workspace_files` | list | Files from task root to copy to workspace/ |
| `variant_of` | string | This is a variant of another task |
| `instruction_suffix` | string | Text to append to instruction |
| `score_in_agent_container` | bool | Run scorers in agent's container (for package/service tasks) |
## Skipped Tasks (5 of 71)

| Task | Reason |
|------|--------|
| `super-benchmark-upet` | Not found in TB repository |
| `vim-terminal-task` | Not found in TB repository |
| `security-vulhub-minio` | Requires separate MinIO container |
| `simple-sheets-put` | Requires PostgreSQL + API server |
| `simple-web-scraper` | Requires web server container |

## Porting Policy

Use exactly two strategies for Terminal Bench:

1. Apply light, general transformations across the suite when the same adaptation works broadly.
2. If a task does not translate cleanly, replace it with a native Bunsen implementation instead of adding task-specific converter hacks.

For native forks, keep the benchmark surface narrow:

- Prebuild anything expensive that the verifier does not require the agent to produce.
- Seed those immutable artifacts with image-backed `workspace.sources`.
- Only leave expensive work in-run when that expensive work is itself the benchmark.

This keeps the converter mechanical and easy to maintain. Native forks live in `experiments/<task-id>/` and are listed in `scripts/tb-native-tasks.yaml` with notes about why they were forked so full regenerations preserve them.

## Adding a New Task

1. Ensure the task exists in `~/code/terminal-bench/original-tasks/<task-id>/`
2. Add its ID to the `CORE_TASKS` list in `convert-terminal-bench.py`
3. If needed, add overrides in `scripts/tb-overrides.yaml`
4. If the task needs semantics-aware, experiment-specific translation logic, stop and create a native Bunsen implementation instead. Add it to `scripts/tb-native-tasks.yaml` with a reason/note.
5. Run `python scripts/convert-terminal-bench.py <task-id>`
6. Verify with `bn info terminal-bench/<task-id>` and `bn run terminal-bench/<task-id> <agent>`

## Troubleshooting

**Scorer fails with read-only filesystem errors:** The verifier test is trying to write to `/bunsen/verifiers/`. This means a TB adaptation is missing — the test needs to be modified to work with read-only verifiers (most commonly, replace `copytree` with `sys.path` manipulation). Fix the pattern in `fix_verifier_paths()` and re-convert.

**Test can't import workspace code:** The test likely needs `sys.path.insert(0, "/workspace")` to import modules from the agent's workspace. Several TB experiments already use `sys.path.append("/workspace")` as their original pattern.

**`verifiers/` contains workspace source code:** Check if the Dockerfile has `COPY tests/<dir>/` commands. If a `tests/` subdirectory is workspace content, it should be excluded from verifiers. Add the appropriate detection logic to `copy_test_file()`.
