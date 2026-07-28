<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  activateCredential,
  approveAction,
  assignCapabilityProfileToDraft,
  claimEnrollment,
  ControlPlaneApiError,
  createBackup,
  createCapabilityProfile,
  createCapabilityProfileVersion,
  createConfigDraft,
  createConfigRelease,
  createDigitalHumanInstance,
  createRestorePlan,
  createScreenGroup,
  createScreenInstance,
  createUser,
  decideConfigDraft,
  executeRestorePlan,
  getConfigDraft,
  getConfigRelease,
  getCapabilityProfile,
  getCredentialMetadata,
  getRuntimeBinding,
  getScreenEffectiveCapabilities,
  getStorageProfile,
  issueEnrollment,
  listAuditEvents,
  listCapabilityProfilePresets,
  listCapabilityProfiles,
  listCapabilityProviders,
  listPendingActions,
  listRoleDefinitions,
  listScreenGroups,
  listScreenInstances,
  listSites,
  listUsers,
  loadSession,
  publishReleaseToGroup,
  publishReleaseToScreen,
  randomIdempotencyKey,
  reauthenticate,
  rejectAction,
  replaceConfigDraftSpec,
  revokeCredential,
  rollbackGroupRelease,
  rollbackScreenRelease,
  rotateCredential,
  signIn,
  signOut,
  type AuditEvent,
  type BackupRecord,
  type CapabilityKey,
  type CapabilityProfile,
  type CapabilityProfilePreset,
  type CapabilityProfileSpec,
  type CapabilityProfileVersion,
  type CapabilityProviderCatalog,
  type CapabilityState,
  type ConfigDraft,
  type ConfigRelease,
  type ControlPlaneSession,
  type ControlPlaneUser,
  type HighRiskAction,
  type RestorePlan,
  type ScreenGroupInventory,
  type ScreenEffectiveCapabilities,
  type ScreenInventory,
  type SiteInventory,
  transitionConfigDraft,
  updateScreenGroup,
  updateScreenInstance,
  verifyBackup,
} from './controlPlaneApi';

type View =
  | 'inventory'
  | 'capabilities'
  | 'releases'
  | 'users'
  | 'approvals'
  | 'devices'
  | 'audit';

const session = ref<ControlPlaneSession | null>(null);
const activeView = ref<View>('inventory');
const busy = ref(false);
const message = ref('');
const error = ref('');
const username = ref('');
const password = ref('');
const reauthenticationPassword = ref('');
const users = ref<ControlPlaneUser[]>([]);
const roles = ref<Array<{ role_id: string; permissions: string[] }>>([]);
const actions = ref<HighRiskAction[]>([]);
const auditEvents = ref<AuditEvent[]>([]);
const sites = ref<SiteInventory[]>([]);
const screenGroups = ref<ScreenGroupInventory[]>([]);
const screens = ref<ScreenInventory[]>([]);
const groupMemberDrafts = ref<Record<string, string[]>>({});
const capabilityKeys: CapabilityKey[] = [
  'dora',
  'knowledge',
  'direct_llm',
  'asr',
  'tts',
  'querying',
  'fvs_control',
];
const capabilityLabels: Record<CapabilityKey, string> = {
  dora: '对话编排 / Dora',
  knowledge: '知识库',
  direct_llm: '直连 LLM',
  asr: '语音识别 ASR',
  tts: '语音合成 TTS',
  querying: '问数',
  fvs_control: 'FVS 控屏',
};
const capabilityClosedBehavior: Record<CapabilityKey, string> = {
  dora: '仅保留固定本地规则',
  knowledge: '不路由知识问答',
  direct_llm: '仅使用固定模板或提取式回答',
  asr: '保留文本输入',
  tts: '保留文字与字幕',
  querying: '返回“当前大屏未开通问数”',
  fvs_control: '只回答，不执行控屏动作',
};
const stateDefinitions: Array<{
  state: CapabilityState;
  label: string;
  description: string;
}> = [
  { state: 'disabled', label: '已关闭', description: '不选择、不调用任何 Provider' },
  { state: 'mock', label: 'Mock', description: '仅用于开发预览与故障演练' },
  { state: 'unverified', label: '未验证', description: '可检查，但阻断验证与发布' },
  { state: 'available', label: '可用', description: '仅代表本地受限能力在预览边界内可用' },
  { state: 'degraded', label: '已降级', description: '只保留明确说明的受限行为' },
];
const providerCatalog = ref<CapabilityProviderCatalog | null>(null);
const capabilityPresets = ref<CapabilityProfilePreset[]>([]);
const capabilityProfiles = ref<CapabilityProfile[]>([]);
const selectedCapabilityProfile = ref<CapabilityProfile | null>(null);
const observedProfileVersions = ref<CapabilityProfileVersion[]>([]);
const screenCapabilities = ref<Record<string, ScreenEffectiveCapabilities>>({});
const selectedPresetId = ref<CapabilityProfilePreset['preset_id']>('text_only');
const newProfileSiteId = ref('');
const newProfileName = ref('文本讲解能力套餐');
const newProfileDescription = ref('从产品预设复制的站点能力套餐；不包含任何凭据或外部连接。');
const selectedCapabilityProfileId = ref('');
const profileEditorSpec = ref<CapabilityProfileSpec>(createDisabledCapabilitySpec());
const fallbackProviderDrafts = ref<Record<CapabilityKey, string>>(
  Object.fromEntries(capabilityKeys.map((capability) => [capability, ''])) as Record<
    CapabilityKey,
    string
  >,
);
const draftCapabilityVersionId = ref('');
const releaseDraft = ref<ConfigDraft | null>(null);
const releaseCandidate = ref<ConfigRelease | null>(null);
const releasePublication = ref<Record<string, any> | null>(null);
const storageProfile = ref<Record<string, any> | null>(null);
const backupRecord = ref<BackupRecord | null>(null);
const restorePlan = ref<RestorePlan | null>(null);
const draftTargetType = ref<'SCREEN' | 'SCREEN_GROUP'>('SCREEN');
const draftTargetId = ref('');
const draftLookupId = ref('');
const releaseLookupId = ref('');
const draftWelcomeText = ref('您好，欢迎了解当前大屏数据。');
const draftFvsRef = ref('https://fvs.example.test/mock-preview');
const draftDecisionReason = ref('已独立核对 Mock 预览、目标指纹与变更内容');
const releaseReason = ref('创建经审批的不可变配置版本');
const publishReason = ref('发布经审批的不可变配置版本');
const publishActionId = ref('');
const rollbackReason = ref('前滚回退到选定历史版本内容');
const rollbackActionId = ref('');
const backupReason = ref('创建 P1.3 开发预览恢复检查点');
const restoreReason = ref('恢复已验证的开发预览检查点');
const restoreActionId = ref('');

const newGroupSlug = ref('');
const newGroupDisplayName = ref('');
const newScreenSlug = ref('');
const newScreenDisplayName = ref('');
const newScreenFvsRef = ref('');

const newUsername = ref('');
const newDisplayName = ref('');
const newUserReason = ref('创建受治理的预配账号');
const createActionId = ref('');
const createRequestKey = ref(randomIdempotencyKey('create-user-request'));
const approvalReason = ref('已独立核对目标、权限与变更原因');

const screenId = ref('screen-trust-fixture');
const enrollmentReason = ref('为信任夹具签发一次性设备注册');
const enrollmentActionId = ref('');
const enrollmentRequestKey = ref(randomIdempotencyKey('enrollment-request'));
const enrollmentToken = ref('');
const deviceCredential = ref('');
const credentialId = ref('');
const familyEtag = ref('');
const credentialEpoch = ref(1);
const revokeActionId = ref('');
const revokeReason = ref('撤销受影响设备凭据族');
const deviceStatus = ref<Record<string, any> | null>(null);

const permissions = computed(() => new Set(session.value?.user.permissions ?? []));
const canManageUsers = computed(() => permissions.value.has('user.manage'));
const canApprove = computed(() => permissions.value.has('risk.approve'));
const canAudit = computed(() => permissions.value.has('audit.read'));
const canEnroll = computed(() => permissions.value.has('device.enroll'));
const canRevoke = computed(() => permissions.value.has('device.revoke'));
const canReadScreens = computed(() => permissions.value.has('screen.read'));
const canManageScreens = computed(() => permissions.value.has('screen.manage'));
const canReadConfig = computed(() => permissions.value.has('config.read'));
const canEditTechnicalConfig = computed(() => permissions.value.has('config.edit_technical'));
const canEditConfig = computed(
  () =>
    permissions.value.has('config.edit_business')
    && permissions.value.has('config.edit_technical'),
);
const canApproveConfig = computed(() => permissions.value.has('config.approve'));
const canPublish = computed(() => permissions.value.has('release.publish'));
const canRollback = computed(() => permissions.value.has('release.rollback'));
const canCreateBackup = computed(() => permissions.value.has('backup.create'));
const canRestore = computed(() => permissions.value.has('backup.restore'));
const draftTargetOptions = computed(() =>
  draftTargetType.value === 'SCREEN'
    ? screens.value.map((screen) => ({
      id: screen.screen_id,
      label: `${screen.display_name} · ${screen.slug}`,
    }))
    : screenGroups.value.map((group) => ({
      id: group.screen_group_id,
      label: `${group.display_name} · ${group.member_screen_ids.length} 屏`,
    })),
);
const profileVersionOptions = computed(() => {
  const options = capabilityProfiles.value
    .filter((profile) => profile.head_version)
    .map((profile) => ({
      profile_id: profile.profile_id,
      profile_version_id: profile.head_version.profile_version_id,
      label: `${profile.name} · v${profile.head_version.version_number}`,
      activation_eligible: profile.head_version.activation_eligible,
      state_summary: profile.head_version.state_summary,
    }));
  const assigned = releaseDraft.value?.capability_profile;
  if (assigned && !options.some((option) => option.profile_version_id === assigned.profile_version_id)) {
    options.push({
      profile_id: assigned.profile_id,
      profile_version_id: assigned.profile_version_id,
      label: `${assigned.profile_name || assigned.profile_id} · v${assigned.version_number}（当前草稿）`,
      activation_eligible: assigned.activation_eligible,
      state_summary: assigned.state_summary,
    });
  }
  return options;
});
const selectedPreset = computed(() =>
  capabilityPresets.value.find((preset) => preset.preset_id === selectedPresetId.value),
);
const selectedEditorStateSummary = computed<Record<CapabilityKey, CapabilityState>>(() =>
  Object.fromEntries(
    capabilityKeys.map((capability) => [
      capability,
      capabilityStateFor(
        capability,
        profileEditorSpec.value[capability].enabled,
        profileEditorSpec.value[capability].primary_provider_id,
      ),
    ]),
  ) as Record<CapabilityKey, CapabilityState>,
);

function createDisabledCapabilitySpec(): CapabilityProfileSpec {
  return Object.fromEntries(
    capabilityKeys.map((capability) => [
      capability,
      {
        enabled: false,
        primary_provider_id: null,
        fallback_provider_ids: [],
        timeout_ms: 5000,
      },
    ]),
  ) as unknown as CapabilityProfileSpec;
}

