# P1.0 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Candidate: commit `d78de0cfce64777678ec606b03470d6ffd5e970f`, tree `8538a8b89b789ebac7ff436ec17c51d1fa86bb47`
- Base accepted version: commit `226e2d48d0731f989c3895e4abc5237cee2b2d10`, tree `f2846576b1184fcf522151057215fb41a9efc4d0`
- Candidate fingerprint: `8B894F9EAF0A491A3F5DA3B367B4D03DBD56C63A0470B5840E354CA06160C633` over 26 non-evidence files
- Changed scope: 31 documentation and validation-script files; runtime unchanged
- Contract gates: `PASS`
- Independent review: `PASS`; zero blocking findings and report hash bound
- User decision: `通过` on 2026-07-27

P1.0 changes target contracts, decision records, governance state and validation scripts only. It does not change the product runtime, implemented POC contracts or a database.

## Executed Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Machine contract and Markdown consistency, PowerShell 7 | `PASS` | `P1_CONTRACT_OK checks=2722 operations=86 entities=32 roles=5` |
| Machine contract and Markdown consistency, PowerShell 5.1 | `PASS` | `P1_CONTRACT_OK checks=2722 operations=86 entities=32 roles=5` |
| Contract negative-fixture self-test | `PASS` | `P1_CONTRACT_SELF_TEST_OK cases=191`: 1 baseline, 166 semantic PowerShell 5.1 executions and 12 raw fixtures on each of PowerShell 5.1 and PowerShell 7 (24 executions) |
| Registry consistency | `PASS` | 23 permissions, 16 state machines, 31 internal security records, 40 errors, 18 key purposes and 20 four-eyes operations |
| Documentation lifecycle, PowerShell 7 | `PASS` | `DOC_LIFECYCLE_OK checks=298 links=135 files=108 plugin_files=1` |
| Documentation lifecycle, PowerShell 5.1 | `PASS` | `DOC_LIFECYCLE_OK checks=298 links=135 files=108 plugin_files=1` |
| Candidate fingerprint and scope | `PASS` | 26 fingerprint files; 31 changed paths are documentation or validation scripts; runtime unchanged |
| Secret scan | `PASS` | 31 files scanned; 0 findings |
| Diff checks | `PASS` | whitespace and changed-path checks returned no findings |
| Independent Codex review | `PASS` | zero blocking findings; report SHA-256 is bound in `manifest.json` |
| G0 rollback proof | `PASS` | exact accepted G0 tree recovered; both hosts returned `DOC_LIFECYCLE_OK checks=267 links=122 files=97 plugin_files=0`; P1-only paths were absent |
| Lifecycle-lint self-test | `N/A` | the lifecycle lint implementation did not change |
| Runtime build and functional tests | `N/A` | P1.0 is target-contract design only; no runtime file changed |
| Database migration / restore execution | `N/A` | no runtime database or migration exists in this batch |
| Real local IAM / device credential tests | `N/A` | identity and device trust are target contracts for P1.1 |
| Real three-screen execution | `N/A` | three-screen target behavior belongs to P1.2-P1.3 |
| Real backup, RPO and RTO drill | `N/A` | targets are frozen here and measured in P1.3 |
| PostgreSQL certification | `N/A` | PostgreSQL 16 remains `UNVERIFIED` until later implementation evidence |
| FineReport plugin | `N/A` | the P2 external gate remains blocked and unchanged |

## Negative Fixtures

The self-test accepts one baseline and proves rejection of 190 executions:

- 166 semantic contract mutations run under PowerShell 5.1;
- 12 raw-JSON mutations run under PowerShell 5.1 and again under PowerShell 7, for 24 raw executions;
- raw cases cover duplicate or Unicode-aliased keys, non-finite and out-of-range numbers, invalid number syntax, trailing content and multiple top-level values;
- semantic cases cover exact state-machine transitions, permission and role registries, field-level authorization, immutable releases, approval binding, direct-operation authorization, enrollment, three-screen isolation, backup and restore security, and versioned API safety.

## Target Decisions Validated

- one Site can own three independently bound screens;
- control-plane user, screen-device and FineReport identities are separate;
- five fixed product roles map to 23 explicit permissions;
- 86 network operations bind exact authorization, precondition, idempotency and error behavior;
- draft changes use default-deny field authorization; FineReport binding requires all dedicated permissions;
- ConfigDraft evidence binds a ResolutionFingerprint; ConfigRelease, ReleaseTarget and their exact Secret/binding versions are immutable;
- RuntimeBinding keeps desired and applied target IDs separate;
- 20 production high-risk operations require typed four-eyes authorization, while only the exact direct asynchronous backup operations use frozen direct-operation authorization;
- group publication uses existing targets and checks the group ETag plus per-screen ETags and generations;
- SQLite is the embedded target and PostgreSQL 16 the only external target;
- production backup uses a separate mounted filesystem, hourly cadence, 24 hourly / 7 daily / 4 weekly retention and one-hour RPO / two-hour RTO targets;
- an authenticated RecoverySecurityLedger and separate monotonic anchor prevent user, password and device-security rollback;
- target API uses separate versioned user and device namespaces with 40 safe error definitions.

## Evidence Boundary

- Evidence root: `logs/productization/P1.0-20260727T064034Z`
- The tracked manifest binds the candidate commit, tree, fingerprint, gate outcomes and rollback result.
- The tracked manifest binds the raw evidence manifest and independent-review report by SHA-256.
- Raw command output and the temporary recovery tree remain outside Git under `logs/productization/`.

Passing the gates proves that the P1.0 target contract is coherent and recoverable to G0. It does not prove a runtime capability, does not accept P1.0, does not change ADR-0028 from `Proposed`, and does not start P1.1.
