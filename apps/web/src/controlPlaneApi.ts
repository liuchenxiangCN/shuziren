const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:18080').replace(
  /\/$/,
  '',
);

let csrfToken = '';

export interface ControlPlaneUser {
  user_id: string;
  normalized_username: string;
  display_name: string;
  account_state: string;
  locked_until?: number | null;
  last_login_at?: number | null;
  etag: string;
  role_assignments: Array<{ role_id: string; scope_type: string; scope_id: string }>;
}

export interface ControlPlaneSession {
  auth_session_id: string;
  etag: string;
  profile: string;
  production_ready: boolean;
  user: {
    user_id: string;
    normalized_username: string;
    display_name: string;
    roles: string[];
    permissions: string[];
  };
}

export interface HighRiskAction {
  high_risk_action_id: string;
  operation_id: string;
  state: string;
  request_digest: string;
  reason: string;
  target_id?: string | null;
  initiator_user_id: string;
  approver_user_id?: string | null;
  requested_at: number;
  expires_at: number;
  etag: string;
}

export interface AuditEvent {
  sequence: number;
  event_id: string;
  event_type: string;
  actor_type: string;
  actor_id?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  outcome: string;
  reason?: string | null;
  details: Record<string, unknown>;
  event_hash: string;
  created_at: number;
}

export interface SiteInventory {
  site_id: string;
  tenant_id: string;
  deployment_id: string;
  slug: string;
  display_name: string;
  timezone: string;
  status: 'ACTIVE';
  screen_group_count: number;
  screen_count: number;
  resource_revision: number;
  etag: string;
}

export interface ScreenGroupInventory {
  screen_group_id: string;
  tenant_id: string;
  deployment_id: string;
  site_id: string;
  slug: string;
  display_name: string;
  member_screen_ids: string[];
  resource_revision: number;
  created_at: number;
  updated_at: number;
  etag: string;
}

export interface DigitalHumanInventory {
  digital_human_instance_id: string;
  screen_id: string;
  status: 'ACTIVE';
  resource_revision: number;
  etag: string;
}

export interface RuntimeBindingInventory {
  screen_id: string;
  digital_human_instance_id?: string | null;
  desired_release_target_id?: string | null;
  applied_release_target_id?: string | null;
  binding_generation: number;
  inventory_status:
    | 'INVENTORY_INCOMPLETE'
    | 'NOT_CONFIGURED_P1_3'
    | 'PUBLISH_PENDING'
    | 'ACTIVE';
  resource_revision: number;
  etag: string;
}

export interface ScreenInventory {
  screen_id: string;
  tenant_id: string;
  deployment_id: string;
  site_id: string;
  screen_group_id?: string | null;
  slug: string;
  display_name: string;
  fvs_binding_ref?: string | null;
  lifecycle_state: 'ACTIVE';
  fvs_status: 'UNVERIFIED';
  device_trust: {
    state: string;
    family_id?: string | null;
    credential_epoch?: number | null;
    family_etag?: string | null;
  };
  digital_human_instance?: DigitalHumanInventory | null;
  runtime_binding: RuntimeBindingInventory;
  resource_revision: number;
  created_at: number;
  updated_at: number;
  etag: string;
}

export interface InventoryPage<T> {
  api_version: 'v1';
  items: T[];
  next_cursor?: string | null;
  snapshot_expires_at?: number | null;
}

export type CapabilityKey =
  | 'dora'
  | 'knowledge'
  | 'direct_llm'
  | 'asr'
  | 'tts'
  | 'querying'
  | 'fvs_control';

export type CapabilityState =
  | 'disabled'
  | 'mock'
  | 'unverified'
  | 'available'
  | 'degraded';

export interface CapabilitySelection {
  enabled: boolean;
  primary_provider_id: string | null;
  fallback_provider_ids: string[];
  timeout_ms: number;
}

export type CapabilityProfileSpec = Record<CapabilityKey, CapabilitySelection>;

export interface CapabilityProviderDescriptor {
  provider_id: string;
  capability: CapabilityKey;
  state: Exclude<CapabilityState, 'disabled'>;
  adapter_kind: string;
  certification_state: string;
  permission_scope: string;
  supports_cancellation: boolean;
  streaming_mode: string;
  session_mode: string;
  external_calls_enabled: boolean;
  boundary: string;
}

export interface CapabilityProviderCatalog {
  api_version: 'v1';
  registry_version: 'p2_provider_registry_001';
  registry_hash: string;
  state_definitions: Record<CapabilityState, string>;
  fallback_policy: {
    allowed_reasons: string[];
    terminal_reasons: string[];
    require_permission_equivalence: boolean;
  };
  items: CapabilityProviderDescriptor[];
}

export interface CapabilityProfilePreset {
  preset_id: 'text_only' | 'mock_voice' | 'mock_presenter';
  name: string;
  description: string;
  spec: CapabilityProfileSpec;
  state_summary: Record<CapabilityKey, CapabilityState>;
  dependency_findings: Array<Record<string, unknown>>;
  activation_eligible: boolean;
  immutable: true;
}

export interface CapabilityProfilePresetCatalog {
  api_version: 'v1';
  schema_version: 'p2_capability_profile_v1';
  registry_version: 'p2_provider_registry_001';
  registry_hash: string;
  items: CapabilityProfilePreset[];
}

