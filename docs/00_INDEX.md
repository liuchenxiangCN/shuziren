# Documentation Index

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: documentation map and lifecycle entry point
- Last reviewed: 2026-07-27

## Start Here

Codex should read only this small current set by default:

1. [CODEX_CONTEXT.md](CODEX_CONTEXT.md) — current product and phase snapshot
2. [NEXT_ACTIONS.md](NEXT_ACTIONS.md) — exactly one active result batch
3. [13_RISKS_AND_TODO.md](13_RISKS_AND_TODO.md) — active product risks and blockers
4. [RESULT_ACCEPTANCE_STANDARD.md](RESULT_ACCEPTANCE_STANDARD.md) — result acceptance rules

Read [17_STANDARD_PRODUCT_DESIGN.md](17_STANDARD_PRODUCT_DESIGN.md) when changing product behavior or contracts. Read [05_DEVELOPMENT_PLAN.md](05_DEVELOPMENT_PLAN.md) when changing phase scope. Do not read the full archive unless a current document points to a specific item.

The root `AGENTS.md` is stable Codex policy and the root `README.md` is stable product navigation. Neither is a current-phase or next-task source.

## Governance And Execution

| Document | Lifecycle | Purpose |
| --- | --- | --- |
| [DOCUMENT_GOVERNANCE.md](DOCUMENT_GOVERNANCE.md) | Authoritative policy | Lifecycle, truth precedence, archive and size rules |
| [RESULT_ACCEPTANCE_STANDARD.md](RESULT_ACCEPTANCE_STANDARD.md) | Authoritative policy | Result cards, evidence, user decisions and rollback |
| [05_DEVELOPMENT_PLAN.md](05_DEVELOPMENT_PLAN.md) | Authoritative current | Result-driven P1-P5 roadmap |
| [DEV_LOG.md](DEV_LOG.md) | Authoritative current | Factual productization work after G0 |
| [CHANGELOG.md](CHANGELOG.md) | Authoritative current | Productization release-facing changes |
| [acceptance/productization/G0](acceptance/productization/G0) | Acceptance evidence | G0 result card, checks, limitations and decision |
| [acceptance/productization/P1.0](acceptance/productization/P1.0) | Acceptance evidence | P1.0 target-contract result card and evidence |
| [acceptance/productization/P1.1](acceptance/productization/P1.1) | Acceptance evidence | Accepted P1.1 identity and device-trust result |
| [acceptance/productization/P1.2](acceptance/productization/P1.2) | Acceptance evidence | Active frozen P1.2 three-screen inventory result card |

## Product Target

| Document | Lifecycle | Purpose |
| --- | --- | --- |
| [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md) | Target not implemented | Product position and boundary |
| [02_PRODUCT_BLUEPRINT.md](02_PRODUCT_BLUEPRINT.md) | Target not implemented | User value and product workflows |
| [17_STANDARD_PRODUCT_DESIGN.md](17_STANDARD_PRODUCT_DESIGN.md) | Target not implemented | Standard product design |
| [product/contracts/README.md](product/contracts/README.md) | Target not implemented | P1 domain, identity, state, data, storage and API target contracts |
| [integrations/FINEREPORT_AI_PLUGIN_INTEGRATION.md](integrations/FINEREPORT_AI_PLUGIN_INTEGRATION.md) | Target not implemented / external gate | Official plugin evidence and connector boundary |
| [decisions/ADR-0026-finereport-fvs-productization.md](decisions/ADR-0026-finereport-fvs-productization.md) | Accepted ADR | Productization decision |
| [decisions/ADR-0027-result-driven-development-and-document-lifecycle.md](decisions/ADR-0027-result-driven-development-and-document-lifecycle.md) | Accepted ADR | Result-driven development and document lifecycle |
| [decisions/ADR-0028-p1-control-plane-foundation.md](decisions/ADR-0028-p1-control-plane-foundation.md) | Accepted ADR | P1 control-plane foundation accepted with P1.0 |

## Implemented POC Baseline

These files describe the current single-instance POC. They do not define the target multi-screen product:

| Document | Lifecycle | Purpose |
| --- | --- | --- |
| [03_ARCHITECTURE.md](03_ARCHITECTURE.md) | As-built POC | Implemented architecture |
| [04_TECH_STACK.md](04_TECH_STACK.md) | As-built POC | Implemented technology baseline |
| [06_API_CONTRACT.md](06_API_CONTRACT.md) | As-built POC | Implemented HTTP / SSE contracts |
| [07_DATA_CONTRACT.md](07_DATA_CONTRACT.md) | As-built POC | Implemented shared structures |
| [08_CONFIG_GUIDE.md](08_CONFIG_GUIDE.md) | As-built POC | POC environment and customer overlays |
| [09_LOCAL_DEPLOY.md](09_LOCAL_DEPLOY.md) | As-built POC | POC local deployment |
| [10_TEST_PLAN.md](10_TEST_PLAN.md) | As-built / customer POC | POC regression scenarios |
| [14_ENHANCEMENT_ROADMAP.md](14_ENHANCEMENT_ROADMAP.md) | Archived POC snapshot | Historical enhancement roadmap; not a current task source |
| [15_MAINLINE_ARCHITECTURE_DIAGRAM.md](15_MAINLINE_ARCHITECTURE_DIAGRAM.md) | Archived POC snapshot | Historical mainline diagram |
| [16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md](16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md) | Archived POC snapshot | Completed POC configuration-center plan |

## Customer-Specific Material

| Customer | Material |
| --- | --- |
| `zt-securities` | [customers/zt-securities](customers/zt-securities) |
| `finance-dashboard` | [customers/finance-dashboard](customers/finance-dashboard) |

The following stable paths contain POC customer fixtures or delivery evidence and must not be treated as standard-product defaults:

- [demo_data](demo_data)
- [demo_knowledge](demo_knowledge)
- [11_POC_DEMO_SCRIPT.md](11_POC_DEMO_SCRIPT.md)
- [12_CUSTOMER_HANDOFF.md](12_CUSTOMER_HANDOFF.md)
- [delivery/v1.0](delivery/v1.0)

## External Integration Baseline

The Dora, RAGFlow, FVS and ASR / TTS documents describe POC integration evidence unless explicitly updated by a target contract:

- [integrations/DORA_INTEGRATION.md](integrations/DORA_INTEGRATION.md)
- [integrations/DORA_AGENT_PROMPT.md](integrations/DORA_AGENT_PROMPT.md)
- [integrations/RAGFLOW_INTEGRATION.md](integrations/RAGFLOW_INTEGRATION.md)
- [integrations/FVS_INTEGRATION.md](integrations/FVS_INTEGRATION.md)
- [integrations/ASR_TTS_INTEGRATION.md](integrations/ASR_TTS_INTEGRATION.md)

## Decisions

ADRs stay at stable paths under [decisions](decisions). Use the [decision index](decisions/README.md) for current and historical scope. ADR-0026 supersedes the earlier product-positioning ADRs. Older ADRs remain valid only for the implemented POC behavior they describe unless explicitly superseded.

## Archive

[archive/poc-v1](archive/poc-v1) preserves long-form POC and initial productization history. Archived “current” and “next” language is historical and never directs new work.

## Automated Check

Run:

```powershell
scripts/lint-doc-lifecycle.ps1
```
