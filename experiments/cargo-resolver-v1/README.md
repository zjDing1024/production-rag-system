# Cargo resolver scope and evidence pilot

Original offline evidence pilot using Cargo 0.86.0 pinned source summaries. It separates root package edition, virtual workspace root, and explicit resolver. No Cargo source is copied and no model is run in CI.

Pinned source commit: d73d2caf9e41a39daf2a8d6ce60ec80bf354d2a7 (Cargo.toml declares MIT OR Apache-2.0). Root selection: src/cargo/core/workspace.rs L288-L299. Edition mapping: src/cargo/core/features.rs L305-L312. Virtual fallback warning: src/cargo/core/workspace.rs L1088-L1109.

Frozen rows:
- root package edition 2021, no override: resolver 2
- root package edition 2024, no override: resolver 3
- virtual root, edition 2024 member, no root resolver: resolver 1
- virtual root with explicit root resolver 3: resolver 3

A partial virtual-workspace excerpt that only says the resolver must be set explicitly is insufficient for numeric 1; a member-edition passage is wrong scope. Correct-by-memory output without supplied root/virtual evidence is unsupported.

Run: python experiments/cargo-resolver-v1/audit.py --check
This is a deterministic source/scope rubric, not a Cargo runtime or model quality claim.