export interface CapabilityProfileVersion {
  profile_version_id: string;
  profile_id: string;
  version_number: number;
  schema_version: 'p2_capability_profile_v1';
  spec: CapabilityProfileSpec;
  content_hash: string;
  provider_registry_version: 'p2_provider_registry_001';
  provider_registry_hash: string;
  state_summary: Record<CapabilityKey, CapabilityState>;
  dependency_findings: Array<Record<string, unknown>>;
  activation_eligible: boolean;
  created_by_user_id: string;
  created_at: number;
  immutable: true;
}

export interface CapabilityProfile {
  profile_id: string;
  site_id: string;
  name: string;
  description: string;
  source_preset_id?: string | null;
  head_version_id: string;
  head_version_number: number;
  head_version: CapabilityProfileVersion;
  resource_revision: number;
  created_at: number;
  updated_at: number;
  etag: string;
}

export interface CapabilityProfileAssignment {
  profile_id: string;
  profile_version_id: string;
  version_number: number;
  profile_name?: string;
  content_hash: string;
  provider_registry_version: string;
  provider_registry_hash: string;
  state_summary: Record<CapabilityKey, CapabilityState>;
  activation_eligible: boolean;
}

export interface CapabilityResolutionSnapshot {
  schema_version: 'p2_capability_profile_v1';
  screen_id: string;
  digital_human_instance_id: string;
  profile_id: string;
  profile_version_id: string;
  version_number: number;
  content_hash: string;
  provider_registry_version: 'p2_provider_registry_001';
  provider_registry_hash: string;
  spec: CapabilityProfileSpec;
  state_summary: Record<CapabilityKey, CapabilityState>;
  dependency_findings: Array<Record<string, unknown>>;
  activation_eligible: boolean;
  capability_envelope_hash: string;
  immutable: true;
}

export interface CapabilityReleaseResolution {
  state: string;
  release_id: string | null;
  release_target_id: string | null;
  binding_generation: number;
  profile_snapshot?: CapabilityResolutionSnapshot | null;
}

export interface ScreenEffectiveCapabilities {
  screen_id: string;
  digital_human_instance_id?: string | null;
  binding_generation: number;
  state: string;
  desired?: CapabilityReleaseResolution | null;
  applied?: CapabilityReleaseResolution | null;
  effective?: CapabilityResolutionSnapshot | null;
}

export type QueryEngine = 'EXCEL' | 'MYSQL' | 'ORACLE' | 'POSTGRESQL';

export interface QueryParameterDefinition {
  name: string;
  type: 'string' | 'integer' | 'number' | 'boolean' | 'date';
  required: boolean;
}

export interface QuerySource {
  api_version: 'v1';
  source_id: string;
  source_version_id: string;
  site_id: string;
  display_name: string;
  engine: QueryEngine;
  state: 'ACTIVE' | 'DISABLED';
  qualification: {
    state: 'UNVERIFIED' | 'AVAILABLE' | 'FAILED';
    code?: string | null;
    last_tested_at?: number | null;
    deployment_local_evidence: boolean;
    product_certification: 'UNVERIFIED';
  };
  read_only_account_confirmed: boolean;
  credential: {
    configured: boolean;
    fingerprint_suffix?: string | null;
    sensitive: true;
    readable: false;
  };
  workbook: { configured: boolean; content_readable: false };
  config_hash: string;
  resource_revision: number;
  etag: string;
  immutable_definition: true;
}

export interface QueryDataset {
  api_version: 'v1';
  dataset_id: string;
  dataset_version_id: string;
  site_id: string;
  display_name: string;
  state: 'ACTIVE' | 'DISABLED';
  source: {
    source_id: string;
    source_version_id: string;
    display_name: string;
    engine: QueryEngine;
    state: 'ACTIVE' | 'DISABLED';
    qualification_state: 'UNVERIFIED' | 'AVAILABLE' | 'FAILED';
  };
  schema_version: 'p2_controlled_dataset_v1';
  metric_definition: string;
  time_scope_description: string;
  freshness_label: string;
  parameter_schema: QueryParameterDefinition[];
  output_fields: string[];
  definition: {
    kind: 'EXCEL_FILTER' | 'DATABASE_SELECT';
    worksheet_configured: boolean;
    query_template_configured: boolean;
    query_template_readable: false;
    relation_count: number;
  };
  definition_hash: string;
  row_limit: number;
  timeout_ms: number;
  resource_revision: number;
  etag: string;
  immutable_definition: true;
}

export interface QueryDatasetRef {
  dataset_id: string;
  dataset_version_id: string;
  dataset_label: string;
  definition_hash: string;
  metric_definition: string;
  time_scope_description: string;
  freshness_label: string;
  parameter_schema: QueryParameterDefinition[];
  output_fields: string[];
  row_limit: number;
  timeout_ms: number;
  source_id: string;
  source_version_id: string;
  source_label: string;
  source_config_hash: string;
  engine: QueryEngine;
}

