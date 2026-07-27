<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  activateCredential,
  approveAction,
  claimEnrollment,
  ControlPlaneApiError,
  createDigitalHumanInstance,
  createScreenGroup,
  createScreenInstance,
  createUser,
  getCredentialMetadata,
  issueEnrollment,
  listAuditEvents,
  listPendingActions,
  listRoleDefinitions,
  listScreenGroups,
  listScreenInstances,
  listSites,
  listUsers,
  loadSession,
  randomIdempotencyKey,
  reauthenticate,
  rejectAction,
  revokeCredential,
  rotateCredential,
  signIn,
  signOut,
  type AuditEvent,
  type ControlPlaneSession,
  type ControlPlaneUser,
  type HighRiskAction,
  type ScreenGroupInventory,
  type ScreenInventory,
  type SiteInventory,
  updateScreenGroup,
  updateScreenInstance,
} from './controlPlaneApi';

type View = 'inventory' | 'users' | 'approvals' | 'devices' | 'audit';

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

function formatTime(value?: number | null) {
  return value ? new Date(value * 1000).toLocaleString() : '-';
}
</script>

<template>
  <main class="cp-shell">
    <section class="cp-frame">
      <header class="cp-header">
        <div>
          <p class="cp-eyebrow">P1.2 · Three-Screen Inventory</p>
          <h1>多屏资产与设备信任控制台</h1>
          <p>开发预览；FVS 始终为 UNVERIFIED，运行配置始终为 NOT_CONFIGURED_P1_3。</p>
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
button { border: 0; border-radius: 10px; padding: 10px 15px; background: #176247; color: #fff; font-weight: 700; }
button.secondary { background: #e5ece8; color: #27483d; }
.cp-notice { margin: 14px 0; padding: 12px 16px; border-radius: 10px; font-weight: 650; }
.cp-notice.success { background: #dff3e8; color: #145b3e; }
.cp-notice.error, .cp-denied { background: #fff0ee; color: #9c332a; }
.cp-login { max-width: 560px; margin: 56px auto; display: grid; gap: 18px; padding: 30px; border: 1px solid #cfd9d2; border-radius: 18px; background: #fff; }
label { display: grid; gap: 7px; color: #354b43; font-size: 13px; font-weight: 750; }
input, textarea { width: 100%; border: 1px solid #c7d2cb; border-radius: 9px; padding: 10px 12px; background: #fff; color: #17302a; font: inherit; }
textarea { min-height: 72px; resize: vertical; }
.cp-nav { display: flex; gap: 8px; margin: 18px 0; padding: 7px; border: 1px solid #d7dfda; border-radius: 13px; background: rgba(255,255,255,.78); }
.cp-nav button { background: transparent; color: #53675f; }
.cp-nav button.active { background: #173d31; color: #fff; }
.cp-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.cp-card { display: grid; align-content: start; gap: 15px; padding: 22px; border: 1px solid #d2dcd6; border-radius: 15px; background: #fff; box-shadow: 0 10px 30px rgba(28, 56, 47, .05); }
.cp-card.wide { grid-column: 1 / -1; }
.cp-site-card { display: flex; align-items: center; justify-content: space-between; }
.cp-stat-strip { display: flex; gap: 10px; }
.cp-stat-strip span { min-width: 94px; padding: 12px; border-radius: 12px; background: #edf5f0; color: #456057; text-align: center; }
.cp-stat-strip strong { display: block; color: #173d31; font-size: 24px; }
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
  .cp-header, .cp-row { flex-direction: column; }
  .cp-site-card { align-items: stretch; }
  .cp-stat-strip { overflow-x: auto; }
  .cp-session { border-left: 0; padding-left: 0; }
  .cp-grid { grid-template-columns: 1fr; }
  .cp-screen-grid { grid-template-columns: 1fr; }
  .cp-nav { overflow-x: auto; }
}
</style>
