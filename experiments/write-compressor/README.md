# write-compressor

This experiment started as a port of Terminal Bench's `write-compressor` task,
but it is now maintained as a Bunsen-native fork.

## Why It Is Native

Upstream Terminal Bench runs the task directly in the image filesystem, where
`decomp.c`, `data.txt`, and the compiled `decomp` binary all live under `/app`.
That does not map cleanly onto Bunsen's runtime contract:

- the agent gets a writable `/workspace`
- immutable starter files live in `/workspace-source`
- verifiers should not mutate seeded inputs

The mechanical port initially failed twice in different ways:

1. the agent saw an empty `/workspace` because the build-time files had not
   been seeded into the runtime workspace
2. once explicit seeds were added, the generic verifier rewrite redirected
   mutable writes into read-only `/workspace-source`

That is task-specific semantics, not a good fit for the shared converter.

## Native Shape

- the Dockerfile still builds `decomp` from the upstream `decomp.c`
- `experiment.yaml` seeds `decomp.c`, `data.txt`, and `decomp` into
  `/workspace` with `workspace.sources`
- the verifier reads the immutable originals from `/workspace-source`
- the verifier checks the agent-authored `/workspace/data.comp`

This keeps the benchmark intent the same while making Bunsen's workspace model
explicit and correct.
