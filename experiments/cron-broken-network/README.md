# cron-broken-network

This experiment started as a port of Terminal Bench's `cron-broken-network`
task, but it is now maintained as a Bunsen-native fork.

## Why It Is Native

Upstream Terminal Bench expects `curl example.com` to return a specific HTML
snapshot and hard-codes that expectation in the verifier. That no longer holds
reliably against the live public site, so correct repairs can fail
deterministically for reasons unrelated to the task.

Rather than add task-specific external-fixture logic to the shared Terminal
Bench converter, Bunsen maintains this task natively and pins the expected
`example.com` response inside the experiment.

## Native Shape

- the task prompt is unchanged
- the sabotage mechanisms that repeatedly break `/usr/bin/curl` are unchanged
- the experiment still requires root and still scores in the agent container
- the verifier carries a pinned `example.com` fixture and serves it locally
  only during the delayed content check, via curl's `--connect-to` override
- the verifier reads the same pinned fixture from
  `verifiers/example.com.html`
- `experiment.yaml` restores Terminal Bench's original `900` second agent
  timeout and `180` second rubric timeout

## Bunsen-Specific Runtime Note

This task intentionally does not use an image `ENTRYPOINT` to start long-lived
task processes.

Bunsen launches Dockerfile experiments as persistent containers with its own
long-lived command and Docker `Init: true`, then performs task startup during
`environment.workspace_setup`. Keeping the runtime startup there makes the task
compatible with Bunsen's execution model while preserving the same task
surface for the agent.

This keeps the benchmark intent the same: the agent still has to diagnose and
remove the persistent sabotage, restore a real curl binary, and make
`/usr/bin/curl example.com` stay healthy across the delayed verifier check.

The only intended divergence from upstream is that the delayed content
assertion is pinned to a local fixture instead of the live internet. The
agent-visible runtime no longer relies on task-injected DNS or hosts changes.
