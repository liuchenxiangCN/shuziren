# P1.0 Known Limitations

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- Candidate: P1.0 target-contract result pack

## Limitations

- Every P1.0 capability is `TARGET_NOT_IMPLEMENTED`; the current runtime remains the single-instance POC.
- The operation registry is machine-readable, but P1.0 does not generate an OpenAPI client/server artifact or implement request handlers.
- Detailed configuration schemas for Provider, QuerySource, ScreenActionPack, AvatarPackage and capability profiles belong to later result batches.
- Local IAM, typed different-user approval, device rotation/revocation and the externally anchored RecoverySecurityLedger have not been exercised against real persistence.
- SQLite and PostgreSQL migration behavior has not been implemented or tested. PostgreSQL 16 remains `UNVERIFIED`.
- The one-hour RPO and two-hour RTO are design targets, not measured results. P1.3 must run a reference restore drill.
- A production backup requires a separately mounted path and a separately held recovery key; a same-disk development backup cannot pass production recovery acceptance.
- V1 excludes AD, LDAP, OIDC and MFA. The proposed local password policy is therefore a single-factor baseline.
- FineReport plugin API, session and permission behavior remain a P2 external blocker; P1.0 does not make the plugin available.
- Real 2D / 3D Renderer formats, database-query Providers and management UI are outside P1.0.
- P1.0 produces a documentation/scripts candidate commit and rollback proof only; it does not produce a package, image, schema migration or runtime rollback artifact.
- P1.1 cannot start until the user explicitly accepts P1.0.