export interface RuntimeQueryDataset {
  dataset_id: string;
  dataset_version_id: string;
  label: string;
  metric_definition: string;
  time_scope_description: string;
  freshness_label: string;
  parameter_schema: QueryParameterDefinition[];
  output_fields: string[];
  row_limit: number;
  timeout_ms: number;
  source: {
    source_id: string;
    engine: QueryEngine;
    label: string;
    qualification: 'DEPLOYMENT_LOCAL_AVAILABLE';
    product_certification: 'UNVERIFIED';
  };
}

export interface QueryExecution {
  api_version: 'v1';
  execution_id: string;
  request_id: string;
  state: string;
  screen_id?: string;
  dataset_id?: string;
  source?: Record<string, unknown>;
  dataset?: Record<string, unknown>;
  requested_time_scope?: Record<string, unknown>;
  permission_subject?: Record<string, unknown>;
  latency_ms?: number;
  fields?: string[];
  row_count?: number;
  rows?: Array<Record<string, unknown>>;
  error?: { code: string; message: string; retryable: boolean };
}

export type QueryExecutionState =
  | 'QUEUED'
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'TIMED_OUT'
  | 'CANCELLED'
  | 'REJECTED_BACKPRESSURE';

export interface ScreenExecutionListItem {
  execution_id: string;
  dataset_id: string;
  dataset_label: string | null;
  state: QueryExecutionState;
  request_id: string;
  latency_ms: number | null;
  row_count: number | null;
  result_retained: boolean;
  error: { code: string; message: string; retryable: boolean } | null;
  created_at: number;
  terminal_at: number | null;
}

export interface ScreenQueueStatus {
  api_version: 'v1';
  screen_instance_id: string;
  screen: {
    inflight: number;
    per_screen_limit: number;
  };
  capacity: {
    global_inflight_limit: number;
    per_screen_inflight_limit: number;
    executor_workers: number;
    retained_terminal_jobs: number;
  };
  counters: {
    rejected_backpressure: number;
  };
}

export type DrillCapability = CapabilityKey;

export type DrillSignal =
  | 'timeout'
  | 'unavailable'
  | 'unsupported'
  | 'permission_denied'
  | 'invalid_request'
  | 'unauthorized_template'
  | 'cancelled'
  | 'backpressure';

export interface ResilienceDrill {
  api_version: 'v1';
  drill_id: string;
  screen_instance_id: string;
  capability: DrillCapability;
  signal: DrillSignal;
  primary_provider_id: string | null;
  fallback_provider_ids: string[];
  permission_equivalent: boolean | null;
  provider_execution_started: boolean;
  queue_admission: 'N/A' | 'REJECTED';
  decision: string | null;
  resolved_provider_id: string | null;
  outcome:
    | 'FALLBACK_RESOLVED'
    | 'TERMINAL_NO_FALLBACK'
    | 'CAPABILITY_DISABLED'
    | 'NO_FALLBACK_CONFIGURED';
  terminal: boolean;
  fallback_allowed: boolean;
  created_at: number;
  latency_ms: number;
}

export interface ConfigDraft {
  draft_id: string;
  target: {
    type: 'SCREEN' | 'SCREEN_GROUP';
    screen_id?: string | null;
    screen_group_id?: string | null;
  };
  schema_version: 'p1_screen_config_v1';
  spec: Record<string, string>;
  content_hash: string;
  state: string;
  draft_revision: number;
  resource_revision: number;
  validation?: {
    outcome: string;
    findings: Array<Record<string, unknown>>;
    fingerprint_hash: string;
  } | null;
  preview?: {
    outcome: 'MOCK_PASSED';
    evidence: Record<string, unknown>;
    fingerprint_hash: string;
  } | null;
  approval?: {
    decision: string;
    approver_user_id: string;
    last_editor_user_id: string;
    reason: string;
  } | null;
  capability_profile?: CapabilityProfileAssignment | null;
  query_datasets?: {
    schema_version: 'p2_query_snapshot_v1';
    dataset_refs: QueryDatasetRef[];
    assignment_hash: string;
    immutable: true;
  } | null;
  etag: string;
}

export interface ConfigReleaseTarget {
  release_target_id: string;
  release_id: string;
  screen_id: string;
  effective_config: Record<string, string>;
  content_hash: string;
  capability_snapshot?: CapabilityResolutionSnapshot | null;
  query_snapshot?: {
    schema_version: 'p2_query_snapshot_v1';
    querying_enabled: boolean;
    assignment_hash: string;
    dataset_refs: QueryDatasetRef[];
    query_snapshot_hash: string;
    immutable: true;
  } | null;
  rollback_source_release_id?: string | null;
  rollback_source_target_id?: string | null;
  immutable: true;
}

export interface ConfigRelease {
  release_id: string;
  release_sequence: number;
  creation_kind: 'NORMAL' | 'ROLLBACK';
  target_set_hash: string;
  targets: ConfigReleaseTarget[];
  reason: string;
  etag: string;
  immutable: true;
}

export interface Publication {
  publication_id: string;
  release_id: string;
  screen_group_id?: string | null;
  state: string;
  immutable_plan: true;
  targets: Array<{
    screen_id: string;
    release_target_id: string;
    state: string;
    expected_binding_generation: number;
    etag: string;
  }>;
}