function cloneCapabilitySpec(spec: CapabilityProfileSpec): CapabilityProfileSpec {
  return structuredClone(spec);
}

function providersFor(capability: CapabilityKey) {
  return (providerCatalog.value?.items || []).filter(
    (provider) => provider.capability === capability,
  );
}

function capabilityStateFor(
  capability: CapabilityKey,
  enabled: boolean,
  providerId: string | null,
): CapabilityState {
  if (!enabled) return 'disabled';
  const providers = providersFor(capability);
  const selection = profileEditorSpec.value[capability];
  const selectedProviders = [
    providerId,
    ...selection.fallback_provider_ids,
  ].filter((item): item is string => Boolean(item));
  if (
    selectedProviders.some(
      (selectedId) =>
        providers.find((provider) => provider.provider_id === selectedId)?.state === 'unverified',
    )
  ) {
    return 'unverified';
  }
  const provider = providers.find((item) => item.provider_id === providerId);
  return provider?.state || 'unverified';
}

function providerState(capability: CapabilityKey, providerId: string): CapabilityState {
  return providersFor(capability).find((item) => item.provider_id === providerId)?.state
    || 'unverified';
}

function stateLabel(state?: CapabilityState | null): string {
  return stateDefinitions.find((item) => item.state === state)?.label || state || '未配置';
}

function normalizeCapabilitySelection(capability: CapabilityKey) {
  const selection = profileEditorSpec.value[capability];
  if (!selection.enabled) {
    selection.primary_provider_id = null;
    selection.fallback_provider_ids = [];
    return;
  }
  const providers = providersFor(capability);
  if (!providers.some((provider) => provider.provider_id === selection.primary_provider_id)) {
    selection.primary_provider_id = providers[0]?.provider_id || null;
  }
  selection.fallback_provider_ids = selection.fallback_provider_ids.filter(
    (providerId) =>
      providerId !== selection.primary_provider_id
      && providers.some((provider) => provider.provider_id === providerId),
  );
}

function fallbackCandidates(capability: CapabilityKey) {
  const selection = profileEditorSpec.value[capability];
  return providersFor(capability).filter(
    (provider) =>
      provider.provider_id !== selection.primary_provider_id
      && !selection.fallback_provider_ids.includes(provider.provider_id),
  );
}

function addFallbackProvider(capability: CapabilityKey) {
  const providerId = fallbackProviderDrafts.value[capability];
  if (!providerId || !fallbackCandidates(capability).some((item) => item.provider_id === providerId)) {
    return;
  }
  profileEditorSpec.value[capability].fallback_provider_ids.push(providerId);
  fallbackProviderDrafts.value[capability] = '';
}

function removeFallbackProvider(capability: CapabilityKey, index: number) {
  profileEditorSpec.value[capability].fallback_provider_ids.splice(index, 1);
}

function moveFallbackProvider(capability: CapabilityKey, index: number, direction: -1 | 1) {
  const nextIndex = index + direction;
  const fallbacks = profileEditorSpec.value[capability].fallback_provider_ids;
  if (nextIndex < 0 || nextIndex >= fallbacks.length) return;
  [fallbacks[index], fallbacks[nextIndex]] = [fallbacks[nextIndex], fallbacks[index]];
}

function capabilitySummaryState(
  snapshot: ScreenEffectiveCapabilities['effective'],
  capability: CapabilityKey,
): CapabilityState | undefined {
  return snapshot?.state_summary?.[capability];
}

onMounted(async () => {
  try {
    session.value = await loadSession();
    await loadActiveView();
  } catch {
    session.value = null;
  }
});

async function run(task: () => Promise<void>) {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    await task();
  } catch (caught) {
    const apiError = caught as ControlPlaneApiError;
    if (apiError.status === 401) {
      session.value = null;
      clearSensitiveState();
    }
    error.value = `${apiError.code || 'REQUEST_FAILED'}：${apiError.message}`;
  } finally {
    busy.value = false;
  }
}

async function login() {
  await run(async () => {
    session.value = await signIn(username.value, password.value);
    password.value = '';
    message.value = '登录成功；会话标识仅存在于 Secure / HttpOnly Cookie。';
    await loadActiveView();
  });
}

async function logout() {
  await run(async () => {
    await signOut();
    session.value = null;
    users.value = [];
    actions.value = [];
    auditEvents.value = [];
    sites.value = [];
    screenGroups.value = [];
    screens.value = [];
    groupMemberDrafts.value = {};
    providerCatalog.value = null;
    capabilityPresets.value = [];
    capabilityProfiles.value = [];
    selectedCapabilityProfile.value = null;
    observedProfileVersions.value = [];
    screenCapabilities.value = {};
    releaseDraft.value = null;
    releaseCandidate.value = null;
    releasePublication.value = null;
    backupRecord.value = null;
    restorePlan.value = null;
    clearSensitiveState();
    message.value = '已退出并撤销当前会话。';
  });
}

async function confirmPassword() {
  if (!session.value) return;
  await run(async () => {
    session.value = await reauthenticate(
      reauthenticationPassword.value,
      session.value!.etag,
    );
    reauthenticationPassword.value = '';
    message.value = '密码已重新确认；会话 Cookie 与 CSRF 已同步轮换。';
  });
}

function clearSensitiveState() {
  password.value = '';
  reauthenticationPassword.value = '';
  enrollmentToken.value = '';
  deviceCredential.value = '';
}

async function switchView(view: View) {
  activeView.value = view;
  await run(loadActiveView);
}

async function loadActiveView() {
  if (!session.value) return;
  if (activeView.value === 'inventory' && canReadScreens.value) {
    const [siteResult, groupResult, screenResult] = await Promise.all([
      listSites(),
      listScreenGroups(),
      listScreenInstances(),
    ]);
    sites.value = siteResult.items;
    screenGroups.value = groupResult.items;
    screens.value = screenResult.items;
    groupMemberDrafts.value = Object.fromEntries(
      groupResult.items.map((group) => [group.screen_group_id, [...group.member_screen_ids]]),
    );
  } else if (activeView.value === 'capabilities' && canReadConfig.value) {
    const [catalogResult, presetResult, profileResult] = await Promise.all([
      listCapabilityProviders(),
      listCapabilityProfilePresets(),
      listCapabilityProfiles(),
    ]);
    providerCatalog.value = catalogResult;
    capabilityPresets.value = presetResult.items;
    capabilityProfiles.value = profileResult.items;
    if (canReadScreens.value) {
      const [siteResult, screenResult] = await Promise.all([listSites(), listScreenInstances()]);
      sites.value = siteResult.items;
      screens.value = screenResult.items;
      if (!newProfileSiteId.value) newProfileSiteId.value = siteResult.items[0]?.site_id || '';
      await loadScreenCapabilityStates();
    }
    if (
      selectedCapabilityProfileId.value
      && !profileResult.items.some(
        (profile) => profile.profile_id === selectedCapabilityProfileId.value,
      )
    ) {
      selectedCapabilityProfileId.value = '';
      selectedCapabilityProfile.value = null;
    }
  } else if (activeView.value === 'releases' && canReadScreens.value) {
    const [groupResult, screenResult, storageResult, capabilityProfileResult] = await Promise.all([
      listScreenGroups(),
      listScreenInstances(),
      getStorageProfile(),
      canReadConfig.value ? listCapabilityProfiles() : Promise.resolve({ items: [] }),
    ]);
    screenGroups.value = groupResult.items;
    screens.value = screenResult.items;
    storageProfile.value = storageResult;
    capabilityProfiles.value = capabilityProfileResult.items as CapabilityProfile[];
    if (!draftTargetId.value) {
      draftTargetId.value = screenResult.items[0]?.screen_id || '';
    }
  } else if (activeView.value === 'users' && canManageUsers.value) {
    const [userResult, roleResult] = await Promise.all([listUsers(), listRoleDefinitions()]);
    users.value = userResult.items;
    roles.value = roleResult.items;
  } else if (activeView.value === 'approvals' && canApprove.value) {
    actions.value = (await listPendingActions()).items;
  } else if (activeView.value === 'audit' && canAudit.value) {
    auditEvents.value = (await listAuditEvents()).items;
  }
}

async function loadScreenCapabilityStates() {
  if (!canReadScreens.value || !screens.value.length) {
    screenCapabilities.value = {};
    return;
  }
  const results = await Promise.all(
    screens.value.map((screen) => getScreenEffectiveCapabilities(screen.screen_id)),
  );
  screenCapabilities.value = Object.fromEntries(
    results.map((result) => [result.screen_id, result]),
  );
}

async function submitGroup() {
  const site = sites.value[0];
  if (!site) return;
  await run(async () => {
    await createScreenGroup(site.site_id, {
      slug: newGroupSlug.value,
      display_name: newGroupDisplayName.value,
    });
    newGroupSlug.value = '';
    newGroupDisplayName.value = '';
    message.value = '大屏组已创建；组本身不是授权边界。';
    await loadActiveView();
  });
}

async function saveGroup(group: ScreenGroupInventory) {
  await run(async () => {
    await updateScreenGroup(group, {
      display_name: group.display_name,
      member_screen_ids: [...(groupMemberDrafts.value[group.screen_group_id] || [])].sort(),
    });
    message.value = '大屏组与完整成员集合已按 ETag 原子更新。';
    await loadActiveView();
  });
}

async function submitScreen() {
  const site = sites.value[0];
  if (!site) return;
  await run(async () => {
    await createScreenInstance(site.site_id, {
      slug: newScreenSlug.value,
      display_name: newScreenDisplayName.value,
      fvs_binding_ref: newScreenFvsRef.value || null,
    });
    newScreenSlug.value = '';
    newScreenDisplayName.value = '';
    newScreenFvsRef.value = '';
    message.value = '新大屏已创建；运行绑定保持 INVENTORY_INCOMPLETE，需创建数字人实例。';
    await loadActiveView();
  });
}

async function saveScreen(screen: ScreenInventory) {
  await run(async () => {
    await updateScreenInstance(screen, {
      slug: screen.slug,
      display_name: screen.display_name,
      fvs_binding_ref: screen.fvs_binding_ref || null,
    });
    message.value = `${screen.display_name} 已按 ETag 更新；其他大屏未改变。`;
    await loadActiveView();
  });
}

async function addDigitalHuman(screen: ScreenInventory) {
  await run(async () => {
    await createDigitalHumanInstance(screen.screen_id);
    message.value = `${screen.display_name} 已创建唯一活动数字人实例。`;
    await loadActiveView();
  });
}

async function submitUser() {
  await run(async () => {
    const result = await createUser(
      {
        normalized_username: newUsername.value,
        display_name: newDisplayName.value,
        reason: newUserReason.value,
      },
      createRequestKey.value,
      createActionId.value,
    );
    if (result.high_risk_action_id) {
      createActionId.value = String(result.high_risk_action_id);
      message.value = `已创建待审批动作 ${createActionId.value}；审批不会执行创建。`;
    } else {
      message.value = '相同命令已在独立审批后执行；账号保持 PROVISIONING、禁用且无角色。';
      createActionId.value = '';
      createRequestKey.value = randomIdempotencyKey('create-user-request');
      await loadActiveView();
    }
  });
}

