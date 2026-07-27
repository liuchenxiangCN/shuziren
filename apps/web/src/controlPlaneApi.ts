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
  inventory_status: 'INVENTORY_INCOMPLETE' | 'NOT_CONFIGURED_P1_3';
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

interface InventoryPage<T> {
  api_version: 'v1';
  items: T[];
  next_cursor?: string | null;
  snapshot_expires_at?: number | null;
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

export function randomIdempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}