export interface BackupRecord {
  backup_id: string;
  state: 'VERIFIED';
  manifest_hash: string;
  ciphertext_hash: string;
  recovery_encryption_key_id: string;
  logical_schema_version: string;
  migration_versions: string[];
  safe_row_counts: Record<string, number>;
  ciphertext_size: number;
  duration_ms: number;
  recovery_key_in_bundle: false;
  production_recovery_certified: false;
}

export interface RestorePlan {
  restore_plan_id: string;
  backup_id: string;
  state: 'READY' | 'EXECUTED' | 'ABORTED' | 'FAILED';
  recovery_source_mode: 'ONLINE_ACTIVE_STORE';
  findings: Record<string, unknown>;
  etag: string;
}

export class ControlPlaneApiError extends Error {
  status: number;
  code: string;
  retryable: boolean;

  constructor(status: number, code: string, message: string, retryable = false) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryable = retryable;
  }
}

async function controlPlaneRequest<T>(
  path: string,
  init: RequestInit = {},
  options: { csrf?: boolean } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (options.csrf) {
    if (!csrfToken) throw new ControlPlaneApiError(403, 'CSRF_REQUIRED', '请刷新会话后重试。');
    headers.set('X-CSRF-Token', csrfToken);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers,
  });
  const responseCsrf = response.headers.get('X-CSRF-Token');
  if (responseCsrf) csrfToken = responseCsrf;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) csrfToken = '';
    throw new ControlPlaneApiError(
      response.status,
      payload?.error?.code || `HTTP_${response.status}`,
      payload?.error?.message || `HTTP ${response.status}`,
      Boolean(payload?.error?.retryable),
    );
  }
  return payload as T;
}

export async function signIn(username: string, password: string): Promise<ControlPlaneSession> {
  return controlPlaneRequest<ControlPlaneSession>('/api/v1/control-plane/auth/sessions', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function loadSession(): Promise<ControlPlaneSession> {
  await controlPlaneRequest<ControlPlaneSession>('/api/v1/control-plane/auth/session');
  return controlPlaneRequest<ControlPlaneSession>(
    '/api/v1/control-plane/auth/session:refresh-csrf',
    { method: 'POST' },
  );
}

export async function reauthenticate(
  password: string,
  sessionEtag: string,
): Promise<ControlPlaneSession> {
  return controlPlaneRequest<ControlPlaneSession>(
    '/api/v1/control-plane/auth/session:reauthenticate',
    {
      method: 'POST',
      headers: {
        'Idempotency-Key': randomIdempotencyKey('reauthenticate'),
        'If-Match': sessionEtag,
      },
      body: JSON.stringify({ password }),
    },
    { csrf: true },
  );
}

export async function signOut(): Promise<void> {
  await controlPlaneRequest('/api/v1/control-plane/auth/session', { method: 'DELETE' }, { csrf: true });
  csrfToken = '';
}

export function listUsers(): Promise<{ items: ControlPlaneUser[] }> {
  return controlPlaneRequest('/api/v1/control-plane/users');
}

export function listRoleDefinitions(): Promise<{
  items: Array<{ role_id: string; permissions: string[]; catalog_version: string }>;
}> {
  return controlPlaneRequest('/api/v1/control-plane/role-definitions');
}

export function listSites(): Promise<InventoryPage<SiteInventory>> {
  return controlPlaneRequest('/api/v1/control-plane/sites');
}

export function listScreenGroups(): Promise<InventoryPage<ScreenGroupInventory>> {
  return controlPlaneRequest('/api/v1/control-plane/screen-groups');
}

export function listScreenInstances(): Promise<InventoryPage<ScreenInventory>> {
  return controlPlaneRequest('/api/v1/control-plane/screen-instances');
}

export function listCapabilityProviders(): Promise<CapabilityProviderCatalog> {
  return controlPlaneRequest('/api/v1/control-plane/capability-providers');
}

export function listCapabilityProfilePresets(): Promise<CapabilityProfilePresetCatalog> {
  return controlPlaneRequest('/api/v1/control-plane/capability-profile-presets');
}

export function listCapabilityProfiles(): Promise<InventoryPage<CapabilityProfile>> {
  return controlPlaneRequest('/api/v1/control-plane/capability-profiles');
}

export function getCapabilityProfile(profileId: string): Promise<CapabilityProfile> {
  return controlPlaneRequest(
    `/api/v1/control-plane/capability-profiles/${encodeURIComponent(profileId)}`,
  );
}

export function createCapabilityProfile(payload: {
  site_id: string;
  name: string;
  description: string;
  source_preset_id: CapabilityProfilePreset['preset_id'];
}): Promise<CapabilityProfile> {
  return controlPlaneRequest(
    '/api/v1/control-plane/capability-profiles',
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('capability-profile-create') },
      body: JSON.stringify(payload),
    },
    { csrf: true },
  );
}

export function createCapabilityProfileVersion(
  profile: CapabilityProfile,
  spec: CapabilityProfileSpec,
): Promise<CapabilityProfile> {
  return controlPlaneRequest(
    `/api/v1/control-plane/capability-profiles/${encodeURIComponent(profile.profile_id)}/versions`,
    {
      method: 'POST',
      headers: {
        'If-Match': profile.etag,
        'Idempotency-Key': randomIdempotencyKey('capability-profile-version-create'),
      },
      body: JSON.stringify({ spec }),
    },
    { csrf: true },
  );
}

