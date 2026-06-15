# polyglot-rust-c

This experiment started as a port of Terminal Bench's `polyglot-rust-c` task,
but it is now maintained as a Bunsen-native fork.

## Why It Is Native

Upstream Terminal Bench's task contract is weaker than its test contract:

- The prompt asks for a "single file polyglot" at `/workspace/polyglot/main.rs`
  and explicitly invites the agent to verify it with both
  `rustc /workspace/polyglot/main.rs && /workspace/polyglot/main N` and
  `g++ -x c++ /workspace/polyglot/main.rs -o /workspace/polyglot/cmain && /workspace/polyglot/cmain N`.
- The verifier then asserts `os.listdir("/workspace/polyglot") == ["main.rs"]`,
  so the prompt-encouraged `main` and `cmain` artifacts cause a 0.0 score
  before any functional check runs.
- The verifier itself runs the same `rustc` and `g++` invocations during
  grading and never cleans up their outputs, so the post-grading directory
  is not actually pristine either.

In other words, "single file polyglot" is meant to describe the source-level
deliverable, not the literal post-run directory contents — but the verifier
treated it as the latter, penalizing the natural compile-and-run verification
workflow the prompt itself encourages.

## Native Shape

- the task prompt is unchanged with respect to the polyglot requirement
- a short clarification is added making the relaxed semantics explicit:
  the deliverable is `main.rs` and leftover compile artifacts from
  prompt-encouraged verification do not affect grading
- the verifier is softened:
  - it asserts `main.rs` exists as a regular file (source-level uniqueness)
  - it always recompiles from that source with both `rustc` and `g++`
    before running the binaries, so the compiled artifacts under test are
    the ones the verifier produced rather than whatever the agent may have
    left behind
  - the strict `os.listdir(...) == ["main.rs"]` directory equality check
    is dropped
  - compilation now uses `subprocess.run(..., check=True)` instead of
    `os.popen(...).read()` so toolchain failures surface clearly rather
    than being silently swallowed
- the rest of the task — the Fibonacci test cases for both the recompiled
  Rust binary and the recompiled C++ binary — is unchanged

The benchmark intent is the same: write a file that is simultaneously a valid
Rust program and a valid C++ program and produces correct Fibonacci output
under both toolchains. The fork only removes a verifier-only cleanliness
requirement that was never spelled out in the task itself.
