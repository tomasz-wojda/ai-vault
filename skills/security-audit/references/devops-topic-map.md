# DevOps Topic Map

DevOps security questions map onto the existing companions. The evidence bar does not change: a topic produces a finding only with a lower-trust principal, a crossed boundary, and a concrete result. Otherwise it is a hardening note.

| Topic | Companion sections |
| --- | --- |
| Secret handling | [cloud-and-deployment.md](cloud-and-deployment.md) "Configuration and secret lifecycle"; [supply-chain-and-release.md](supply-chain-and-release.md) "Dependency and build-input" and "CI and automation"; [data-isolation-and-lifecycle.md](data-isolation-and-lifecycle.md) "Export, backup, restore, and migration" |
| Dependency CVE triage | [supply-chain-and-release.md](supply-chain-and-release.md) "Dependency and build-input". A known-vulnerable dependency is a finding only with a reachable boundary path |
| IAM and least privilege | [cloud-and-deployment.md](cloud-and-deployment.md) "Workload identity and IAM" |
| Container image hardening | [cloud-and-deployment.md](cloud-and-deployment.md) "Container and orchestration"; [supply-chain-and-release.md](supply-chain-and-release.md) "Release and update" for artifact provenance |
| CI pipelines, including Jenkins | [supply-chain-and-release.md](supply-chain-and-release.md) "CI and automation" |
| Kubernetes manifests, Helm, and Terraform | [cloud-and-deployment.md](cloud-and-deployment.md) |

PR review is out of scope for this skill.
