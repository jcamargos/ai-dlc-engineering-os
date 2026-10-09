# Security policy

Report vulnerabilities privately through GitHub's private vulnerability reporting for this
repository. Do not open public issues with exploit details, tokens or customer data.
Expect acknowledgement within two business days.

Supported: the latest release on the default branch.

Design guarantees you can test: credential refusal on every write path, prompt-injection
flagging and withholding, human-only approvals (`ai-dlc-admin` requires an interactive TTY),
hard purge with audit scrubbing, opt-in federation/marketplace, loopback-only Mission Control.
