import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import uuid
from pathlib import Path

import pytest

TEST_ID = str(uuid.uuid4())
TEST_ROOT = f"/var/tmp/c4_test_{TEST_ID}"
TEST_INPUT_DIR = os.path.join(TEST_ROOT, "input")
TEST_OUTPUT_ROOT = os.path.join(TEST_ROOT, "output-root")
TEST_OUTPUT_DIR = os.path.join(TEST_OUTPUT_ROOT, "output")
EXEC_ROOT = os.path.join(TEST_ROOT, "exec-root")
COMPRESS_RUNTIME_ROOT = os.path.join(TEST_ROOT, "runtime-compress")
DECOMPRESS_RUNTIME_ROOT = os.path.join(TEST_ROOT, "runtime-decompress")
MAX_SIZE_PER_FILE = 15 * 1024 * 1024  # 15MB in bytes (not GB!)
MAX_FILES_PER_FOLDER = 30
COMPRESS_SCRIPT = "/workspace/compress.py"
DECOMPRESS_SCRIPT = "/workspace/decompress.py"
EXPECTED_HASHES_PATH = Path("/bunsen/verifiers/files_hashes.json")
HIDDEN_INPUT_ARCHIVE_PATH = Path("/bunsen/verifiers/hidden_input.tar.gz")
HIDDEN_INPUT_ARCHIVE_SHA256_PATH = Path("/bunsen/verifiers/hidden_input.sha256")
SANDBOX_UID = 12345
SANDBOX_GID = 12345
WORKSPACE_COPY_EXCLUDES = {"c4_sample", ".seed"}


def _chown_tree(root, uid, gid):
    os.chown(root, uid, gid)
    for current_root, dirnames, filenames in os.walk(root):
        os.chown(current_root, uid, gid)
        for dirname in dirnames:
            os.chown(os.path.join(current_root, dirname), uid, gid)
        for filename in filenames:
            os.chown(os.path.join(current_root, filename), uid, gid)


def _prepare_runtime_root(runtime_root):
    shutil.rmtree(runtime_root, ignore_errors=True)
    os.makedirs(runtime_root, exist_ok=True)
    for name in ("home", "tmp", "uv-cache", "xdg-cache", "pycache"):
        os.makedirs(os.path.join(runtime_root, name), exist_ok=True)
    _chown_tree(runtime_root, SANDBOX_UID, SANDBOX_GID)


def _strip_write_bits_tree(root):
    for current_root, dirnames, filenames in os.walk(root):
        current_mode = os.stat(current_root).st_mode
        os.chmod(current_root, current_mode & ~0o222)
        for dirname in dirnames:
            path = os.path.join(current_root, dirname)
            mode = os.stat(path).st_mode
            os.chmod(path, mode & ~0o222)
        for filename in filenames:
            path = os.path.join(current_root, filename)
            mode = os.stat(path).st_mode
            os.chmod(path, mode & ~0o222)


def _prepare_exec_root():
    shutil.rmtree(EXEC_ROOT, ignore_errors=True)
    os.makedirs(EXEC_ROOT, exist_ok=True)
    for entry in os.listdir("/workspace"):
        if entry in WORKSPACE_COPY_EXCLUDES:
            continue
        source = os.path.join("/workspace", entry)
        target = os.path.join(EXEC_ROOT, entry)
        if os.path.isdir(source) and not os.path.islink(source):
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target, follow_symlinks=False)
    _strip_write_bits_tree(EXEC_ROOT)


