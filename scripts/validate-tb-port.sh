#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/validate-tb-port.sh [options] <task>

Validate a Terminal Bench port (mechanically converted or natively forked) by
running the upstream solution.sh against the Bunsen-initialized workspace and
verifier for the matching task.

Options:
  --tb-root <path>  Path to Terminal Bench original-tasks directory. Required.
  --image <image>   Docker image to use. Required for tasks with a custom
                    experiment Dockerfile.
  --keep-tmp        Keep the staged temp directory instead of deleting it.
  -h, --help        Show this help text.

Examples:
  scripts/validate-tb-port.sh --tb-root /path/to/terminal-bench/original-tasks raman-fitting
  scripts/validate-tb-port.sh --tb-root /path/to/terminal-bench/original-tasks --image my-task-image fix-pandas-version
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

task=""
tb_root=""
image_override=""
keep_tmp=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tb-root)
      [[ $# -ge 2 ]] || die "--tb-root requires a value"
      tb_root="$2"
      shift 2
      ;;
    --image)
      [[ $# -ge 2 ]] || die "--image requires a value"
      image_override="$2"
      shift 2
      ;;
    --keep-tmp)
      keep_tmp=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      die "Unknown option: $1"
      ;;
    *)
      [[ -z "$task" ]] || die "Only one task may be provided"
      task="$1"
      shift
      ;;
  esac
done

[[ -n "$task" ]] || {
  usage >&2
  exit 1
}
[[ -n "$tb_root" ]] || die "--tb-root is required"

command -v docker >/dev/null 2>&1 || die "docker is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"
command -v bn >/dev/null 2>&1 || die "bn is required"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT_DIR/scripts/validate_tb_port_lib.py"
[[ -f "$HELPER" ]] || die "Helper script not found: $HELPER"

TB_TASK_DIR="$tb_root/$task"
SOLUTION_PATH="$TB_TASK_DIR/solution.sh"

[[ -d "$TB_TASK_DIR" ]] || die "Terminal Bench task not found: $TB_TASK_DIR"
[[ -f "$SOLUTION_PATH" ]] || die "Terminal Bench solution not found: $SOLUTION_PATH"

# Pull experiment metadata once and reuse it. `bn experiments show --format json`
# emits the parsed v1 config plus pre-resolved workspaceSources, dir, and
# verifiersPath so we never have to second-guess filesystem layout.
EXPERIMENT_JSON="$(bn experiments show "$task" --format json)" \
  || die "bn experiments show $task failed — is the experiment registered with Bunsen?"

SUMMARY_OUTPUT="$(printf '%s' "$EXPERIMENT_JSON" | python3 "$HELPER" summary)" \
  || die "Failed to summarise experiment metadata for $task"

# Helper emits shell-quoted KEY=VALUE lines: safe to source.
eval "$SUMMARY_OUTPUT"

[[ -n "$EXPERIMENT_DIR" ]] || die "bn experiments show did not report an experiment dir"
[[ -d "$EXPERIMENT_DIR" ]] || die "Reported experiment dir does not exist: $EXPERIMENT_DIR"
[[ -n "$VERIFIERS_DIR" ]] || die "Experiment $task has no verifiers/ directory — cannot validate"
[[ -d "$VERIFIERS_DIR" ]] || die "Verifiers dir does not exist: $VERIFIERS_DIR"

if [[ -n "$image_override" ]]; then
  IMAGE="$image_override"
elif [[ "$HAS_DOCKERFILE" == "1" ]]; then
  die "Experiment has a custom Dockerfile. Re-run with --image <built-image>."
else
  [[ -n "$BASE_IMAGE" ]] || die "Could not determine base image for $task"
  IMAGE="$BASE_IMAGE"
fi

EXPERIMENT_PLATFORM="$PLATFORM"

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

docker_run() {
  if [[ -n "$EXPERIMENT_PLATFORM" ]]; then
    docker run --rm --platform "$EXPERIMENT_PLATFORM" "$@"
  else
    docker run --rm "$@"
  fi
}

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/validate-tb-port.${task}.XXXXXX")"
cleanup() {
  if [[ "$keep_tmp" -eq 0 ]]; then
    rm -rf "$TMP_DIR" 2>/dev/null || true
  else
    echo "Kept temp dir: $TMP_DIR"
  fi
}
trap cleanup EXIT

WORKSPACE_SOURCE_DIR="$TMP_DIR/workspace-source"
WORKSPACE_DIR="$TMP_DIR/workspace"
mkdir -p "$WORKSPACE_DIR" "$WORKSPACE_SOURCE_DIR"

copy_host_source() {
  local source_path="$1"
  local target_rel="$2"
  local destination_root="$WORKSPACE_SOURCE_DIR"

  [[ -e "$source_path" ]] || die "Workspace source path does not exist: $source_path"

  if [[ -d "$source_path" ]]; then
    if [[ -n "$target_rel" ]]; then
      mkdir -p "$destination_root/$target_rel"
      cp -a "$source_path"/. "$destination_root/$target_rel/"
    else
      cp -a "$source_path"/. "$destination_root/"
    fi
    return
  fi

  local dest_rel
  if [[ -n "$target_rel" ]]; then
    dest_rel="$target_rel"
  else
    dest_rel="$(basename "$source_path")"
  fi

  mkdir -p "$(dirname "$destination_root/$dest_rel")"
  cp -a "$source_path" "$destination_root/$dest_rel"
}

copy_image_source() {
  local source_path="$1"
  local target_rel="$2"

  docker_run \
    -e HOST_UID="$HOST_UID" \
    -e HOST_GID="$HOST_GID" \
    -v "$WORKSPACE_SOURCE_DIR":/staging \
    "$IMAGE" \
    bash -lc '
      set -euo pipefail
      source_path="$1"
      target_rel="$2"
      destination_root="/staging"

      if [ ! -e "$source_path" ]; then
        echo "Workspace source path does not exist in image: $source_path" >&2
        exit 1
      fi

      if [ -d "$source_path" ]; then
        if [ -n "$target_rel" ]; then
          mkdir -p "$destination_root/$target_rel"
          cp -a --no-preserve=ownership "$source_path"/. "$destination_root/$target_rel/"
        else
          cp -a --no-preserve=ownership "$source_path"/. "$destination_root/"
        fi
        chown -R "$HOST_UID:$HOST_GID" /staging
        exit 0
      fi

      if [ -n "$target_rel" ]; then
        dest_rel="$target_rel"
      else
        dest_rel="$(basename "$source_path")"
      fi

      mkdir -p "$(dirname "$destination_root/$dest_rel")"
      cp -a --no-preserve=ownership "$source_path" "$destination_root/$dest_rel"
      chown -R "$HOST_UID:$HOST_GID" /staging
    ' -- "$source_path" "$target_rel"
}

while IFS=$'\t' read -r source_type source_path target_rel; do
  [[ -n "$source_type" ]] || continue
  case "$source_type" in
    path)
      copy_host_source "$source_path" "$target_rel"
      ;;
    image)
      copy_image_source "$source_path" "$target_rel"
      ;;
    *)
      die "Unknown workspace source type: $source_type"
      ;;
  esac
