# get-bitcoin-nodes

This experiment started as a port of Terminal Bench's `get-bitcoin-nodes`
task, but it is now maintained as a Bunsen-native fork.

## Why It Is Native

Upstream Terminal Bench's task contract is internally inconsistent and depends
on undeclared historical blockchain access:

- the original task introduction asked for a Bitcoin Core RPC client and said
  the service should run on `8332`, which is at least RPC-shaped
- a later upstream rewrite kept the "Create a Bitcoin Core RPC client
  connection" wording but changed the prompt to require connecting on `8333`,
  the default Bitcoin P2P port
- the verifier deterministically expects the mainnet genesis block and the
  genesis coinbase transaction to be available through the service
- the upstream reference solution probes peers on `8333` but then hard-codes
  the genesis block and transaction instead of retrieving them from a real
  Bitcoin Core RPC server or a real historical P2P sync path

That means the upstream task is not cleanly testing one explicit architecture.
It mixes RPC language, P2P port language, and deterministic historical-data
requirements without provisioning a local node, RPC credentials, or any pinned
chain data.

## Native Shape

- the graded API surface is unchanged: `/block/<block_hash>`,
  `/transaction/<txid>`, and `/status`
- the native fork seeds a pinned Bitcoin fixture into
  `/workspace/bitcoin-fixture/`
- the task prompt now makes that fixture explicit and states that live peer or
  RPC connectivity is optional rather than an unstated requirement
- `score_in_agent_container: true` is preserved
- the agent timeout is restored to the upstream Terminal Bench value of `900`
  seconds and the verifier timeout remains `180` seconds
- the verifier is intentionally stricter than upstream:
  - `/status` must return exactly `{"status":"online"}`
  - the graded genesis block response must exactly match the seeded block
    fixture
  - the graded genesis transaction response must exactly match the seeded
    transaction fixture
  - invalid block and transaction lookups must return `404` with exactly one
    non-empty string field, `error`

The benchmark intent is still to build and run a local service that exposes
Bitcoin-shaped data over HTTP. The fork only removes the hidden infrastructure
guessing game and makes the deterministic historical data source explicit.
It also makes the verifier faithful to the written API contract rather than to
the narrower upstream test coverage.

## Upstream Provenance

- initial upstream task commit: `708afa53d` (`retrieve bitcoin data from protocol task`)
- later upstream rewrite carrying the `8333` contradiction:
  `131ed1275` (`Remove support for multiple task descriptions`)
- later background-run clarification: `a01da6d3c` (`Clarify task descriptions`)

The Bunsen fork is intentionally explicit about that divergence instead of
presenting the stabilized task as a plain unmodified Terminal Bench port.
