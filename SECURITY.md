# Security policy

Report vulnerabilities privately through GitHub's private vulnerability reporting for this
repository. Do not open public issues with exploit details, tokens or customer data.
Expect acknowledgement within two business days.

Supported: the latest release on the default branch.

Design guarantees you can test: credential refusal on every write path, prompt-injection
flagging and withholding, human-only approvals (`ai-dlc-admin` requires an interactive TTY),
hard purge with audit scrubbing, opt-in federation/marketplace, loopback-only Mission Control.

Repository graphs require an explicit `AI_DLC_GRAPH_ROOTS` allowlist on the server host.
They never execute indexed source or store source bodies. Paths and import edges are
untrusted data and may be sent to a model by the client. Symlinks/reparse points are
excluded; size, traversal and response limits bound normal use. This is not a sandbox
against a malicious local process racing filesystem changes. See
[graph boundaries](docs/REPOSITORY_GRAPH.md).