done < <(printf '%s' "$EXPERIMENT_JSON" | python3 "$HELPER" workspace-sources)

cp -a "$WORKSPACE_SOURCE_DIR"/. "$WORKSPACE_DIR/" 2>/dev/null || true

python3 "$HELPER" rewrite-solution "$SOLUTION_PATH" "$TMP_DIR/workspace/solution.sh"
chmod +x "$TMP_DIR/workspace/solution.sh"

echo "Task: $task"
echo "Image: $IMAGE"
if [[ -n "$EXPERIMENT_PLATFORM" ]]; then
  echo "Platform: $EXPERIMENT_PLATFORM"
fi
echo "Workspace: $WORKSPACE_DIR"
echo "Workspace Source: $WORKSPACE_SOURCE_DIR"
echo "Verifiers: $VERIFIERS_DIR"
echo "Verifier: $VERIFIER_COMMAND"
if [[ "$keep_tmp" -eq 1 ]]; then
  echo "Temp dir: $TMP_DIR"
fi
echo
echo "Running upstream solution against Bunsen verifier..."

docker_run \
  -e HOST_UID="$HOST_UID" \
  -e HOST_GID="$HOST_GID" \
  -e VERIFIER_COMMAND="$VERIFIER_COMMAND" \
  -v "$TMP_DIR/workspace":/workspace \
  -v "$TMP_DIR/workspace-source":/workspace-source:ro \
  -v "$VERIFIERS_DIR":/bunsen/verifiers:ro \
  -w /workspace \
  "$IMAGE" \
  bash -lc '
    set -euo pipefail
    status=0
    case "$VERIFIER_COMMAND" in
      pytest\ *)
        # Mechanically-converted TB ports rely on the image default Python and
        # do not pre-install pytest. The fallback is for older pips (<23.0)
        # that do not understand --break-system-packages and do not need it.
        if ! python3 -c "import pytest" >/dev/null 2>&1; then
          python3 -m pip install pytest >/dev/null 2>&1 \
            || python3 -m pip install --break-system-packages pytest \
            || status=$?
        fi
        ;;
    esac
    if [[ "$status" -eq 0 ]]; then
      bash /workspace/solution.sh >/workspace/gold-solution.log 2>&1 || {
        cat /workspace/gold-solution.log
        status=$?
      }
    fi
    if [[ "$status" -eq 0 && -f /workspace/results.json ]]; then
      cat /workspace/results.json
    fi
    if [[ "$status" -eq 0 ]]; then
      bash -lc "$VERIFIER_COMMAND" || status=$?
    fi
    chown -R "$HOST_UID:$HOST_GID" /workspace || true
    exit "$status"
  '