def run_as_sandbox_user(command, runtime_root, timeout, cwd):
    _prepare_runtime_root(runtime_root)
    env = os.environ.copy()
    env.update(
        {
            "HOME": os.path.join(runtime_root, "home"),
            "TMPDIR": os.path.join(runtime_root, "tmp"),
            "UV_CACHE_DIR": os.path.join(runtime_root, "uv-cache"),
            "XDG_CACHE_HOME": os.path.join(runtime_root, "xdg-cache"),
            "PYTHONPYCACHEPREFIX": os.path.join(runtime_root, "pycache"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        capture_output=True,
        text=True,
        env=env,
        user=SANDBOX_UID,
        group=SANDBOX_GID,
    )


def _list_paths_owned_by_sandbox_user():
    result = subprocess.run(
        [
            "find",
            "/",
            "-path",
            "/proc",
            "-prune",
            "-o",
            "-path",
            "/sys",
            "-prune",
            "-o",
            "-path",
            "/dev",
            "-prune",
            "-o",
            "-path",
            "/run",
            "-prune",
            "-o",
            "-uid",
            str(SANDBOX_UID),
            "-print",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def assert_no_persistent_writes_outside_output_dir(output_dir, baseline_owned_paths):
    owned_paths = _list_paths_owned_by_sandbox_user()
    disallowed = []
    for owned_path in owned_paths:
        if owned_path in baseline_owned_paths:
            continue
        if owned_path == TEST_OUTPUT_ROOT:
            continue
        if owned_path == output_dir or owned_path.startswith(f"{output_dir}/"):
            continue
        disallowed.append(owned_path)

    assert not disallowed, (
        "compress.py created persistent files outside the output directory: "
        + ", ".join(sorted(disallowed)[:25])
    )


def assert_only_output_dir_was_created(output_root, output_dir):
    entries = sorted(os.listdir(output_root))
    expected = [os.path.basename(output_dir)]
    assert entries == expected, (
        f"Files or folders were created outside the output directory. "
        f"Expected only {expected} under {output_root}, found {entries}"
    )


def _compute_file_sha256(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as file_handle:
        while True:
            chunk = file_handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


@pytest.fixture(scope="session")
def generate_test_data():
    """Extract verifier-only hidden test data and validate it matches expected hashes."""
    print("Extracting hidden test data.")

    # Clean up any existing test directories
    if os.path.exists(TEST_ROOT):
        shutil.rmtree(TEST_ROOT)
    expected_hashes = json.loads(EXPECTED_HASHES_PATH.read_text())
    assert HIDDEN_INPUT_ARCHIVE_PATH.exists(), f"Missing hidden verifier archive: {HIDDEN_INPUT_ARCHIVE_PATH}"
    assert HIDDEN_INPUT_ARCHIVE_SHA256_PATH.exists(), (
        f"Missing hidden verifier checksum file: {HIDDEN_INPUT_ARCHIVE_SHA256_PATH}"
    )

    expected_archive_sha256 = HIDDEN_INPUT_ARCHIVE_SHA256_PATH.read_text().strip()
    actual_archive_sha256 = _compute_file_sha256(HIDDEN_INPUT_ARCHIVE_PATH)
    assert actual_archive_sha256 == expected_archive_sha256, (
        "Hidden verifier archive checksum mismatch"
    )

    os.makedirs(TEST_ROOT, exist_ok=True)
    with tarfile.open(HIDDEN_INPUT_ARCHIVE_PATH, "r:gz") as archive:
        archive.extractall(TEST_ROOT, filter="data")

    assert os.path.isdir(TEST_INPUT_DIR), f"Expected extracted hidden input at {TEST_INPUT_DIR}"
    extracted_names = sorted(path.name for path in Path(TEST_INPUT_DIR).iterdir())
    expected_names = sorted(expected_hashes.keys())
    assert extracted_names == expected_names, "Extracted verifier input file list does not match expected hidden shard"

    print(f"Prepared {len(expected_hashes)} hidden test files")
    return expected_hashes


def test_compress_decompress_workflow(generate_test_data):
    """Test the full compress -> decompress workflow is successful."""
    original_hashes = generate_test_data

    # Part 1: Test compression
    # Clean up output directory
    if os.path.exists(TEST_OUTPUT_ROOT):
        shutil.rmtree(TEST_OUTPUT_ROOT)
    os.makedirs(TEST_OUTPUT_ROOT, exist_ok=True)
    _chown_tree(TEST_OUTPUT_ROOT, SANDBOX_UID, SANDBOX_GID)

    # Install dependencies first to avoid snapshot contamination
    print("Installing dependencies with uv sync...")
    sync_result = subprocess.run(
        ["uv", "sync"],
        cwd="/workspace",
        capture_output=True,
        text=True,
    )
    if sync_result.returncode != 0:
        print(f"uv sync failed: {sync_result.stderr}")
        assert False, f"uv sync failed: {sync_result.stderr}"
    _prepare_exec_root()
    baseline_owned_paths = set(_list_paths_owned_by_sandbox_user())

    # Run the compress script
    try:
        print(
            f"Running compress script: {COMPRESS_SCRIPT} "
            f"{TEST_INPUT_DIR} {TEST_OUTPUT_DIR}"
        )
        result = run_as_sandbox_user(
            [
                "uv",
                "run",
                "--no-sync",
                "python",
                os.path.join(EXEC_ROOT, "compress.py"),
                TEST_INPUT_DIR,
                TEST_OUTPUT_DIR,
            ],
            runtime_root=COMPRESS_RUNTIME_ROOT,
            timeout=600,
            cwd=EXEC_ROOT,
        )
        if result.returncode != 0:
            print(f"Compress script failed with return code {result.returncode}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            assert False, f"Compress script failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        assert False, "The compress script timed out!"

    # Verify output directory exists
    assert os.path.exists(TEST_OUTPUT_DIR), "Output directory was not created"
    shutil.rmtree(COMPRESS_RUNTIME_ROOT, ignore_errors=True)
    assert_no_persistent_writes_outside_output_dir(TEST_OUTPUT_DIR, baseline_owned_paths)
    assert_only_output_dir_was_created(TEST_OUTPUT_ROOT, TEST_OUTPUT_DIR)

    # Check that the maximum file size in TEST_OUTPUT_DIR is MAX_SIZE_PER_FILE
    for root, dirs, files in os.walk(TEST_OUTPUT_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            file_size = os.path.getsize(file_path)
            assert file_size <= MAX_SIZE_PER_FILE, (
                f"File {file_path} is {file_size} bytes, exceeds {MAX_SIZE_PER_FILE}"
            )

        # Check that the number of files+folders in each directory is less than
        # MAX_FILES_PER_FOLDER
        total_items = len(files) + len(dirs)
        assert total_items <= MAX_FILES_PER_FOLDER, (
            f"Directory {root} has {total_items} items, exceeds {MAX_FILES_PER_FOLDER}"
        )

    print("Filesystem ownership check passed: no persistent writes escaped the output directory")

    print("Compression test passed. Now testing decompression.")

    # Part 2: Test decompression
    # Delete the original test input directory to ensure decompress doesn't cheat
    if os.path.exists(TEST_INPUT_DIR):
        shutil.rmtree(TEST_INPUT_DIR)

    # Run the decompress script to revert in-place
    try:
        print(f"Running decompress script: {DECOMPRESS_SCRIPT} {TEST_OUTPUT_DIR}")
        result = run_as_sandbox_user(
            [
                "uv",
                "run",
                "--no-sync",
                "python",
                os.path.join(EXEC_ROOT, "decompress.py"),
                TEST_OUTPUT_DIR,
            ],
            runtime_root=DECOMPRESS_RUNTIME_ROOT,
            timeout=600,
            cwd=EXEC_ROOT,
        )
        if result.returncode != 0:
            print(f"Decompress script failed with return code {result.returncode}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            assert False, f"Decompress script failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        assert False, "The decompress script timed out!"
    finally:
        shutil.rmtree(DECOMPRESS_RUNTIME_ROOT, ignore_errors=True)

    assert_only_output_dir_was_created(TEST_OUTPUT_ROOT, TEST_OUTPUT_DIR)

    # Verify that the files in TEST_OUTPUT_DIR now match the original hashes
    output_files = os.listdir(TEST_OUTPUT_DIR)

    # Assert that the fileset is the same by checking basenames
    assert set(original_hashes.keys()) == set(output_files), (
        f"File sets don't match. Original: {set(original_hashes.keys())}, "
        f"Output: {set(output_files)}"
    )

    # Assert that the files are the same by checking the hashes
    for file in output_files:
        file_path = os.path.join(TEST_OUTPUT_DIR, file)
        with open(file_path, "r") as f:
            file_content = f.read().strip()
            file_hash = hashlib.sha256(file_content.encode()).hexdigest()

        expected_hash = original_hashes[file]
        assert file_hash == expected_hash, (
            f"File {file} hash mismatch. Expected: {expected_hash}, Got: {file_hash}"
        )

    print(f"Successfully verified {len(output_files)} files match original hashes")
