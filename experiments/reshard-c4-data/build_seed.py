# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "datasets==3.6.0",
# ]
# ///

import json
import math
import shutil
import argparse
import hashlib
from pathlib import Path

from datasets import load_dataset  # type: ignore

DEFAULT_DATA_FILE = "en/c4-train.00000-of-01024.json.gz"
DEFAULT_ROOT_NAME = "c4_sample"
DEFAULT_STAGE_ROOT = Path("/seed")
DEFAULT_NUM_SPLITS = 10000


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-file", default=DEFAULT_DATA_FILE)
    parser.add_argument("--root-name", default=DEFAULT_ROOT_NAME)
    parser.add_argument("--stage-root", type=Path, default=DEFAULT_STAGE_ROOT)
    parser.add_argument("--num-splits", type=int, default=DEFAULT_NUM_SPLITS)
    parser.add_argument("--hashes-path", type=Path)
    return parser.parse_args()


def build_sample(data_file, root_name, stage_root, num_splits, hashes_path=None):
    sample_dir = stage_root / root_name
    stage_root.mkdir(parents=True, exist_ok=True)
    if sample_dir.exists():
        shutil.rmtree(sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(
        "allenai/c4",
        data_files={"train": [data_file]},
        split="train",
    )

    total_samples = len(dataset)
    samples_per_split = math.ceil(total_samples / num_splits)

    current_split = None
    current_file = None
    file_hashes = {}
    current_hasher = None
    current_output_file = None
    first_line = True

    def close_current_file():
        nonlocal current_file, current_split, current_hasher, current_output_file, first_line
        if current_file is None or current_hasher is None or current_output_file is None:
            return
        current_file.close()
        file_hashes[current_output_file.name] = current_hasher.hexdigest()
        current_file = None
        current_split = None
        current_hasher = None
        current_output_file = None
        first_line = True

    for index, item in enumerate(dataset):
        split_index = index // samples_per_split
        if split_index >= num_splits:
            break

        if split_index != current_split:
            close_current_file()
            current_split = split_index
            current_output_file = sample_dir / f"c4-mini-{split_index:05d}-of-{num_splits:05d}.jsonl"
            current_file = current_output_file.open("w", encoding="utf-8")
            current_hasher = hashlib.sha256()
            first_line = True
            if split_index % 10 == 0:
                print(f"Created mini-shard {split_index + 1}/{num_splits}")

        record = dict(item)
        record.pop("timestamp", None)
        line = json.dumps(record)
        current_file.write(line + "\n")
        if not first_line:
            current_hasher.update(b"\n")
        current_hasher.update(line.encode("utf-8"))
        first_line = False

    close_current_file()

    if hashes_path is not None:
        hashes_path.parent.mkdir(parents=True, exist_ok=True)
        hashes_path.write_text(json.dumps(file_hashes, indent=2, sort_keys=True) + "\n")


def main():
    args = parse_args()
    build_sample(
        data_file=args.data_file,
        root_name=args.root_name,
        stage_root=args.stage_root,
        num_splits=args.num_splits,
        hashes_path=args.hashes_path,
    )


if __name__ == "__main__":
    main()