export function assignCapabilityProfileToDraft(
  draft: ConfigDraft,
  profileVersionId: string,
): Promise<ConfigDraft> {
  return controlPlaneRequest(
    `/api/v1/control-plane/config-drafts/${encodeURIComponent(draft.draft_id)}/capability-profile`,
    {
      method: 'PUT',
      headers: {
        'If-Match': draft.etag,
        'Idempotency-Key': randomIdempotencyKey('draft-capability-profile-assign'),
      },
      body: JSON.stringify({ profile_version_id: profileVersionId }),
    },
    { csrf: true },
  );
}

export function getScreenEffectiveCapabilities(
  screenId: string,
): Promise<ScreenEffectiveCapabilities> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/effective-capabilities`,
  );
}

export function listQuerySources(): Promise<InventoryPage<QuerySource>> {
  return controlPlaneRequest('/api/v1/control-plane/query-sources');
}

export function createQuerySource(payload: {
  site_id: string;
  display_name: string;
  engine: QueryEngine;
  read_only_account_confirmed: boolean;
  connection?: {
    host: string;
    port: number;
    database: string;
    username: string;
    password: string;
  };
  excel_file_name?: string;
  excel_workbook_base64?: string;
}): Promise<QuerySource> {
  return controlPlaneRequest(
    '/api/v1/control-plane/query-sources',
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('query-source-create') },
      body: JSON.stringify(payload),
    },
    { csrf: true },
  );
}

export function testQuerySource(source: QuerySource): Promise<{
  source_id: string;
  qualification_state: 'AVAILABLE' | 'FAILED';
  code: string;
  message: string;
  latency_ms: number;
}> {
  return controlPlaneRequest(
    `/api/v1/control-plane/query-sources/${encodeURIComponent(source.source_id)}:test`,
    {
      method: 'POST',
      headers: {
        'If-Match': source.etag,
        'Idempotency-Key': randomIdempotencyKey('query-source-test'),
      },
    },
    { csrf: true },
  );
}

export function disableQuerySource(source: QuerySource): Promise<QuerySource> {
  return controlPlaneRequest(
    `/api/v1/control-plane/query-sources/${encodeURIComponent(source.source_id)}:disable`,
    {
      method: 'POST',
      headers: {
        'If-Match': source.etag,
        'Idempotency-Key': randomIdempotencyKey('query-source-disable'),
      },
    },
    { csrf: true },
  );
}

export function listQueryDatasets(): Promise<InventoryPage<QueryDataset>> {
  return controlPlaneRequest('/api/v1/control-plane/query-datasets');
}

export function createQueryDataset(payload: {
  source_id: string;
  display_name: string;
  metric_definition: string;
  time_scope_description: string;
  freshness_label: string;
  parameters: QueryParameterDefinition[];
  output_fields: string[];
  definition: {
    worksheet?: string;
    parameter_columns?: Record<string, string>;
    query_template?: string;
    allowed_relations?: string[];
  };
  row_limit: number;
  timeout_ms: number;
}): Promise<QueryDataset> {
  return controlPlaneRequest(
    '/api/v1/control-plane/query-datasets',
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('query-dataset-create') },
      body: JSON.stringify(payload),
    },
    { csrf: true },
  );
}

export function disableQueryDataset(dataset: QueryDataset): Promise<QueryDataset> {
  return controlPlaneRequest(
    `/api/v1/control-plane/query-datasets/${encodeURIComponent(dataset.dataset_id)}:disable`,
    {
      method: 'POST',
      headers: {
        'If-Match': dataset.etag,
        'Idempotency-Key': randomIdempotencyKey('query-dataset-disable'),
      },
    },
    { csrf: true },
  );
}

export function assignQueryDatasetsToDraft(
  draft: ConfigDraft,
  datasetVersionIds: string[],
): Promise<ConfigDraft> {
  return controlPlaneRequest(
    `/api/v1/control-plane/config-drafts/${encodeURIComponent(draft.draft_id)}/query-datasets`,
    {
      method: 'PUT',
      headers: {
        'If-Match': draft.etag,
        'Idempotency-Key': randomIdempotencyKey('draft-query-datasets-assign'),
      },
      body: JSON.stringify({ dataset_version_ids: datasetVersionIds }),
    },
    { csrf: true },
  );
}

export function listScreenQueryDatasets(screenId: string): Promise<{
  api_version: 'v1';
  screen_id: string;
  release_target_id: string;
  query_snapshot_hash: string;
  provider: 'controlled_query';
  state: 'available';
  items: RuntimeQueryDataset[];
}> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/query-datasets`,
  );
}

export function startScreenQuery(
  screenId: string,
  datasetId: string,
  parameters: Record<string, unknown>,
): Promise<QueryExecution> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/query-datasets/${encodeURIComponent(datasetId)}:execute`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('controlled-query-start') },
      body: JSON.stringify({ parameters }),
    },
    { csrf: true },
  );
}

export function getScreenQueryExecution(
  screenId: string,
  executionId: string,
): Promise<QueryExecution> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/query-executions/${encodeURIComponent(executionId)}`,
  );
}

