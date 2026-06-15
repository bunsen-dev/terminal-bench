# Terminal Bench (Bunsen suite)

A port of [Terminal Bench](https://www.terminal-bench.org) into Bunsen's
suite format. Each task is a self-contained `experiment.yaml` under
[`experiments/`](./experiments); the suite manifest in
[`bunsen-suite.yaml`](./bunsen-suite.yaml) names the suite and declares
where Bunsen should look for them. Project-management tasks (porting
work, fork notes, follow-ups) live alongside in [`tasks/`](./tasks).

## Using the suite

This suite is consumed via Bunsen's git-native suite system. From a Bunsen
project's `bunsen.config.yaml`:

```yaml
suites:
  - source:
      type: git
      url: https://github.com/bunsen-dev/terminal-bench.git
      ref: v0.1.0
    as: terminal-bench
```

The canonical suite id is derived from the clone URL —
`github.com/bunsen-dev/terminal-bench` — and recorded on every run's
manifest. The optional `as: terminal-bench` alias is purely a local
shorthand for `bn run terminal-bench/<task-name>`.

## Running tasks

Once the suite is added (`bn suites add`, or by clone + `paths.experiments`
entry), individual tasks run like any other Bunsen experiment:

```sh
bn run terminal-bench/hello-world --agent claude-code
bn run github.com/bunsen-dev/terminal-bench/blind-maze-explorer-5x5 --agent echo-agent
```

## Native forks

Most tasks are mechanical translations of the upstream Terminal Bench
benchmark. A handful are maintained as native Bunsen experiments because
they need semantics-aware handling (custom verifier, bespoke service shape,
etc.) — see [`scripts/tb-native-tasks.yaml`](./scripts/tb-native-tasks.yaml)
for the list and the rationale for each fork.

## License & attribution

This repository is licensed under the [Apache License 2.0](./LICENSE).

The task content under [`experiments/`](./experiments) is derived from
[Terminal Bench](https://www.terminal-bench.org)
([`laude-institute/terminal-bench`](https://github.com/laude-institute/terminal-bench)),
Copyright the Terminal Bench authors, originally licensed under Apache-2.0, and
has been modified for this suite. See the [`NOTICE`](./NOTICE) file for the
required attribution, statement of changes, and a list of bundled third-party
components (which remain under their own licenses).
