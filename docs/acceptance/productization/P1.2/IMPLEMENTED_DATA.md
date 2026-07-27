# P1.2 Candidate Implemented Data

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Logical schema: `p1_control_plane_001`
- Latest migration: `002_three_screen_inventory`
- Scope: factual SQLite P1.2 subset; not the complete P1 target model
- Target source: [../../../product/contracts/DATA_MODEL.md](../../../product/contracts/DATA_MODEL.md)

P1.2 preserves accepted migration `001_initial_identity_device_trust` and its
checksum. Startup accepts only the exact ordered registry. An unknown,
reordered, missing, empty-over-existing-schema or checksum-tampered registry
fails closed.

## Added Tables

| Table | Candidate purpose |
| --- | --- |
| `sites` | Read-only physical Site inventory, timezone, status and resource revision |
| `screen_groups` | Site-owned convenience grouping and resource revision |
| `screen_instances` | Site/group ownership, display metadata, non-secret FVS reference and lifecycle state |
| `digital_human_instances` | One active inventory instance per screen |
| `runtime_bindings` | One same-screen inventory binding, generation `0`, null release/acknowledgement fields |
| `list_snapshots` | Expiring principal-bound ordered ID snapshots for pagination |

## Ownership And Uniqueness

- Composite foreign keys preserve tenant/deployment/Site/screen lineage.
- Site slugs are unique inside a deployment; group and screen slugs are unique
  inside a Site.
- A screen references at most one group.
- A screen has exactly one RuntimeBinding through supported initialization and
  create paths.
- A partial unique index permits at most one `ACTIVE` DigitalHumanInstance per
  screen.
- Existing and new DeviceEnrollment/DeviceCredentialFamily rows must resolve to
  one inventory screen with the same tenant/deployment/screen lineage.
- Inventory parents use restrictive foreign keys. The API exposes no P1.2
  delete operation, and SQLite rejects deletion that would cascade or orphan
  device/runtime history.

## Accepted-P1.1 Copy Upgrade

The copied upgrade uses SQLite's online backup API, restores the caller's
process-level root-key environment after use and propagates a native migration
failure before writing the target env file. It then:

1. verifies exact `001` registry/checksum and the existing control-plane schema;
2. rejects every legacy enrollment/family row not owned by the exact metadata
   fixture lineage;
3. creates the default Site and group;
4. creates Screen 1 with the exact accepted `fixture_screen_id`;
5. creates Screens 2 and 3 with server UUIDv7 IDs;
6. creates one distinct non-secret FVS label, active DigitalHumanInstance and
   RuntimeBinding for each screen;
7. appends one sanitized `THREE_SCREEN_INVENTORY_MIGRATED` event only after all
   checks pass; and
8. records migration `002` in the same transaction.

Failure rolls back the P1.2 schema, inventory rows, migration row and appended
audit event. The pre-002 copy stays usable by the accepted P1.1 runtime. Repeat
initialization is a no-op.

## Runtime States

- Initial fixture screens: FVS `UNVERIFIED`, device trust derived independently
  per screen, runtime `NOT_CONFIGURED_P1_3`.
- New screen: null digital-human pointer and `INVENTORY_INCOMPLETE`.
- First active DigitalHumanInstance: same-screen pointer and
  `NOT_CONFIGURED_P1_3`.
- `binding_generation` remains `0`; desired/applied release, acknowledgement
  marker and acknowledgement time remain null.

## Explicitly Absent

- No ConfigDraft, ConfigRelease, Publication, publication acknowledgement,
  product rollback or backup/restore tables.
- No SecretRecord/SecretVersion, FineReport identity, provider, Renderer or
  AvatarPackage data.
- No Site mutation, screen retirement/deletion, cross-Site move or group
  deletion.
- No PostgreSQL migration or certification.