export function cancelScreenQueryExecution(
  screenId: string,
  executionId: string,
): Promise<QueryExecution> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/query-executions/${encodeURIComponent(executionId)}:cancel`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('controlled-query-cancel') },
    },
    { csrf: true },
  );
}

export function listScreenQueryExecutions(
  screenId: string,
  limit = 50,
): Promise<{
  api_version: 'v1';
  screen_instance_id: string;
  items: ScreenExecutionListItem[];
}> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/query-executions?limit=${limit}`,
  );
}

export function getScreenQueueStatus(screenId: string): Promise<ScreenQueueStatus> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/queue-status`,
  );
}

export function startResilienceDrill(
  screenId: string,
  capability: DrillCapability,
  signal: DrillSignal,
): Promise<ResilienceDrill> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/resilience-drills`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('resilience-drill-start') },
      body: JSON.stringify({ capability, signal }),
    },
    { csrf: true },
  );
}

export function getResilienceDrill(
  screenId: string,
  drillId: string,
): Promise<ResilienceDrill> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/resilience-drills/${encodeURIComponent(drillId)}`,
  );
}

export function getRuntimeBinding(screenId: string): Promise<RuntimeBindingInventory> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/runtime-binding`,
  );
}

export function createScreenGroup(
  siteId: string,
  payload: { slug: string; display_name: string },
): Promise<ScreenGroupInventory> {
  return controlPlaneRequest(
    `/api/v1/control-plane/sites/${encodeURIComponent(siteId)}/screen-groups`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('create-screen-group') },
      body: JSON.stringify(payload),
    },
    { csrf: true },
  );
}

export function updateScreenGroup(
  group: ScreenGroupInventory,
  payload: { display_name?: string; slug?: string; member_screen_ids?: string[] },
): Promise<ScreenGroupInventory> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-groups/${encodeURIComponent(group.screen_group_id)}`,
    {
      method: 'PATCH',
      headers: { 'If-Match': group.etag },
      body: JSON.stringify(payload),
    },
    { csrf: true },
  );
}

export function createScreenInstance(
  siteId: string,
  payload: { slug: string; display_name: string; fvs_binding_ref?: string | null },
): Promise<ScreenInventory> {
  return controlPlaneRequest(
    `/api/v1/control-plane/sites/${encodeURIComponent(siteId)}/screen-instances`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('create-screen') },
      body: JSON.stringify(payload),
    },
    { csrf: true },
  );
}

export function updateScreenInstance(
  screen: ScreenInventory,
  payload: { slug?: string; display_name?: string; fvs_binding_ref?: string | null },
): Promise<ScreenInventory> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screen.screen_id)}`,
    {
      method: 'PATCH',
      headers: { 'If-Match': screen.etag },
      body: JSON.stringify(payload),
    },
    { csrf: true },
  );
}

export function createDigitalHumanInstance(
  screenId: string,
): Promise<DigitalHumanInventory> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/digital-human-instances`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('create-digital-human') },
      body: JSON.stringify({}),
    },
    { csrf: true },
  );
}

export function createUser(
  payload: { normalized_username: string; display_name: string; reason: string },
  idempotencyKey: string,
  actionId = '',
): Promise<Record<string, unknown>> {
  const headers: Record<string, string> = { 'Idempotency-Key': idempotencyKey };
  if (actionId) headers['High-Risk-Action-ID'] = actionId;
  return controlPlaneRequest(
    '/api/v1/control-plane/users',
    { method: 'POST', headers, body: JSON.stringify(payload) },
    { csrf: true },
  );
}

export function listPendingActions(): Promise<{ items: HighRiskAction[] }> {
  return controlPlaneRequest('/api/v1/control-plane/high-risk-actions');
}

export function approveAction(action: HighRiskAction, reason: string): Promise<HighRiskAction> {
  return controlPlaneRequest(
    `/api/v1/control-plane/high-risk-actions/${encodeURIComponent(action.high_risk_action_id)}:approve`,
    {
      method: 'POST',
      headers: {
        'Idempotency-Key': randomIdempotencyKey('approve'),
        'If-Match': action.etag,
      },
      body: JSON.stringify({ expected_request_digest: action.request_digest, reason }),
    },
    { csrf: true },
  );
}

export function rejectAction(action: HighRiskAction, reason: string): Promise<HighRiskAction> {
  return controlPlaneRequest(
    `/api/v1/control-plane/high-risk-actions/${encodeURIComponent(action.high_risk_action_id)}:reject`,
    {
      method: 'POST',
      headers: {
        'Idempotency-Key': randomIdempotencyKey('reject'),
        'If-Match': action.etag,
      },
      body: JSON.stringify({ expected_request_digest: action.request_digest, reason }),
    },
    { csrf: true },
  );
}

export function issueEnrollment(
  screenId: string,
  reason: string,
  idempotencyKey: string,
  actionId = '',
): Promise<Record<string, any>> {
  const headers: Record<string, string> = { 'Idempotency-Key': idempotencyKey };
  if (actionId) headers['High-Risk-Action-ID'] = actionId;
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/device-enrollments`,
    { method: 'POST', headers, body: JSON.stringify({ reason }) },
    { csrf: true },
  );
}

