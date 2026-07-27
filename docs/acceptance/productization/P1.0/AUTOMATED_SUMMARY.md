# P1.0 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- Candidate: working-tree target-contract candidate based on G0 commit `226e2d48d0731f989c3895e4abc5237cee2b2d10`
- Candidate fingerprint: `DE13234D6DDC51F2A34F4FFFD4AFF020A0BB0EF53B4704D118EF4DAFF6632E71` over 26 non-evidence source files
- Contract gates: `PASS`
- Independent review: in progress
- User decision: Pending

P1.0 changes target contracts, decision records, governance state and validation scripts only. It does not change the product runtime, implemented POC contracts or a database.

## Executed Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Machine contract and Markdown consistency | `PASS` | `P1_CONTRACT_OK checks=1439 operations=70 entities=31 roles=5` |
| Contract negative-fixture self-test | `PASS` | `P1_CONTRACT_SELF_TEST_OK cases=70` |
| Documentation lifecycle | `PASS` | `DOC_LIFECYCLE_OK checks=298 links=136 files=108 plugin_files=1` |
| Unstaged diff check | `PASS` | `git diff --check` returned 0 with no output |
| Staged diff check | `PASS` | `git diff --cached --check` returned 0 with no output |
| Lifecycle-lint self-test | `N/A` | the lifecycle lint implementation did not change |
| Runtime build and functional tests | `N/A` | P1.0 is target contract design only; no runtime file changed |
| Database migration / restore execution | `N/A` | no database or migration exists in this batch |
| Real local IAM / device credential tests | `N/A` | identity and device trust are target contracts for P1.1 |
| Real three-screen execution | `N/A` | three-screen target behavior is implemented in P1.2-P1.3 |
| Real backup, RPO and RTO drill | `N/A` | targets are frozen here and measured in P1.3 |
| PostgreSQL certification | `N/A` | PostgreSQL 16 remains `UNVERIFIED` until later implementation evidence |
| FineReport plugin | `N/A` | P2 external gate remains unchanged and blocked |

## Negative Fixtures

The self-test accepts the baseline and proves rejection of 69 mutated contracts. The mutations cover:

- exact state-machine bypasses, missing transitions, terminal-state reopening and ambiguous device-credential entry states;
- permission-registry drift, role escalation and operation method/path/permission changes;
- default-allow or partial draft writes, wrong JSON-Pointer permission and weakened FineReport joint authorization;
- stale ResolutionFingerprint reuse, Publication-created ReleaseTargets and incomplete PublicationTarget composite keys;
- missing different-user approval, free-form high-risk action creation, request-hash omissions and protected-operation marker drift;
- changed password/session/reset/device/SQLite/backup-retention parameters;
- recovery ledger co-location, unauthenticated chains, missing generations, stale anchors and old password/device credential resurrection;
- missing bootstrap/reset/reauth/session API closure, cacheable one-time responses and immutable-release deletion;
- publication without control-plane `If-Match`, device acknowledgement incorrectly using it and cross-screen fixture leakage;
- duplicate DigitalHumanInstance ownership and security evidence placed under runtime retention.

## Target Decisions Validated

- one Site can own three independently bound screens;
- control-plane user, screen-device and FineReport identities are separate;
- five fixed product roles map to 22 explicit permissions;
- draft changes use default-deny field authorization; FineReport binding requires all three dedicated permissions;
- ConfigDraft evidence binds a ResolutionFingerprint; ConfigRelease / ReleaseTarget and their exact Secret/binding versions are immutable;
- RuntimeBinding keeps desired and applied target IDs separate;
- production publication, rollback, device hard revocation, Secret/FineReport identity replacement and restore use typed different-user approval;
- group publication uses existing targets and checks the group ETag plus per-screen ETags/generations;
- SQLite is the embedded target and PostgreSQL 16 the only external target;
- production backup uses a separate mounted filesystem, hourly cadence, 24 hourly / 7 daily / 4 weekly retention and one-hour RPO / two-hour RTO targets;
- an authenticated RecoverySecurityLedger and separate monotonic anchor prevent user/password/device security rollback;
- target API uses separate versioned user and device namespaces with safe errors.

## Evidence Boundary

The machine manifest contains sanitized hashes for the contract registry, validation scripts, summaries, candidate file list and rollback proof. Raw command output and temporary recovery-tree evidence remain outside Git under `logs/productization/`.

Passing P1.0 proves that the target contract is coherent. It does not prove any runtime capability.