async function decideAction(action: HighRiskAction, decision: 'approve' | 'reject') {
  await run(async () => {
    if (decision === 'approve') await approveAction(action, approvalReason.value);
    else await rejectAction(action, approvalReason.value);
    message.value =
      decision === 'approve'
        ? '审批证据已记录；原发起人仍须重新提交完全相同的命令。'
        : '动作已拒绝，未产生业务效果。';
    actions.value = (await listPendingActions()).items;
  });
}

async function submitEnrollment() {
  await run(async () => {
    const result = await issueEnrollment(
      screenId.value,
      enrollmentReason.value,
      enrollmentRequestKey.value,
      enrollmentActionId.value,
    );
    if (result.high_risk_action_id) {
      enrollmentActionId.value = String(result.high_risk_action_id);
      message.value = `设备注册待审批：${enrollmentActionId.value}`;
    } else {
      enrollmentToken.value = String(result.enrollment_token || '');
      message.value = '一次性注册材料已签发，仅保存在当前页面内存；请立即由目标设备领取。';
    }
  });
}

async function claimDevice() {
  await run(async () => {
    const result = await claimEnrollment(
      enrollmentToken.value,
      randomIdempotencyKey('claim-enrollment'),
    );
    deviceCredential.value = String(result.credential || '');
    credentialId.value = String(result.credential_id || '');
    familyEtag.value = String(result.family_etag || '');
    credentialEpoch.value = Number(result.credential_epoch || 1);
    enrollmentToken.value = '';
    message.value = '设备已领取独立凭据；一次性注册材料已从页面内存清除。';
  });
}

async function rotateDevice() {
  await run(async () => {
    const result = await rotateCredential(
      deviceCredential.value,
      randomIdempotencyKey('rotate-credential'),
    );
    deviceCredential.value = String(result.credential || '');
    credentialId.value = String(result.credential_id || '');
    familyEtag.value = String(result.family_etag || '');
    message.value = '后继凭据处于 PENDING_ACTIVATION；首次认证将原子激活并撤销前任。';
  });
}

async function activateDevice() {
  await run(async () => {
    deviceStatus.value = await activateCredential(deviceCredential.value);
    message.value = '设备凭据认证成功；后继版本已激活。';
  });
}

async function loadCredential() {
  await run(async () => {
    const result = await getCredentialMetadata(screenId.value, credentialId.value);
    familyEtag.value = String(result.family_etag || '');
    credentialEpoch.value = Number(result.credential_epoch || 1);
    deviceStatus.value = result;
    message.value = '已读取不含凭据原文的设备元数据。';
  });
}

async function submitRevoke() {
  await run(async () => {
    const result = await revokeCredential(
      screenId.value,
      credentialId.value,
      { expected_credential_epoch: credentialEpoch.value, reason: revokeReason.value },
      familyEtag.value,
      randomIdempotencyKey(revokeActionId.value ? 'revoke-execute' : 'revoke-request'),
      revokeActionId.value,
    );
    if (result.high_risk_action_id) {
      revokeActionId.value = String(result.high_risk_action_id);
      message.value = `整族撤销待独立审批：${revokeActionId.value}`;
    } else {
      message.value = '设备凭据族已整族撤销；活动与待激活凭据均不再可用。';
      deviceStatus.value = result;
    }
  });
}

function choosePreset(preset: CapabilityProfilePreset) {
  selectedPresetId.value = preset.preset_id;
  newProfileName.value = `${preset.name}（自定义）`;
  newProfileDescription.value = preset.description;
}

async function copySelectedPreset() {
  if (!selectedPreset.value) return;
  await run(async () => {
    const profile = await createCapabilityProfile({
      site_id: newProfileSiteId.value,
      name: newProfileName.value.trim(),
      description: newProfileDescription.value.trim(),
      source_preset_id: selectedPreset.value!.preset_id,
    });
    capabilityProfiles.value = [
      profile,
      ...capabilityProfiles.value.filter((item) => item.profile_id !== profile.profile_id),
    ];
    selectedCapabilityProfileId.value = profile.profile_id;
    selectedCapabilityProfile.value = profile;
    observedProfileVersions.value = [profile.head_version];
    profileEditorSpec.value = cloneCapabilitySpec(profile.head_version.spec);
    message.value =
      `已从 ${selectedPreset.value!.preset_id} 复制站点能力套餐；`
      + `v${profile.head_version.version_number} 已不可变。`;
  });
}

async function openCapabilityProfile(profileId: string) {
  if (!profileId) {
    selectedCapabilityProfile.value = null;
    observedProfileVersions.value = [];
    profileEditorSpec.value = createDisabledCapabilitySpec();
    return;
  }
  await run(async () => {
    const profile = await getCapabilityProfile(profileId);
    selectedCapabilityProfile.value = profile;
    selectedCapabilityProfileId.value = profile.profile_id;
    observedProfileVersions.value = [profile.head_version];
    profileEditorSpec.value = cloneCapabilitySpec(profile.head_version.spec);
    message.value =
      `已读取 ${profile.name} v${profile.head_version.version_number}；`
      + '编辑只会创建新的不可变版本。';
  });
}

async function createNextCapabilityProfileVersion() {
  if (!selectedCapabilityProfile.value) return;
  await run(async () => {
    const previousVersion = selectedCapabilityProfile.value!.head_version;
    capabilityKeys.forEach(normalizeCapabilitySelection);
    const profile = await createCapabilityProfileVersion(
      selectedCapabilityProfile.value!,
      cloneCapabilitySpec(profileEditorSpec.value),
    );
    selectedCapabilityProfile.value = profile;
    capabilityProfiles.value = capabilityProfiles.value.map((item) =>
      item.profile_id === profile.profile_id ? profile : item,
    );
    observedProfileVersions.value = [
      profile.head_version,
      previousVersion,
      ...observedProfileVersions.value,
    ].filter(
      (version, index, versions) =>
        versions.findIndex(
          (candidate) => candidate.profile_version_id === version.profile_version_id,
        ) === index,
    );
    message.value =
      `已创建 ${profile.name} v${profile.head_version.version_number}；`
      + '旧版本与已发布快照保持不变。';
  });
}

async function assignDraftCapabilityProfile() {
  if (!releaseDraft.value || !draftCapabilityVersionId.value) return;
  await run(async () => {
    const draft = await assignCapabilityProfileToDraft(
      releaseDraft.value!,
      draftCapabilityVersionId.value,
    );
    syncDraftForm(draft);
    message.value =
      `草稿已绑定不可变能力版本 ${draft.capability_profile?.profile_version_id || ''}；`
      + 'revision 已推进，旧验证、预览和审批证据已失效。';
  });
}

function resetDraftTarget() {
  draftTargetId.value = draftTargetOptions.value[0]?.id || '';
}

function syncDraftForm(draft: ConfigDraft) {
  releaseDraft.value = draft;
  draftLookupId.value = draft.draft_id;
  draftTargetType.value = draft.target.type;
  draftTargetId.value = draft.target.screen_id || draft.target.screen_group_id || '';
  draftWelcomeText.value = draft.spec.welcome_text || draftWelcomeText.value;
  draftFvsRef.value = draft.spec.fvs_binding_ref || draftFvsRef.value;
  draftCapabilityVersionId.value = draft.capability_profile?.profile_version_id || '';
}

async function startReleaseDraft() {
  await run(async () => {
    const draft = await createConfigDraft(draftTargetType.value, draftTargetId.value);
    syncDraftForm(draft);
    releaseCandidate.value = null;
    releasePublication.value = null;
    message.value = `草稿 ${draft.draft_id} 已创建；先完整替换配置，再验证与 Mock 预览。`;
  });
}

async function loadReleaseDraft() {
  await run(async () => {
    const draft = await getConfigDraft(draftLookupId.value.trim());
    syncDraftForm(draft);
    message.value = `已读取草稿 ${draft.draft_id}；状态为 ${draft.state}。`;
  });
}

async function saveReleaseDraftSpec() {
  if (!releaseDraft.value) return;
  await run(async () => {
    const draft = await replaceConfigDraftSpec(releaseDraft.value!, {
      welcome_text: draftWelcomeText.value,
      fvs_binding_ref: draftFvsRef.value,
    });
    syncDraftForm(draft);
    message.value = '完整配置已按强 ETag 写入；没有执行任何 FVS 请求。';
  });
}

async function moveReleaseDraft(
  operation: 'validate' | 'preview' | 'submit-for-approval' | 'revise' | 'abandon',
) {
  if (!releaseDraft.value) return;
  await run(async () => {
    const draft = await transitionConfigDraft(releaseDraft.value!, operation);
    syncDraftForm(draft);
    if (operation === 'preview') {
      message.value = 'Mock 预览完成；此结果不代表真实 FVS 兼容性或生产可用性。';
    } else if (operation === 'submit-for-approval') {
      message.value = `草稿已冻结待异人审批；请将草稿 ID ${draft.draft_id} 交给管理员。`;
    } else {
      message.value = `草稿已执行 ${operation}；当前状态 ${draft.state}。`;
    }
  });
}

async function decideReleaseDraft(decision: 'approve' | 'reject') {
  if (!releaseDraft.value) return;
  await run(async () => {
    const draft = await decideConfigDraft(
      releaseDraft.value!,
      decision,
      draftDecisionReason.value,
    );
    syncDraftForm(draft);
    message.value =
      decision === 'approve'
        ? '已记录异人审批；原编辑者可重新读取草稿并创建不可变 Release。'
        : '草稿已拒绝，历史证据仍保留。';
  });
}

async function buildConfigRelease() {
  if (!releaseDraft.value) return;
  await run(async () => {
    releaseCandidate.value = await createConfigRelease(
      releaseDraft.value!,
      releaseReason.value,
    );
    releaseLookupId.value = releaseCandidate.value.release_id;
    releaseDraft.value = await getConfigDraft(releaseDraft.value!.draft_id);
    message.value = `不可变 NORMAL Release ${releaseCandidate.value.release_id} 已创建。`;
  });
}

async function loadConfigReleaseById() {
  await run(async () => {
    releaseCandidate.value = await getConfigRelease(releaseLookupId.value.trim());
    message.value = `已读取不可变 ${releaseCandidate.value.creation_kind} Release。`;
  });
}

async function submitPublication() {
  if (!releaseCandidate.value) return;
  await run(async () => {
    let result: Record<string, any>;
    if (draftTargetType.value === 'SCREEN') {
      const target = releaseCandidate.value!.targets.find(
        (item) => item.screen_id === draftTargetId.value,
      );
      if (!target) throw new Error('当前 Release 不包含所选大屏');
      const binding = await getRuntimeBinding(draftTargetId.value);
      result = await publishReleaseToScreen(
        draftTargetId.value,
        releaseCandidate.value!,
        target,
        binding,
        publishReason.value,
        publishActionId.value,
      );
    } else {
      const group = screenGroups.value.find(
        (item) => item.screen_group_id === draftTargetId.value,
      );
      if (!group) throw new Error('未找到所选大屏组');
      const bindings = await Promise.all(
        group.member_screen_ids.map((id) => getRuntimeBinding(id)),
      );
      result = await publishReleaseToGroup(
        group,
        releaseCandidate.value!,
        bindings,
        publishReason.value,
        publishActionId.value,
      );
    }
    if (result.high_risk_action_id) {
      publishActionId.value = String(result.high_risk_action_id);
      message.value = `发布请求 ${publishActionId.value} 待另一管理员审批；尚未改变 desired。`;
    } else {
      releasePublication.value = result.publication;
      publishActionId.value = '';
      message.value = '发布计划已执行；applied 仍需目标设备确认准确 generation/hash。';
    }
  });
}