export function claimEnrollment(
  enrollmentToken: string,
  idempotencyKey: string,
): Promise<Record<string, any>> {
  return controlPlaneRequest('/api/v1/device/enrollments:claim', {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ enrollment_token: enrollmentToken }),
  });
}

export function rotateCredential(
  credential: string,
  idempotencyKey: string,
): Promise<Record<string, any>> {
  return controlPlaneRequest('/api/v1/device/credentials:rotate', {
    method: 'POST',
    headers: {
      Authorization: `DeviceCredential ${credential}`,
      'Idempotency-Key': idempotencyKey,
    },
  });
}

export function activateCredential(credential: string): Promise<Record<string, any>> {
  return controlPlaneRequest('/api/v1/device/runtime-binding', {
    headers: { Authorization: `DeviceCredential ${credential}` },
  });
}

export function getCredentialMetadata(
  screenId: string,
  credentialId: string,
): Promise<Record<string, any>> {
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/device-credentials/${encodeURIComponent(credentialId)}`,
  );
}

export function revokeCredential(
  screenId: string,
  credentialId: string,
  payload: { expected_credential_epoch: number; reason: string },
  familyEtag: string,
  idempotencyKey: string,
  actionId = '',
): Promise<Record<string, any>> {
  const headers: Record<string, string> = {
    'Idempotency-Key': idempotencyKey,
    'If-Match': familyEtag,
  };
  if (actionId) headers['High-Risk-Action-ID'] = actionId;
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/device-credentials/${encodeURIComponent(credentialId)}:revoke`,
    { method: 'POST', headers, body: JSON.stringify(payload) },
    { csrf: true },
  );
}

export function listAuditEvents(): Promise<{ items: AuditEvent[] }> {
  return controlPlaneRequest('/api/v1/control-plane/audit-events?limit=100');
}

export function createConfigDraft(
  targetType: 'SCREEN' | 'SCREEN_GROUP',
  targetId: string,
): Promise<ConfigDraft> {
  return controlPlaneRequest(
    '/api/v1/control-plane/config-drafts',
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('draft-create') },
      body: JSON.stringify({
        target_type: targetType,
        target_id: targetId,
        schema_version: 'p1_screen_config_v1',
      }),
    },
    { csrf: true },
  );
}

export function getConfigDraft(draftId: string): Promise<ConfigDraft> {
  return controlPlaneRequest(
    `/api/v1/control-plane/config-drafts/${encodeURIComponent(draftId)}`,
  );
}

export function replaceConfigDraftSpec(
  draft: ConfigDraft,
  payload: { welcome_text: string; fvs_binding_ref: string },
): Promise<ConfigDraft> {
  return controlPlaneRequest(
    `/api/v1/control-plane/config-drafts/${encodeURIComponent(draft.draft_id)}/spec`,
    {
      method: 'PUT',
      headers: { 'If-Match': draft.etag },
      body: JSON.stringify(payload),
    },
    { csrf: true },
  );
}

export function transitionConfigDraft(
  draft: ConfigDraft,
  operation: 'validate' | 'preview' | 'submit-for-approval' | 'revise' | 'abandon',
): Promise<ConfigDraft> {
  return controlPlaneRequest(
    `/api/v1/control-plane/config-drafts/${encodeURIComponent(draft.draft_id)}:${operation}`,
    {
      method: 'POST',
      headers: {
        'If-Match': draft.etag,
        'Idempotency-Key': randomIdempotencyKey(`draft-${operation}`),
      },
    },
    { csrf: true },
  );
}

export function decideConfigDraft(
  draft: ConfigDraft,
  decision: 'approve' | 'reject',
  reason: string,
): Promise<ConfigDraft> {
  return controlPlaneRequest(
    `/api/v1/control-plane/config-drafts/${encodeURIComponent(draft.draft_id)}:${decision}`,
    {
      method: 'POST',
      headers: {
        'If-Match': draft.etag,
        'Idempotency-Key': randomIdempotencyKey(`draft-${decision}`),
      },
      body: JSON.stringify({ reason }),
    },
    { csrf: true },
  );
}

export function createConfigRelease(
  draft: ConfigDraft,
  reason: string,
): Promise<ConfigRelease> {
  return controlPlaneRequest(
    `/api/v1/control-plane/config-drafts/${encodeURIComponent(draft.draft_id)}:release`,
    {
      method: 'POST',
      headers: {
        'If-Match': draft.etag,
        'Idempotency-Key': randomIdempotencyKey('release-create'),
      },
      body: JSON.stringify({ reason }),
    },
    { csrf: true },
  );
}

export function getConfigRelease(releaseId: string): Promise<ConfigRelease> {
  return controlPlaneRequest(
    `/api/v1/control-plane/config-releases/${encodeURIComponent(releaseId)}`,
  );
}

