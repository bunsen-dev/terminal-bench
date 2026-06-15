# polyglot-c-py

This experiment started as a port of Terminal Bench's `polyglot-c-py` task,
but it is now maintained as a Bunsen-native fork.

## Why It Is Native

Upstream Terminal Bench's task contract is weaker than its test contract:

- The prompt asks for a "single file polyglot" at `/workspace/polyglot/main.py.c`
  and explicitly invites the agent to verify it with
  `gcc /workspace/polyglot/main.py.c -o /workspace/polyglot/cmain && /workspace/polyglot/cmain N`.
- The verifier then asserts `os.listdir("/workspace/polyglot") == ["main.py.c"]`,
  so the prompt-encouraged `cmain` artifact causes a 0.0 score before any
  functional check runs.
- The verifier itself runs `gcc ... -o /workspace/polyglot/cmain` and never
  cleans it up, so the post-grading directory is not actually pristine either.

In other words, "single file polyglot" is meant to describe the source-level
deliverable, not the literal post-run directory contents — but the verifier
treated it as the latter, penalizing the natural compile-and-run verification
workflow the prompt itself encourages.

## Native Shape

- the task prompt is unchanged with respect to the polyglot requirement
- a short clarification is added making the relaxed semantics explicit:
  the deliverable is `main.py.c` and leftover compile artifacts from
  prompt-encouraged verification do not affect grading
- the verifier is softened:
  - it asserts `main.py.c` exists as a regular file (source-level uniqueness)
  - it always recompiles from that source before running the binary, so the
    compiled artifact under test is the one the verifier produced rather than
    whatever the agent may have left behind
  - the strict `os.listdir(...) == ["main.py.c"]` directory equality check
    is dropped
- the rest of the task — the Fibonacci test cases for both `python3
  /workspace/polyglot/main.py.c N` and the recompiled C binary — is unchanged

The benchmark intent is the same: write a file that is simultaneously a valid
Python program and a valid C program and produces correct Fibonacci output
under both toolchains. The fork only removes a verifier-only cleanliness
requirement that was never spelled out in the task itself.