async function submitRollback() {
  if (!releaseCandidate.value) return;
  await run(async () => {
    let result: Record<string, any>;
    if (draftTargetType.value === 'SCREEN') {
      const source = releaseCandidate.value!.targets.find(
        (item) => item.screen_id === draftTargetId.value,
      );
      if (!source) throw new Error('历史 Release 不包含所选大屏');
      const binding = await getRuntimeBinding(draftTargetId.value);
      result = await rollbackScreenRelease(
        draftTargetId.value,
        source.release_target_id,
        binding,
        rollbackReason.value,
        rollbackActionId.value,
      );
    } else {
      const group = screenGroups.value.find(
        (item) => item.screen_group_id === draftTargetId.value,
      );
      if (!group) throw new Error('未找到所选大屏组');
      const bindings = await Promise.all(
        group.member_screen_ids.map((id) => getRuntimeBinding(id)),
      );
      result = await rollbackGroupRelease(
        group,
        releaseCandidate.value!,
        bindings,
        rollbackReason.value,
        rollbackActionId.value,
      );
    }
    if (result.high_risk_action_id) {
      rollbackActionId.value = String(result.high_risk_action_id);
      message.value = `回滚请求 ${rollbackActionId.value} 待异人审批；历史未被修改。`;
    } else {
      releaseCandidate.value = result.release;
      releasePublication.value = result.publication;
      rollbackActionId.value = '';
      message.value = '已创建并发布新的 ROLLBACK Release；历史版本保持不可变。';
    }
  });
}

async function makeBackup() {
  await run(async () => {
    backupRecord.value = await createBackup(backupReason.value);
    restorePlan.value = null;
    message.value = `加密备份 ${backupRecord.value.backup_id} 已创建并完成即时验证。`;
  });
}

async function checkBackup() {
  if (!backupRecord.value) return;
  await run(async () => {
    const result = await verifyBackup(backupRecord.value!.backup_id);
    message.value = `备份重新验证：${result.outcome}；耗时 ${result.duration_ms} ms。`;
  });
}

async function prepareRestore() {
  if (!backupRecord.value) return;
  await run(async () => {
    restorePlan.value = await createRestorePlan(backupRecord.value!.backup_id);
    message.value = `恢复计划 ${restorePlan.value.restore_plan_id} 已验证；执行仍需异人审批。`;
  });
}

async function submitRestore() {
  if (!restorePlan.value) return;
  await run(async () => {
    const result = await executeRestorePlan(
      restorePlan.value!,
      restoreReason.value,
      restoreActionId.value,
    );
    if (result.high_risk_action_id) {
      restoreActionId.value = String(result.high_risk_action_id);
      message.value = `恢复请求 ${restoreActionId.value} 待异人审批；活动库尚未切换。`;
    } else {
      restoreActionId.value = '';
      message.value = '恢复已完成并保留旧库；所有浏览器会话已失效，请重新登录。';
      session.value = null;
    }
  });
}

function formatTime(value?: number | null) {
  return value ? new Date(value * 1000).toLocaleString() : '-';
}
</script>