export function publishReleaseToScreen(
  screenId: string,
  release: ConfigRelease,
  target: ConfigReleaseTarget,
  binding: RuntimeBindingInventory,
  reason: string,
  actionId = '',
): Promise<Record<string, any>> {
  const headers: Record<string, string> = {
    'If-Match': binding.etag,
    'Idempotency-Key': randomIdempotencyKey(actionId ? 'publish-execute' : 'publish-request'),
  };
  if (actionId) headers['High-Risk-Action-ID'] = actionId;
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/publications`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        release_id: release.release_id,
        release_target_id: target.release_target_id,
        expected_binding_generation: binding.binding_generation,
        reason,
      }),
    },
    { csrf: true },
  );
}

export function publishReleaseToGroup(
  group: ScreenGroupInventory,
  release: ConfigRelease,
  bindings: RuntimeBindingInventory[],
  reason: string,
  actionId = '',
): Promise<Record<string, any>> {
  const targetMap = new Map(release.targets.map((target) => [target.screen_id, target]));
  const headers: Record<string, string> = {
    'If-Match': group.etag,
    'Idempotency-Key': randomIdempotencyKey(
      actionId ? 'group-publish-execute' : 'group-publish-request',
    ),
  };
  if (actionId) headers['High-Risk-Action-ID'] = actionId;
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-groups/${encodeURIComponent(group.screen_group_id)}/publications`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        release_id: release.release_id,
        targets: bindings.map((binding) => ({
          screen_id: binding.screen_id,
          release_target_id: targetMap.get(binding.screen_id)?.release_target_id,
          runtime_if_match: binding.etag,
          expected_binding_generation: binding.binding_generation,
        })),
        reason,
      }),
    },
    { csrf: true },
  );
}

export function rollbackScreenRelease(
  screenId: string,
  sourceReleaseTargetId: string,
  binding: RuntimeBindingInventory,
  reason: string,
  actionId = '',
): Promise<Record<string, any>> {
  const headers: Record<string, string> = {
    'If-Match': binding.etag,
    'Idempotency-Key': randomIdempotencyKey(actionId ? 'rollback-execute' : 'rollback-request'),
  };
  if (actionId) headers['High-Risk-Action-ID'] = actionId;
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-instances/${encodeURIComponent(screenId)}/rollbacks`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        source_release_target_id: sourceReleaseTargetId,
        expected_binding_generation: binding.binding_generation,
        reason,
      }),
    },
    { csrf: true },
  );
}

export function rollbackGroupRelease(
  group: ScreenGroupInventory,
  sourceRelease: ConfigRelease,
  bindings: RuntimeBindingInventory[],
  reason: string,
  actionId = '',
): Promise<Record<string, any>> {
  const sourceMap = new Map(
    sourceRelease.targets.map((target) => [target.screen_id, target]),
  );
  const missingSource = bindings.find(
    (binding) => !sourceMap.has(binding.screen_id),
  );
  if (missingSource) {
    return Promise.reject(
      new Error(
        `回退源不包含屏幕 ${missingSource.screen_id}，请重新加载完整的组 Release`,
      ),
    );
  }
  const headers: Record<string, string> = {
    'If-Match': group.etag,
    'Idempotency-Key': randomIdempotencyKey(
      actionId ? 'group-rollback-execute' : 'group-rollback-request',
    ),
  };
  if (actionId) headers['High-Risk-Action-ID'] = actionId;
  return controlPlaneRequest(
    `/api/v1/control-plane/screen-groups/${encodeURIComponent(group.screen_group_id)}/rollbacks`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        source_targets: bindings.map((binding) => ({
          screen_id: binding.screen_id,
          source_release_target_id: sourceMap.get(binding.screen_id)!.release_target_id,
        })),
        targets: bindings.map((binding) => ({
          screen_id: binding.screen_id,
          release_target_id: sourceMap.get(binding.screen_id)!.release_target_id,
          runtime_if_match: binding.etag,
          expected_binding_generation: binding.binding_generation,
        })),
        reason,
      }),
    },
    { csrf: true },
  );
}

export function getStorageProfile(): Promise<Record<string, any>> {
  return controlPlaneRequest('/api/v1/control-plane/storage-profile');
}

export function createBackup(reason: string): Promise<BackupRecord> {
  return controlPlaneRequest(
    '/api/v1/control-plane/backups',
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('backup-create') },
      body: JSON.stringify({ reason }),
    },
    { csrf: true },
  );
}

export function verifyBackup(backupId: string): Promise<Record<string, any>> {
  return controlPlaneRequest(
    `/api/v1/control-plane/backups/${encodeURIComponent(backupId)}:verify`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('backup-verify') },
    },
    { csrf: true },
  );
}

export function createRestorePlan(backupId: string): Promise<RestorePlan> {
  return controlPlaneRequest(
    '/api/v1/control-plane/restore-plans',
    {
      method: 'POST',
      headers: { 'Idempotency-Key': randomIdempotencyKey('restore-plan') },
      body: JSON.stringify({ backup_id: backupId }),
    },
    { csrf: true },
  );
}

export function executeRestorePlan(
  plan: RestorePlan,
  reason: string,
  actionId = '',
): Promise<Record<string, any>> {
  const headers: Record<string, string> = {
    'If-Match': plan.etag,
    'Idempotency-Key': randomIdempotencyKey(
      actionId ? 'restore-execute' : 'restore-request',
    ),
  };
  if (actionId) headers['High-Risk-Action-ID'] = actionId;
  return controlPlaneRequest(
    `/api/v1/control-plane/restore-plans/${encodeURIComponent(plan.restore_plan_id)}:execute`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        confirmation: 'RESTORE_VERIFIED_BACKUP',
        reason,
      }),
    },
    { csrf: true },
  );
}

export function randomIdempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}
