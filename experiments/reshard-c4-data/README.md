# reshard-c4-data

This experiment started as a port of Terminal Bench's `reshard-c4-data` task, but it is now maintained as a Bunsen-native fork. This file records the ways it differs from the original task and why.

## Goal

Keep the benchmark intent the same:

- the agent writes `compress.py` and `decompress.py`
- `compress.py` must obey the directory fanout and file size limits
- `decompress.py` must restore the original hidden input exactly
- the solution should not be able to persist stash data outside the allowed output area and reconstruct from that later

## Original Terminal Bench Shape

The original task:

- used `/app` instead of `/workspace`
- baked the visible sample directly into the image workspace during image build
- generated the hidden shard at verifier runtime from C4 shard `00009`
- enforced "do not write outside the output dir" by snapshotting essentially all of `/` before and after `compress.py`

Source references:

- [`task.yaml`](https://github.com/laude-institute/terminal-bench/blob/main/original-tasks/reshard-c4-data/task.yaml)
- [`Dockerfile`](https://github.com/laude-institute/terminal-bench/blob/main/original-tasks/reshard-c4-data/Dockerfile)
- [`tests/test_outputs.py`](https://github.com/laude-institute/terminal-bench/blob/main/original-tasks/reshard-c4-data/tests/test_outputs.py)

## Differences From Terminal Bench

### 1. `/app` became `/workspace`

This is the normal Bunsen path translation. The task instructions in [`experiment.yaml`](./experiment.yaml) are otherwise intended to be semantically equivalent.

One small wording change was also made: shell-active markdown like backticked usage examples was removed from the task prompt because raw orchestrated shell invocation had previously interpreted those badly.

### 2. The visible sample is seeded directly from the image into `/workspace`

Current shape:

- the image builds `/seed/c4_sample/` (expanded, ~10,000 small files)
- Bunsen seeds that directory into `/workspace-source/c4_sample/` via `workspace.sources[].imagePath`
- the executor materializes `/workspace` from `/workspace-source` as the non-root execution user, so no recursive ownership handoff is required

Files:

- [`Dockerfile`](./Dockerfile)
- [`build_seed.py`](./build_seed.py)
- [`experiment.yaml`](./experiment.yaml)

Why:

- baking thousands of files into `/workspace-source` is cheap now that workspace materialization runs as the execution user (so no recursive ownership handoff is needed)
- the visible input data is identical to the benchmark; only the transport shape changed

This is an implementation change, not an intended benchmark change.

### 3. The hidden fixture is prebuilt and pinned instead of regenerated every run

Current shape:

- verifier reads [`verifiers/hidden_input.tar.gz`](./verifiers/hidden_input.tar.gz)
- verifier checks it against [`verifiers/hidden_input.sha256`](./verifiers/hidden_input.sha256)
- verifier validates the extracted filenames against [`verifiers/files_hashes.json`](./verifiers/files_hashes.json)

Why:

- runtime generation of the hidden input from Hugging Face was far too slow in Bunsen and dominated scorer runtime
- pinning a verifier-only archive makes scoring deterministic and fast enough to be practical

Important caveat:

- this is the biggest known divergence from Terminal Bench
- the current Bunsen-side [`files_hashes.json`](./verifiers/files_hashes.json) is not byte-identical to Terminal Bench's original [`files_hashes.json`](https://github.com/laude-institute/terminal-bench/blob/main/original-tasks/reshard-c4-data/tests/files_hashes.json)
- so although the hidden fixture still represents "C4 shard `00009` split into 10,000 files", it is not guaranteed to be the exact same hidden bytes that the original TB task used

This means the benchmark intent is preserved, but exact TB fixture parity is not.

### 4. Verifier scratch data lives under `/var/tmp`, not `/workspace`

Current verifier scratch root is created under `/var/tmp/...`.

Why:

- in Bunsen's separate scorer container, `/workspace` is an extracted/mounted workspace copy
- verifier-owned scratch trees with thousands of files are much slower there than on normal container storage

This does not change what the agent sees or what is scored. It only changes where the verifier stages its own temporary files.

### 5. Anti-cheating enforcement changed from full-filesystem diffing to a dedicated-UID persistence check

Original TB verifier:

- walked and hashed essentially all of `/` before `compress.py`
- ran `compress.py`
- walked and hashed all of `/` again
- failed if anything outside the output dir had changed

Current Bunsen verifier:

- runs `compress.py` and `decompress.py` as a dedicated unprivileged UID/GID
- redirects scratch paths like `HOME`, `TMPDIR`, and cache dirs into per-phase runtime roots under the verifier test root
- runs the candidate from a copied read-only exec root under the verifier test root instead of directly from `/workspace`
- after `compress.py`, scans for newly created persistent paths owned by that UID outside the allowed output dir and fails if any exist

Why:

- full-root hashing was too slow in Bunsen
- `strace`-based checking turned out to be too noisy and brittle
- `bubblewrap` was not usable inside the scorer container because namespace creation was blocked by the container runtime

What this preserves:

- it still blocks the main cheat we care about: `compress.py` persisting recoverable data outside the output dir for `decompress.py` to use later

What this no longer guarantees:

- it is not as broad as TB's literal full-filesystem diff
- it can miss transient write-then-delete behavior outside the output dir
- it can miss modifications to preexisting writable paths whose ownership does not change

So this is a real strictness tradeoff, even though it preserves the most important benchmark property in practice.

### 6. The verifier still checks correctness with the same core semantics

The current verifier still requires:

- `uv sync` to succeed
- `uv run --no-sync` execution for both scripts
- output directory creation
- max 30 entries per directory
- max 15MB per file
- exact hidden-input reconstruction after deleting the original hidden input

This is the part of the verifier we intentionally kept strict.

### 7. The scorer timeout was increased

Current rubric timeout in [`experiment.yaml`](./experiment.yaml) is `7200`.

Why:

- the original TB `max_test_timeout_sec` was `900`
- Bunsen scorer behavior and the cost of this task made that too small during the port

This is a runtime-budget change, not a benchmark-meaning change.

## Current Assessment

### Areas that still match the benchmark intent well

- visible agent task
- required deliverables
- output constraints
- exact decompression correctness check
- hidden-data scoring model
- requirement to use `uv`

### Areas that are not exact Terminal Bench parity

- hidden fixture bytes are pinned locally and do not currently match TB's original checked-in hidden hash manifest byte-for-byte
- anti-cheating enforcement is narrower than TB's original full-filesystem snapshot approach

## If We Want Closer TB Parity Later

The two most meaningful follow-ups would be:

1. Recover the exact original TB hidden fixture bytes, if possible, and repin the Bunsen verifier to those exact bytes.
2. Improve Bunsen/runtime-level scorer sandboxing so this task can enforce "only write here" more directly without expensive verifier-local hacks.