<template>
  <main class="cp-shell">
    <section class="cp-frame">
      <header class="cp-header">
        <div>
          <p class="cp-eyebrow">P2.1 · Per-screen capability profiles</p>
          <h1>多屏能力与发布控制台</h1>
          <p>开发预览；按屏能力只执行本地 / Mock 诊断，不连接真实 Provider、FVS 或官方插件。</p>
        </div>
        <div v-if="session" class="cp-session">
          <strong>{{ session.user.display_name }}</strong>
          <span>{{ session.user.roles.join(' / ') || '无角色' }}</span>
          <form class="cp-reauth" @submit.prevent="confirmPassword">
            <input
              v-model="reauthenticationPassword"
              type="password"
              autocomplete="current-password"
              aria-label="重新确认当前密码"
              placeholder="高风险操作前重新确认密码"
            />
            <button type="submit" :disabled="busy || !reauthenticationPassword">重新验证</button>
          </form>
          <button type="button" :disabled="busy" @click="logout">退出</button>
        </div>
      </header>

      <div v-if="message" class="cp-notice success">{{ message }}</div>
      <div v-if="error" class="cp-notice error">{{ error }}</div>

      <form v-if="!session" class="cp-login" @submit.prevent="login">
        <div>
          <p class="cp-eyebrow">Built-in local identity</p>
          <h2>管理员登录</h2>
          <p>密码不会进入前端存储；成功后只下发 Secure / HttpOnly 会话 Cookie。</p>
        </div>
        <label>
          用户名
          <input v-model="username" autocomplete="username" required />
        </label>
        <label>
          密码
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <button type="submit" :disabled="busy">{{ busy ? '验证中…' : '登录' }}</button>
      </form>

      <template v-else>
        <nav class="cp-nav" aria-label="控制面功能">
          <button :class="{ active: activeView === 'inventory' }" @click="switchView('inventory')">
            多屏清单
          </button>
          <button
            :class="{ active: activeView === 'capabilities' }"
            @click="switchView('capabilities')"
          >
            能力套餐
          </button>
          <button :class="{ active: activeView === 'releases' }" @click="switchView('releases')">
            发布中心
          </button>
          <button :class="{ active: activeView === 'users' }" @click="switchView('users')">
            用户与角色
          </button>
          <button :class="{ active: activeView === 'approvals' }" @click="switchView('approvals')">
            独立审批
          </button>
          <button :class="{ active: activeView === 'devices' }" @click="switchView('devices')">
            设备信任
          </button>
          <button :class="{ active: activeView === 'audit' }" @click="switchView('audit')">
            安全审计
          </button>
        </nav>

        <section v-if="activeView === 'inventory'" class="cp-grid">
          <article v-if="!canReadScreens" class="cp-card wide">
            <div class="cp-denied">当前角色没有 `screen.read`，API 已拒绝读取多屏清单。</div>
          </article>

          <article v-for="site in sites" :key="site.site_id" class="cp-card wide cp-site-card">
            <div>
              <p class="cp-eyebrow">Read-only Site</p>
              <h2>{{ site.display_name }}</h2>
              <p>{{ site.slug }} · {{ site.timezone }} · {{ site.status }}</p>
            </div>
            <div class="cp-stat-strip">
              <span><strong>{{ site.screen_count }}</strong>大屏</span>
              <span><strong>{{ site.screen_group_count }}</strong>大屏组</span>
              <span><strong>1</strong>物理站点</span>
            </div>
          </article>

          <article class="cp-card wide">
            <div class="cp-card-title">
              <div>
                <p class="cp-eyebrow">ScreenInstance isolation</p>
                <h2>三屏及扩展清单</h2>
              </div>
              <button @click="run(loadActiveView)">刷新</button>
            </div>
            <div class="cp-screen-grid">
              <article v-for="screen in screens" :key="screen.screen_id" class="cp-screen">
                <div class="cp-card-title">
                  <div>
                    <span class="cp-pill">{{ screen.slug }}</span>
                    <h3>{{ screen.display_name }}</h3>
                  </div>
                  <span class="cp-health">{{ screen.lifecycle_state }}</span>
                </div>
                <dl>
                  <div><dt>Screen ID</dt><dd>{{ screen.screen_id }}</dd></div>
                  <div><dt>设备信任</dt><dd>{{ screen.device_trust.state }}</dd></div>
                  <div><dt>FVS</dt><dd>{{ screen.fvs_status }}</dd></div>
                  <div>
                    <dt>运行配置</dt>
                    <dd>{{ screen.runtime_binding.inventory_status }}</dd>
                  </div>
                  <div>
                    <dt>数字人实例</dt>
                    <dd>
                      {{
                        screen.digital_human_instance?.digital_human_instance_id ||
                        '尚未创建'
                      }}
                    </dd>
                  </div>
                </dl>
                <template v-if="canManageScreens">
                  <label>Slug<input v-model="screen.slug" /></label>
                  <label>显示名<input v-model="screen.display_name" /></label>
                  <label>
                    非敏感 FVS 引用
                    <input
                      v-model="screen.fvs_binding_ref"
                      placeholder="仅标签或不含凭据的 URL"
                    />
                  </label>
                  <div class="cp-actions">
                    <button @click="saveScreen(screen)">保存屏幕</button>
                    <button
                      v-if="!screen.digital_human_instance"
                      class="secondary"
                      @click="addDigitalHuman(screen)"
                    >
                      创建数字人实例
                    </button>
                  </div>
                </template>
              </article>
            </div>
          </article>

          <article v-for="group in screenGroups" :key="group.screen_group_id" class="cp-card">
            <p class="cp-eyebrow">Convenience metadata · not authorization</p>
            <h2>{{ group.display_name }}</h2>
            <p>{{ group.slug }} · {{ group.member_screen_ids.length }} 块大屏</p>
            <template v-if="canManageScreens">
              <label>显示名<input v-model="group.display_name" /></label>
              <fieldset>
                <legend>完整成员集合</legend>
                <label v-for="screen in screens" :key="screen.screen_id" class="cp-check">
                  <input
                    v-model="groupMemberDrafts[group.screen_group_id]"
                    type="checkbox"
                    :value="screen.screen_id"
                  />
                  <span>{{ screen.display_name }} <small>{{ screen.slug }}</small></span>
                </label>
              </fieldset>
              <button @click="saveGroup(group)">按 ETag 更新组</button>
            </template>
            <div v-else class="cp-readonly-note">只读角色可以核对成员，但不能改变组。</div>
          </article>

          <article v-if="canManageScreens" class="cp-card">
            <p class="cp-eyebrow">screen.manage</p>
            <h2>新建大屏</h2>
            <label>Slug<input v-model="newScreenSlug" placeholder="screen-4" /></label>
            <label>显示名<input v-model="newScreenDisplayName" placeholder="大屏 4" /></label>
            <label>
              非敏感 FVS 引用
              <input v-model="newScreenFvsRef" placeholder="fvs-inventory-screen-4" />
            </label>
            <button :disabled="!newScreenSlug || !newScreenDisplayName" @click="submitScreen">
              创建独立屏幕
            </button>
          </article>

          <article v-if="canManageScreens" class="cp-card">
            <p class="cp-eyebrow">screen.manage</p>
            <h2>新建大屏组</h2>
            <label>Slug<input v-model="newGroupSlug" placeholder="group-secondary" /></label>
            <label>显示名<input v-model="newGroupDisplayName" placeholder="辅助大屏组" /></label>
            <button :disabled="!newGroupSlug || !newGroupDisplayName" @click="submitGroup">
              创建空组
            </button>
          </article>
        </section>

        <section v-else-if="activeView === 'capabilities'" class="cp-grid">
          <article v-if="!canReadConfig" class="cp-card wide">
            <div class="cp-denied">
              当前角色没有 `config.read`，Provider catalog、能力套餐和逐屏生效状态均不披露。
            </div>
          </article>

          <template v-else>
            <article class="cp-card wide cp-boundary">
              <div>
                <p class="cp-eyebrow">P2.1 development-preview boundary</p>
                <h2>能力可按屏组合，真实 Provider 不外呼</h2>
                <p>
                  Profile 只保存闭合选择器、fallback 顺序和超时。连接地址、凭据、Prompt、
                  SQL、健康结果与认证声明都不能写入套餐。
                </p>
              </div>
              <div class="cp-stat-strip">
                <span><strong>7</strong>固定能力</span>
                <span><strong>3</strong>产品预设</span>
                <span><strong>0</strong>真实外呼</span>
              </div>
            </article>

            <article class="cp-card wide">
              <div class="cp-card-title">
                <div>
                  <p class="cp-eyebrow">Five states · no ambiguous green light</p>
                  <h2>五种状态的含义</h2>
                </div>
                <span class="cp-pill">服务端派生</span>
              </div>
              <div class="cp-state-grid">
                <div v-for="item in stateDefinitions" :key="item.state" class="cp-state-card">
                  <span :class="['cp-state', `is-${item.state}`]">{{ item.state }}</span>
                  <strong>{{ item.label }}</strong>
                  <small>{{ item.description }}</small>
                </div>
              </div>
              <div class="cp-evidence warning">
                <strong>Fallback 只处理技术不可达</strong>
                <span>
                  timeout / unavailable / unsupported 且权限范围等价时才允许；
                  permission_denied / invalid_request / unauthorized_template / cancelled 立即终止。
                </span>
              </div>
            </article>

            <article class="cp-card wide">
              <div class="cp-card-title">
                <div>
                  <p class="cp-eyebrow">p2_provider_registry_001</p>
                  <h2>Provider catalog</h2>
                </div>
                <span v-if="providerCatalog" class="cp-pill">
                  {{ providerCatalog.items.length }} providers
                </span>
              </div>
              <div v-if="providerCatalog" class="cp-hash-line">
                <span>{{ providerCatalog.registry_version }}</span>
                <code>{{ providerCatalog.registry_hash }}</code>
              </div>
              <div v-if="providerCatalog" class="cp-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>能力</th>
                      <th>Provider</th>
                      <th>状态</th>
                      <th>运行边界</th>
                      <th>调用声明</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="provider in providerCatalog.items" :key="provider.provider_id">
                      <td>{{ capabilityLabels[provider.capability] }}</td>
                      <td>
                        <strong>{{ provider.provider_id }}</strong>
                        <small>{{ provider.adapter_kind }} · {{ provider.permission_scope }}</small>
                      </td>
                      <td>
                        <span :class="['cp-state', `is-${provider.state}`]">
                          {{ provider.state }}
                        </span>
                      </td>
                      <td>{{ provider.boundary }}</td>
                      <td>
                        <strong>{{ provider.external_calls_enabled ? '外呼启用' : '本批不外呼' }}</strong>
                        <small>
                          {{ provider.streaming_mode }} · {{ provider.session_mode }} ·
                          {{ provider.supports_cancellation ? '可取消' : '不可取消' }}
                        </small>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </article>

            <article class="cp-card wide">
              <div class="cp-card-title">
                <div>
                  <p class="cp-eyebrow">Immutable product presets</p>
                  <h2>从预设复制站点能力套餐</h2>
                </div>
                <span class="cp-pill">预设本身不可修改</span>
              </div>
              <div class="cp-preset-grid">
                <article
                  v-for="preset in capabilityPresets"
                  :key="preset.preset_id"
                  :class="['cp-preset', { selected: selectedPresetId === preset.preset_id }]"
                >
                  <div class="cp-card-title">
                    <div>
                      <span class="cp-pill">{{ preset.preset_id }}</span>
                      <h3>{{ preset.name }}</h3>
                    </div>
                    <span class="cp-health">
                      {{ preset.activation_eligible ? '可激活' : '阻断' }}
                    </span>
                  </div>
                  <p>{{ preset.description }}</p>
                  <div class="cp-mini-state-list">
                    <span v-for="capability in capabilityKeys" :key="capability">
                      {{ capabilityLabels[capability] }}
                      <b :class="['cp-state', `is-${preset.state_summary[capability]}`]">
                        {{ preset.state_summary[capability] }}
                      </b>
                    </span>
                  </div>
                  <button class="secondary" @click="choosePreset(preset)">选择此预设</button>
                </article>
              </div>
              <div v-if="canEditTechnicalConfig" class="cp-form-grid">
                <label>
                  所属站点
                  <select v-model="newProfileSiteId">
                    <option v-for="site in sites" :key="site.site_id" :value="site.site_id">
                      {{ site.display_name }} · {{ site.slug }}
                    </option>
                  </select>
                </label>
                <label>
                  套餐名称
                  <input v-model="newProfileName" maxlength="120" />
                </label>
                <label class="cp-grow">
                  说明
                  <textarea v-model="newProfileDescription" maxlength="500"></textarea>
                </label>
                <div class="cp-actions cp-align-end">
                  <button
                    :disabled="!newProfileSiteId || !newProfileName.trim() || !selectedPreset"
                    @click="copySelectedPreset"
                  >
                    复制为自定义套餐
                  </button>
                </div>
              </div>
              <div v-else class="cp-readonly-note">
                当前角色可核对预设，但没有 `config.edit_technical`，不能复制或创建版本。
              </div>
            </article>

            <article class="cp-card wide">
              <div class="cp-card-title">
                <div>
                  <p class="cp-eyebrow">Exact seven-capability schema</p>
                  <h2>自定义套餐与不可变版本</h2>
                </div>
                <span v-if="selectedCapabilityProfile" class="cp-pill">
                  head v{{ selectedCapabilityProfile.head_version.version_number }}
                </span>
              </div>
              <div class="cp-form-grid">
                <label>
                  能力套餐
                  <select
                    v-model="selectedCapabilityProfileId"
                    @change="openCapabilityProfile(selectedCapabilityProfileId)"
                  >
                    <option value="">请选择</option>
                    <option
                      v-for="profile in capabilityProfiles"
                      :key="profile.profile_id"
                      :value="profile.profile_id"
                    >
                      {{ profile.name }} · v{{ profile.head_version_number }}
                    </option>
                  </select>
                </label>
                <div v-if="selectedCapabilityProfile" class="cp-hash-line">
                  <span>
                    {{ selectedCapabilityProfile.profile_id }} ·
                    {{ selectedCapabilityProfile.head_version.profile_version_id }}
                  </span>
                  <code>{{ selectedCapabilityProfile.head_version.content_hash }}</code>
                </div>
              </div>
              <div v-if="observedProfileVersions.length" class="cp-target-list">
                <div
                  v-for="version in observedProfileVersions"
                  :key="version.profile_version_id"
                >
                  <strong>
                    v{{ version.version_number }}
                    {{ version.profile_version_id === selectedCapabilityProfile?.head_version_id ? '· HEAD' : '· immutable history' }}
                  </strong>
                  <span>{{ version.profile_version_id }}</span>
                  <code>{{ version.content_hash }}</code>
                </div>
              </div>

              <template v-if="selectedCapabilityProfile">
                <div class="cp-capability-grid">
                  <article
                    v-for="capability in capabilityKeys"
                    :key="capability"
                    class="cp-capability"
                  >
                    <div class="cp-card-title">
                      <div>
                        <p class="cp-eyebrow">{{ capability }}</p>
                        <h3>{{ capabilityLabels[capability] }}</h3>
                      </div>
                      <span
                        :class="[
                          'cp-state',
                          `is-${selectedEditorStateSummary[capability]}`,
                        ]"
                      >
                        {{ selectedEditorStateSummary[capability] }}
                      </span>
                    </div>
                    <label class="cp-switch">
                      <input
                        v-model="profileEditorSpec[capability].enabled"
                        type="checkbox"
                        :disabled="!canEditTechnicalConfig"
                        @change="normalizeCapabilitySelection(capability)"
                      />
                      <span>启用此能力</span>
                    </label>
                    <label>
                      Primary Provider
                      <select
                        v-model="profileEditorSpec[capability].primary_provider_id"
                        :disabled="
                          !canEditTechnicalConfig || !profileEditorSpec[capability].enabled
                        "
                        @change="normalizeCapabilitySelection(capability)"
                      >
                        <option :value="null">请选择</option>
                        <option
                          v-for="provider in providersFor(capability)"
                          :key="provider.provider_id"
                          :value="provider.provider_id"
                        >
                          {{ provider.provider_id }} · {{ provider.state }}
                        </option>
                      </select>
                    </label>
                    <div class="cp-fallback-editor">
                      <strong>Fallback 顺序</strong>
                      <div class="cp-fallback-add">
                        <select
                          v-model="fallbackProviderDrafts[capability]"
                          :disabled="
                            !canEditTechnicalConfig || !profileEditorSpec[capability].enabled
                          "
                          :aria-label="`${capabilityLabels[capability]}待添加 fallback`"
                        >
                          <option value="">选择同能力 Provider</option>
                          <option
                            v-for="provider in fallbackCandidates(capability)"
                            :key="provider.provider_id"
                            :value="provider.provider_id"
                          >
                            {{ provider.provider_id }} · {{ provider.state }}
                          </option>
                        </select>
                        <button
                          type="button"
                          class="secondary"
                          :disabled="
                            !canEditTechnicalConfig ||
                            !profileEditorSpec[capability].enabled ||
                            !fallbackProviderDrafts[capability]
                          "
                          @click="addFallbackProvider(capability)"
                        >
                          添加
                        </button>
                      </div>
                      <ol
                        v-if="profileEditorSpec[capability].fallback_provider_ids.length"
                        class="cp-fallback-list"
                      >
                        <li
                          v-for="(providerId, index) in profileEditorSpec[capability]
                            .fallback_provider_ids"
                          :key="providerId"
                        >
                          <span>
                            {{ index + 1 }}. {{ providerId }}
                            <b :class="['cp-state', `is-${providerState(capability, providerId)}`]">
                              {{ providerState(capability, providerId) }}
                            </b>
                          </span>
                          <div class="cp-actions">
                            <button
                              type="button"
                              class="secondary"
                              :disabled="!canEditTechnicalConfig || index === 0"
                              :aria-label="`上移 ${providerId}`"
                              @click="moveFallbackProvider(capability, index, -1)"
                            >
                              ↑
                            </button>
                            <button
                              type="button"
                              class="secondary"
                              :disabled="
                                !canEditTechnicalConfig ||
                                index ===
                                  profileEditorSpec[capability].fallback_provider_ids.length - 1
                              "
                              :aria-label="`下移 ${providerId}`"
                              @click="moveFallbackProvider(capability, index, 1)"
                            >
                              ↓
                            </button>
                            <button
                              type="button"
                              class="secondary"
                              :disabled="!canEditTechnicalConfig"
                              :aria-label="`移除 ${providerId}`"
                              @click="removeFallbackProvider(capability, index)"
                            >
                              ×
                            </button>
                          </div>
                        </li>
                      </ol>
                      <small v-else>无 fallback；技术故障将使用该能力的固定关闭行为。</small>
                    </div>
                    <label>
                      Timeout (100–120000 ms)
                      <input
                        v-model.number="profileEditorSpec[capability].timeout_ms"
                        type="number"
                        min="100"
                        max="120000"
                        :readonly="!canEditTechnicalConfig"
                      />
                    </label>
                    <small class="cp-closed-behavior">
                      关闭后：{{ capabilityClosedBehavior[capability] }}
                    </small>
                  </article>
                </div>
                <div
                  v-if="selectedCapabilityProfile.head_version.dependency_findings.length"
                  class="cp-evidence warning"
                >
                  <strong>依赖检查</strong>
                  <code
                    v-for="(finding, index) in selectedCapabilityProfile.head_version
                      .dependency_findings"
                    :key="index"
                  >
                    {{ JSON.stringify(finding) }}
                  </code>
                </div>
                <div class="cp-actions">
                  <button
                    v-if="canEditTechnicalConfig"
                    :disabled="busy"
                    @click="createNextCapabilityProfileVersion"
                  >
                    创建新的不可变版本
                  </button>
                  <span class="cp-readonly-note">
                    只移动 mutable head；既有版本与已发布快照不会改变。
                  </span>
                </div>
              </template>
              <div v-else class="cp-empty">选择一个站点能力套餐后查看或创建下一版本。</div>
            </article>

            <article class="cp-card wide">
              <div class="cp-card-title">
                <div>
                  <p class="cp-eyebrow">Desired ≠ applied · applied only at runtime</p>
                  <h2>三屏生效能力</h2>
                </div>
                <button class="secondary" :disabled="!canReadScreens" @click="run(loadScreenCapabilityStates)">
                  刷新三屏
                </button>
              </div>
              <div v-if="!canReadScreens" class="cp-denied">
                当前角色没有 `screen.read`，不能枚举屏幕或读取其 desired / applied 状态。
              </div>
              <div v-else class="cp-screen-grid">
                <article v-for="screen in screens" :key="screen.screen_id" class="cp-screen">
                  <div class="cp-card-title">
                    <div>
                      <span class="cp-pill">{{ screen.slug }}</span>
                      <h3>{{ screen.display_name }}</h3>
                    </div>
                    <span class="cp-health">
                      {{ screenCapabilities[screen.screen_id]?.state || '读取中' }}
                    </span>
                  </div>
                  <dl v-if="screenCapabilities[screen.screen_id]">
                    <div>
                      <dt>Binding generation</dt>
                      <dd>{{ screenCapabilities[screen.screen_id].binding_generation }}</dd>
                    </div>
                    <div>
                      <dt>Desired profile</dt>
                      <dd>
                        {{
                          screenCapabilities[screen.screen_id].desired?.profile_snapshot
                            ?.profile_version_id || 'NOT_CONFIGURED_P2_1'
                        }}
                      </dd>
                    </div>
                    <div>
                      <dt>Applied profile</dt>
                      <dd>
                        {{
                          screenCapabilities[screen.screen_id].applied?.profile_snapshot
                            ?.profile_version_id || 'NOT_CONFIGURED_P2_1'
                        }}
                      </dd>
                    </div>
                    <div>
                      <dt>DigitalHumanInstance</dt>
                      <dd>
                        {{
                          screenCapabilities[screen.screen_id].digital_human_instance_id ||
                          '未绑定'
                        }}
                      </dd>
                    </div>
                  </dl>
                  <div
                    v-if="screenCapabilities[screen.screen_id]?.effective"
                    class="cp-mini-state-list"
                  >
                    <span v-for="capability in capabilityKeys" :key="capability">
                      {{ capabilityLabels[capability] }}
                      <b
                        :class="[
                          'cp-state',
                          `is-${
                            capabilitySummaryState(
                              screenCapabilities[screen.screen_id]?.effective,
                              capability,
                            ) || 'disabled'
                          }`,
                        ]"
                      >
                        {{
                          stateLabel(
                            capabilitySummaryState(
                              screenCapabilities[screen.screen_id]?.effective,
                              capability,
                            ),
                          )
                        }}
                      </b>
                    </span>
                  </div>
                  <div v-else class="cp-evidence warning">
                    <strong>NOT_CONFIGURED_P2_1</strong>
                    <small>当前 applied target 是 P1.3 legacy 内容；不会套用全局 Provider 或 Mock。</small>
                  </div>
                  <small class="cp-closed-behavior">
                    Runtime 只解析 applied ReleaseTarget；legacy target 不会回退到全局 Mock。
                  </small>
                </article>
              </div>
            </article>
          </template>
        </section>

        <section v-else-if="activeView === 'releases'" class="cp-grid">
          <article class="cp-card wide cp-boundary">
            <div>
              <p class="cp-eyebrow">Development preview boundary</p>
              <h2>Mock / 本地能力可验收，真实 Provider 未验证</h2>
              <p>
                配置预览固定标记为 <strong>MOCK_PASSED</strong>；能力快照绑定 exact
                immutable profile version，不会发起 FineReport、FVS、插件或其他外部 Provider 请求。
              </p>
            </div>
            <div class="cp-stat-strip">
              <span><strong>3 天</strong>运行明细</span>
              <span><strong>7 项</strong>按屏能力</span>
              <span><strong>AES-256-GCM</strong>备份</span>
            </div>
          </article>

          <article class="cp-card wide">
            <div class="cp-card-title">
              <div>
                <p class="cp-eyebrow">Draft → validation → Mock preview → approval</p>
                <h2>配置草稿与异人审批</h2>
              </div>
              <span v-if="releaseDraft" class="cp-pill">{{ releaseDraft.state }}</span>
            </div>
            <div class="cp-form-grid">
              <label>
                目标类型
                <select v-model="draftTargetType" @change="resetDraftTarget">
                  <option value="SCREEN">单屏</option>
                  <option value="SCREEN_GROUP">大屏组</option>
                </select>
              </label>
              <label>
                目标
                <select v-model="draftTargetId">
                  <option v-for="item in draftTargetOptions" :key="item.id" :value="item.id">
                    {{ item.label }}
                  </option>
                </select>
              </label>
              <label>
                草稿 ID（跨账号交接）
                <input v-model="draftLookupId" placeholder="drf_..." />
              </label>
              <div class="cp-actions cp-align-end">
                <button v-if="canEditConfig" :disabled="!draftTargetId" @click="startReleaseDraft">
                  新建草稿
                </button>
                <button class="secondary" :disabled="!draftLookupId" @click="loadReleaseDraft">
                  读取草稿
                </button>
              </div>
            </div>

            <template v-if="releaseDraft">
              <div class="cp-hash-line">
                <span>Draft {{ releaseDraft.draft_id }}</span>
                <code>{{ releaseDraft.content_hash }}</code>
              </div>
              <div class="cp-form-grid">
                <label>
                  欢迎语
                  <textarea v-model="draftWelcomeText" :readonly="releaseDraft.state !== 'DRAFT'"></textarea>
                </label>
                <label>
                  非敏感 FVS 引用
                  <textarea v-model="draftFvsRef" :readonly="releaseDraft.state !== 'DRAFT'"></textarea>
                </label>
              </div>
              <div class="cp-assignment-box">
                <div>
                  <p class="cp-eyebrow">Technical assignment · exact immutable version</p>
                  <h3>能力套餐分配</h3>
                  <p>
                    分配会推进 draft revision，并使旧 validation、preview 与 approval 证据失效；
                    不会向 `p1_screen_config_v1` 偷加第三个字段。
                  </p>
                </div>
                <div class="cp-form-grid">
                  <label>
                    Profile version
                    <select
                      v-model="draftCapabilityVersionId"
                      :disabled="releaseDraft.state !== 'DRAFT'"
                    >
                      <option value="">未分配</option>
                      <option
                        v-for="option in profileVersionOptions"
                        :key="option.profile_version_id"
                        :value="option.profile_version_id"
                      >
                        {{ option.label }} ·
                        {{ option.activation_eligible ? '可激活' : '含未验证 Provider' }}
                      </option>
                    </select>
                  </label>
                  <div class="cp-actions cp-align-end">
                    <button
                      v-if="canEditTechnicalConfig && releaseDraft.state === 'DRAFT'"
                      :disabled="
                        !draftCapabilityVersionId ||
                        !releaseDraft.spec.welcome_text ||
                        !releaseDraft.spec.fvs_binding_ref
                      "
                      @click="assignDraftCapabilityProfile"
                    >
                      分配并推进 revision
                    </button>
                  </div>
                </div>
                <div v-if="releaseDraft.capability_profile" class="cp-evidence">
                  <strong>
                    {{ releaseDraft.capability_profile.profile_name || 'CapabilityProfile' }}
                    · v{{ releaseDraft.capability_profile.version_number }}
                  </strong>
                  <span>{{ releaseDraft.capability_profile.profile_version_id }}</span>
                  <code>{{ releaseDraft.capability_profile.content_hash }}</code>
                  <small>
                    {{
                      releaseDraft.capability_profile.activation_eligible
                        ? '依赖允许进入验证'
                        : '存在未验证 Provider：草稿验证与 Release 创建将被阻断'
                    }}
                  </small>
                </div>
                <div v-else class="cp-readonly-note">
                  尚未分配 P2.1 能力套餐；旧 P1.3 target 将明确返回 `NOT_CONFIGURED_P2_1`。
                </div>
              </div>
              <div class="cp-actions cp-wrap">
                <button
                  v-if="canEditConfig && releaseDraft.state === 'DRAFT'"
                  @click="saveReleaseDraftSpec"
                >
                  保存完整配置
                </button>
                <button
                  v-if="permissions.has('config.validate') && releaseDraft.state === 'DRAFT'"
                  class="secondary"
                  @click="moveReleaseDraft('validate')"
                >
                  验证
                </button>
                <button
                  v-if="permissions.has('config.preview') && releaseDraft.state === 'VALIDATED'"
                  class="secondary"
                  @click="moveReleaseDraft('preview')"
                >
                  生成 Mock 预览
                </button>
                <button
                  v-if="canEditConfig && releaseDraft.state === 'PREVIEWED'"
                  @click="moveReleaseDraft('submit-for-approval')"
                >
                  提交异人审批
                </button>
                <button
                  v-if="canEditConfig && ['VALIDATED','PREVIEWED','APPROVAL_PENDING','REJECTED'].includes(releaseDraft.state)"
                  class="secondary"
                  @click="moveReleaseDraft('revise')"
                >
                  修订为新草稿
                </button>
              </div>
              <div v-if="releaseDraft.preview" class="cp-evidence">
                <strong>{{ releaseDraft.preview.outcome }}</strong>
                <span>指纹 {{ releaseDraft.preview.fingerprint_hash }}</span>
                <small>这是 Mock 证据，不是 FVS 实机兼容证明。</small>
              </div>
              <div v-if="releaseDraft.state === 'APPROVAL_PENDING'" class="cp-approval-box">
                <label>审批原因<textarea v-model="draftDecisionReason"></textarea></label>
                <div v-if="canApproveConfig" class="cp-actions">
                  <button @click="decideReleaseDraft('approve')">批准草稿</button>
                  <button class="secondary" @click="decideReleaseDraft('reject')">拒绝</button>
                </div>
                <p v-else>请由具备 `config.approve` 的另一位管理员读取此 Draft ID 后审批。</p>
              </div>
              <div v-if="releaseDraft.state === 'APPROVED'" class="cp-actions">
                <label class="cp-grow">Release 原因<textarea v-model="releaseReason"></textarea></label>
                <button v-if="canPublish" @click="buildConfigRelease">创建不可变 Release</button>
              </div>
            </template>
          </article>

          <article class="cp-card wide">
            <div class="cp-card-title">
              <div>
                <p class="cp-eyebrow">Immutable release · typed four-eyes publication</p>
                <h2>发布、设备待确认与前滚回滚</h2>
              </div>
              <span v-if="releaseCandidate" class="cp-pill">
                {{ releaseCandidate.creation_kind }} #{{ releaseCandidate.release_sequence }}
              </span>
            </div>
            <div class="cp-form-grid">
              <label>Release ID<input v-model="releaseLookupId" placeholder="rel_..." /></label>
              <div class="cp-actions cp-align-end">
                <button class="secondary" :disabled="!releaseLookupId" @click="loadConfigReleaseById">
                  读取 Release
                </button>
              </div>
            </div>
            <template v-if="releaseCandidate">
              <div class="cp-hash-line">
                <span>{{ releaseCandidate.release_id }} · {{ releaseCandidate.targets.length }} 个目标</span>
                <code>{{ releaseCandidate.target_set_hash }}</code>
              </div>
              <div class="cp-target-list">
                <div v-for="target in releaseCandidate.targets" :key="target.release_target_id">
                  <strong>{{ target.screen_id }}</strong>
                  <span>Target {{ target.release_target_id }}</span>
                  <code>{{ target.content_hash }}</code>
                  <span>
                    Capability
                    {{
                      target.capability_snapshot?.profile_version_id ||
                      'NOT_CONFIGURED_P2_1'
                    }}
                  </span>
                </div>
              </div>
              <div class="cp-form-grid">
                <label>发布原因<textarea v-model="publishReason"></textarea></label>
                <label>已批准发布动作 ID<input v-model="publishActionId" placeholder="首次留空" /></label>
                <label>回滚原因<textarea v-model="rollbackReason"></textarea></label>
                <label>已批准回滚动作 ID<input v-model="rollbackActionId" placeholder="首次留空" /></label>
              </div>
              <div class="cp-actions cp-wrap">
                <button v-if="canPublish" @click="submitPublication">
                  {{ publishActionId ? '执行同一发布命令' : '提交发布审批' }}
                </button>
                <button v-if="canRollback" class="secondary" @click="submitRollback">
                  {{ rollbackActionId ? '执行前滚回滚' : '提交回滚审批' }}
                </button>
              </div>
            </template>
            <pre v-if="releasePublication">{{ JSON.stringify(releasePublication, null, 2) }}</pre>
          </article>

          <article class="cp-card wide">
            <div class="cp-card-title">
              <div>
                <p class="cp-eyebrow">Encrypted checkpoint · online-source staged restore</p>
                <h2>备份与恢复</h2>
              </div>
              <span class="cp-pill">同设备开发路径</span>
            </div>
            <div v-if="storageProfile" class="cp-evidence warning">
              <strong>{{ storageProfile.engine }} · {{ storageProfile.backup_backend }}</strong>
              <span>默认运行明细 {{ storageProfile.runtime_detail_days_default }} 天</span>
              <small>生产恢复拓扑：{{ storageProfile.production_recovery_topology_verified ? 'VERIFIED' : 'UNVERIFIED' }}</small>
            </div>
            <label>备份原因<textarea v-model="backupReason"></textarea></label>
            <div class="cp-actions cp-wrap">
              <button v-if="canCreateBackup" @click="makeBackup">创建并验证加密备份</button>
              <button
                v-if="canCreateBackup && backupRecord"
                class="secondary"
                @click="checkBackup"
              >
                重新验证
              </button>
              <button v-if="canRestore && backupRecord" class="secondary" @click="prepareRestore">
                生成恢复计划
              </button>
            </div>
            <div v-if="backupRecord" class="cp-hash-line">
              <span>{{ backupRecord.backup_id }} · {{ backupRecord.state }}</span>
              <code>{{ backupRecord.manifest_hash }}</code>
            </div>
            <template v-if="restorePlan">
              <div class="cp-evidence warning">
                <strong>{{ restorePlan.state }} · {{ restorePlan.recovery_source_mode }}</strong>
                <span>Plan {{ restorePlan.restore_plan_id }}</span>
                <small>恢复会失效全部浏览器会话，并在切换前保留旧库。</small>
              </div>
              <label>恢复原因<textarea v-model="restoreReason"></textarea></label>
              <label>已批准恢复动作 ID<input v-model="restoreActionId" placeholder="首次留空" /></label>
              <button v-if="canRestore" @click="submitRestore">
                {{ restoreActionId ? '执行已批准恢复' : '提交恢复审批' }}
              </button>
            </template>
          </article>
        </section>

        <section v-else-if="activeView === 'users'" class="cp-grid">
          <article class="cp-card wide">
            <div class="cp-card-title">
              <div>
                <p class="cp-eyebrow">Server-enforced RBAC</p>
                <h2>本地用户</h2>
              </div>
              <button v-if="canManageUsers" @click="run(loadActiveView)">刷新</button>
            </div>
            <div v-if="!canManageUsers" class="cp-denied">当前角色没有 `user.manage`，API 已拒绝读取。</div>
            <div v-else class="cp-table-wrap">
              <table>
                <thead>
                  <tr><th>用户</th><th>状态</th><th>角色范围</th><th>最后登录</th></tr>
                </thead>
                <tbody>
                  <tr v-for="user in users" :key="user.user_id">
                    <td><strong>{{ user.display_name }}</strong><small>{{ user.normalized_username }}</small></td>
                    <td><span class="cp-pill">{{ user.account_state }}</span></td>
                    <td>{{ user.role_assignments.map((item) => item.role_id).join(' / ') || '空角色集' }}</td>
                    <td>{{ formatTime(user.last_login_at) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <article v-if="canManageUsers" class="cp-card">
            <p class="cp-eyebrow">Typed high-risk command</p>
            <h2>创建预配账号</h2>
            <p>首次提交只产生待审批证据；另一管理员审批后，原发起人用相同字段和动作 ID 重提。</p>
            <label>用户名<input v-model="newUsername" placeholder="new-auditor" /></label>
            <label>显示名<input v-model="newDisplayName" placeholder="新审计员" /></label>
            <label>原因<textarea v-model="newUserReason"></textarea></label>
            <label>已批准动作 ID（执行时填写）<input v-model="createActionId" /></label>
            <button :disabled="busy" @click="submitUser">
              {{ createActionId ? '执行相同命令' : '提交独立审批' }}
            </button>
          </article>

          <article v-if="canManageUsers" class="cp-card">
            <p class="cp-eyebrow">p1_roles_v1</p>
            <h2>固定角色目录</h2>
            <details v-for="role in roles" :key="role.role_id">
              <summary>{{ role.role_id }}</summary>
              <code>{{ role.permissions.join(' · ') }}</code>
            </details>
          </article>
        </section>

        <section v-else-if="activeView === 'approvals'" class="cp-card">
          <div class="cp-card-title">
            <div>
              <p class="cp-eyebrow">Evidence only</p>
              <h2>待独立审批动作</h2>
            </div>
            <button v-if="canApprove" @click="run(loadActiveView)">刷新</button>
          </div>
          <div v-if="!canApprove" class="cp-denied">当前角色没有 `risk.approve`。</div>
          <template v-else>
            <label>审批说明<textarea v-model="approvalReason"></textarea></label>
            <div class="cp-list">
              <article v-for="action in actions" :key="action.high_risk_action_id" class="cp-row">
                <div>
                  <strong>{{ action.operation_id }}</strong>
                  <span>{{ action.target_id || '-' }} · {{ action.high_risk_action_id }}</span>
                  <small>发起人 {{ action.initiator_user_id }} · 到期 {{ formatTime(action.expires_at) }}</small>
                </div>
                <div class="cp-actions">
                  <button @click="decideAction(action, 'approve')">批准证据</button>
                  <button class="secondary" @click="decideAction(action, 'reject')">拒绝</button>
                </div>
              </article>
              <p v-if="!actions.length" class="cp-empty">没有当前角色可审批的待处理动作。</p>
            </div>
          </template>
        </section>

        <section v-else-if="activeView === 'devices'" class="cp-grid">
          <article class="cp-card">
            <p class="cp-eyebrow">Trust-only fixture</p>
            <h2>签发一次性注册</h2>
            <div v-if="!canEnroll" class="cp-denied">当前角色没有 `device.enroll`。</div>
            <template v-else>
              <label>屏幕信任目标<input v-model="screenId" /></label>
              <label>原因<textarea v-model="enrollmentReason"></textarea></label>
              <label>已批准动作 ID<input v-model="enrollmentActionId" /></label>
              <button @click="submitEnrollment">
                {{ enrollmentActionId ? '执行注册签发' : '提交签发审批' }}
              </button>
            </template>
          </article>

          <article class="cp-card">
            <p class="cp-eyebrow">Device plane</p>
            <h2>领取与轮换</h2>
            <label>一次性注册材料<textarea v-model="enrollmentToken"></textarea></label>
            <button :disabled="!enrollmentToken" @click="claimDevice">设备领取</button>
            <label>设备凭据（仅页面内存）<textarea v-model="deviceCredential"></textarea></label>
            <div class="cp-actions">
              <button :disabled="!deviceCredential" @click="rotateDevice">请求后继凭据</button>
              <button class="secondary" :disabled="!deviceCredential" @click="activateDevice">认证并激活</button>
            </div>
          </article>

          <article class="cp-card">
            <p class="cp-eyebrow">Family-wide hard revoke</p>
            <h2>元数据与整族撤销</h2>
            <div v-if="!canRevoke" class="cp-denied">当前角色没有 `device.revoke`。</div>
            <template v-else>
              <label>Credential ID<input v-model="credentialId" /></label>
              <button class="secondary" @click="loadCredential">读取安全元数据</button>
              <label>Family ETag<input v-model="familyEtag" readonly /></label>
              <label>Credential epoch<input v-model.number="credentialEpoch" type="number" readonly /></label>
              <label>撤销原因<textarea v-model="revokeReason"></textarea></label>
              <label>已批准动作 ID<input v-model="revokeActionId" /></label>
              <button @click="submitRevoke">
                {{ revokeActionId ? '执行整族撤销' : '提交撤销审批' }}
              </button>
            </template>
          </article>

          <article v-if="deviceStatus" class="cp-card wide">
            <p class="cp-eyebrow">Sanitized metadata</p>
            <h2>当前设备状态</h2>
            <pre>{{ JSON.stringify(deviceStatus, null, 2) }}</pre>
          </article>
        </section>

        <section v-else class="cp-card">
          <div class="cp-card-title">
            <div>
              <p class="cp-eyebrow">SHA-256 chained · append only</p>
              <h2>安全审计事件</h2>
            </div>
            <button v-if="canAudit" @click="run(loadActiveView)">刷新</button>
          </div>
          <div v-if="!canAudit" class="cp-denied">当前角色没有 `audit.read`。</div>
          <div v-else class="cp-list">
            <article v-for="event in auditEvents" :key="event.event_id" class="cp-row">
              <div>
                <strong>{{ event.event_type }} · {{ event.outcome }}</strong>
                <span>{{ event.actor_type }} {{ event.actor_id || '-' }} → {{ event.target_type || '-' }} {{ event.target_id || '' }}</span>
                <small>#{{ event.sequence }} · {{ formatTime(event.created_at) }} · {{ event.event_hash.slice(0, 16) }}…</small>
              </div>
            </article>
          </div>
        </section>
      </template>
    </section>
  </main>
</template>

<style scoped>
.cp-shell { min-height: 100vh; padding: 28px; background: #f2f5f1; color: #17302a; }
.cp-frame { width: min(1240px, 100%); margin: 0 auto; }
.cp-header { display: flex; justify-content: space-between; gap: 24px; padding: 26px 30px; border: 1px solid #cfd9d2; border-radius: 18px; background: #fff; box-shadow: 0 18px 50px rgba(28, 56, 47, .08); }
.cp-header h1, .cp-card h2, .cp-login h2 { margin: 4px 0 8px; }
.cp-header p, .cp-card p, .cp-login p { margin: 0; color: #60716a; line-height: 1.6; }
.cp-eyebrow { color: #237156 !important; font-size: 12px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
.cp-session { min-width: 220px; display: grid; align-content: center; gap: 5px; padding-left: 22px; border-left: 1px solid #dfe7e2; }
.cp-session span { color: #60716a; font-size: 13px; }
.cp-reauth { display: grid; grid-template-columns: minmax(180px, 1fr) auto; gap: 8px; margin-top: 6px; }
.cp-reauth input { min-width: 0; }
button { cursor: pointer; border: 0; border-radius: 10px; padding: 10px 15px; background: #176247; color: #fff; font-weight: 700; }
button.secondary { background: #e5ece8; color: #27483d; }
button:disabled { cursor: not-allowed; opacity: .55; }
.cp-notice { margin: 14px 0; padding: 12px 16px; border-radius: 10px; font-weight: 650; }
.cp-notice.success { background: #dff3e8; color: #145b3e; }
.cp-notice.error, .cp-denied { background: #fff0ee; color: #9c332a; }
.cp-login { max-width: 560px; margin: 56px auto; display: grid; gap: 18px; padding: 30px; border: 1px solid #cfd9d2; border-radius: 18px; background: #fff; }
label { display: grid; gap: 7px; color: #354b43; font-size: 13px; font-weight: 750; }
input, textarea, select { width: 100%; border: 1px solid #c7d2cb; border-radius: 9px; padding: 10px 12px; background: #fff; color: #17302a; font: inherit; }
textarea { min-height: 72px; resize: vertical; }
.cp-nav { display: flex; gap: 8px; margin: 18px 0; padding: 7px; border: 1px solid #d7dfda; border-radius: 13px; background: rgba(255,255,255,.78); }
.cp-nav button { background: transparent; color: #53675f; }
.cp-nav button.active { background: #173d31; color: #fff; }
.cp-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.cp-card { display: grid; align-content: start; gap: 15px; padding: 22px; border: 1px solid #d2dcd6; border-radius: 15px; background: #fff; box-shadow: 0 10px 30px rgba(28, 56, 47, .05); }
.cp-card.wide { grid-column: 1 / -1; }
.cp-site-card { display: flex; align-items: center; justify-content: space-between; }
.cp-boundary { display: flex; align-items: center; justify-content: space-between; }
.cp-stat-strip { display: flex; gap: 10px; }
.cp-stat-strip span { min-width: 94px; padding: 12px; border-radius: 12px; background: #edf5f0; color: #456057; text-align: center; }
.cp-stat-strip strong { display: block; color: #173d31; font-size: 24px; }
.cp-state-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
.cp-state-card { display: grid; align-content: start; gap: 7px; min-width: 0; padding: 13px; border: 1px solid #dce5df; border-radius: 11px; background: #fafcfb; }
.cp-state-card small { color: #667970; line-height: 1.45; }
.cp-state { display: inline-block; width: fit-content; max-width: 100%; padding: 3px 8px; border: 1px solid transparent; border-radius: 999px; font-size: 11px; font-weight: 850; letter-spacing: .02em; overflow-wrap: anywhere; }
.cp-state.is-disabled { border-color: #c8d0cc; background: #edf0ee; color: #4e5d57; }
.cp-state.is-mock { border-color: #a9c9ba; background: #e3f1ea; color: #176247; }
.cp-state.is-unverified { border-color: #e2c279; background: #fff4d8; color: #805d0b; }
.cp-state.is-available { border-color: #8dc7aa; background: #daf3e5; color: #0e6440; }
.cp-state.is-degraded { border-color: #dcaa8a; background: #fff0e6; color: #8f4824; }
.cp-preset-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.cp-preset { display: grid; align-content: start; gap: 12px; min-width: 0; padding: 16px; border: 1px solid #dbe4df; border-radius: 12px; background: #fbfcfb; }
.cp-preset.selected { border-color: #3e846b; box-shadow: 0 0 0 2px rgba(62, 132, 107, .13); }
.cp-preset h3, .cp-capability h3, .cp-assignment-box h3 { margin: 6px 0 0; }
.cp-capability-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.cp-capability { display: grid; align-content: start; gap: 12px; min-width: 0; padding: 16px; border: 1px solid #dbe4df; border-radius: 12px; background: #fbfcfb; }
.cp-switch { display: flex; grid-template-columns: none; align-items: center; gap: 9px; }
.cp-switch input { width: auto; }
.cp-fallback-editor { display: grid; gap: 7px; color: #354b43; font-size: 13px; }
.cp-fallback-add { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 7px; }
.cp-fallback-list { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.cp-fallback-list li { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; padding: 7px 9px; border-radius: 8px; background: #eef3f0; }
.cp-fallback-list li > span { display: flex; align-items: center; gap: 6px; min-width: 0; overflow-wrap: anywhere; }
.cp-fallback-list button { padding: 5px 8px; }
.cp-closed-behavior { padding: 9px 10px; border-radius: 8px; background: #eef3f0; color: #5a6e66; line-height: 1.45; }
.cp-mini-state-list { display: grid; gap: 6px; }
.cp-mini-state-list > span { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: #53675f; font-size: 12px; }
.cp-mini-state-list b { flex: 0 0 auto; }
.cp-assignment-box { display: grid; gap: 13px; padding: 16px; border: 1px solid #cbdad2; border-radius: 12px; background: #f8fbf9; }
.cp-screen-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.cp-screen { display: grid; align-content: start; gap: 13px; min-width: 0; padding: 17px; border: 1px solid #dbe4df; border-radius: 13px; background: #fbfcfb; }
.cp-screen h3 { margin: 9px 0 0; }
.cp-health { color: #176247; font-size: 12px; font-weight: 800; }
dl { display: grid; gap: 8px; margin: 0; }
dl div { min-width: 0; }
dt { color: #72827b; font-size: 11px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
dd { margin: 3px 0 0; color: #28483e; font-size: 12px; overflow-wrap: anywhere; }
fieldset { display: grid; gap: 9px; margin: 0; padding: 14px; border: 1px solid #dbe4df; border-radius: 10px; }
legend { padding: 0 6px; color: #53675f; font-size: 12px; font-weight: 800; }
.cp-check { display: flex; grid-template-columns: none; align-items: flex-start; gap: 9px; font-weight: 650; }
.cp-check input { width: auto; margin-top: 3px; }
.cp-check small { display: block; color: #72827b; font-weight: 500; }
.cp-readonly-note { padding: 12px; border-radius: 9px; background: #f3f6f4; color: #60716a; }
.cp-card-title { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.cp-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.cp-align-end { align-self: end; }
.cp-wrap { flex-wrap: wrap; }
.cp-grow { flex: 1 1 320px; }
.cp-hash-line { display: grid; gap: 6px; min-width: 0; padding: 12px 14px; border-radius: 10px; background: #f1f6f3; color: #3f5b51; }
.cp-hash-line code, .cp-target-list code { overflow-wrap: anywhere; color: #176247; font-size: 11px; }
.cp-evidence { display: grid; gap: 5px; padding: 14px; border: 1px solid #bcdac9; border-radius: 11px; background: #eef8f2; color: #31584a; overflow-wrap: anywhere; }
.cp-evidence.warning { border-color: #e2cf9d; background: #fff8e8; color: #755b1c; }
.cp-approval-box { display: grid; gap: 12px; padding: 16px; border: 1px solid #ccd9d2; border-radius: 12px; background: #fafcfb; }
.cp-target-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
.cp-target-list > div { display: grid; gap: 4px; min-width: 0; padding: 11px; border: 1px solid #e0e8e3; border-radius: 9px; }
.cp-target-list span { overflow-wrap: anywhere; color: #64776f; font-size: 11px; }
.cp-denied { padding: 15px; border-radius: 9px; font-weight: 700; }
.cp-table-wrap { overflow: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 12px; border-bottom: 1px solid #e6ece8; text-align: left; vertical-align: top; }
td strong, td small { display: block; }
td small { margin-top: 4px; color: #72827b; }
.cp-pill { display: inline-block; padding: 3px 8px; border-radius: 99px; background: #e5f2eb; color: #176247; font-size: 12px; font-weight: 800; }
details { padding: 11px 0; border-bottom: 1px solid #e5ebe7; }
details code { display: block; margin-top: 10px; color: #53675f; line-height: 1.7; white-space: normal; }
.cp-list { display: grid; gap: 10px; }
.cp-row { display: flex; justify-content: space-between; gap: 16px; padding: 15px; border: 1px solid #e0e7e3; border-radius: 11px; background: #fbfcfb; }
.cp-row div:first-child { display: grid; gap: 4px; min-width: 0; }
.cp-row span, .cp-row small { color: #667970; overflow-wrap: anywhere; }
.cp-actions { display: flex; align-items: center; gap: 8px; }
.cp-empty { padding: 24px; text-align: center; }
pre { overflow: auto; margin: 0; padding: 15px; border-radius: 10px; background: #10241e; color: #cfebdf; }
@media (max-width: 760px) {
  .cp-shell { padding: 14px; }
  .cp-header, .cp-row, .cp-boundary { flex-direction: column; }
  .cp-site-card { align-items: stretch; }
  .cp-stat-strip { overflow-x: auto; }
  .cp-session { border-left: 0; padding-left: 0; }
  .cp-grid { grid-template-columns: 1fr; }
  .cp-screen-grid, .cp-form-grid, .cp-target-list, .cp-state-grid, .cp-preset-grid, .cp-capability-grid { grid-template-columns: 1fr; }
  .cp-fallback-add { grid-template-columns: 1fr; }
  .cp-nav { overflow-x: auto; }
}
</style>
