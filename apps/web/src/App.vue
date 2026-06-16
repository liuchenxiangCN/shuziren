<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  executeScreenAction,
  fetchConfigEffective,
  fetchConfigSchema,
  fetchDemoConfig,
  fetchOpsDependencies,
  fetchOpsErrors,
  fetchOpsExport,
  fetchOpsHealth,
  fetchOpsMetrics,
  fetchOpsSessions,
  fetchWakeConfig,
  fetchScreenActions,
  sendChat,
  streamChat,
  streamSpeech,
  synthesizeSpeech,
  toApiUrl,
  transcribeAudio,
} from './api';
import { executeFvsAction as executeFvsAdapterAction, getFvsConfig } from './fvsAdapter';
import type {
  ChatResponse,
  ChatStreamTtsReady,
  ConfigEffectiveResponse,
  ConfigField,
  ConfigSchemaResponse,
  DemoConfigResponse,
  DemoQuestion,
  OpsDependenciesResponse,
  OpsErrorItem,
  OpsHealthResponse,
  OpsMetricsResponse,
  OpsSessionSummary,
  OpsStatus,
  ScreenAction,
  ScreenExecuteResponse,
  TtsStreamAudioChunk,
  WakeConfigResponse,
} from './types';
import type { FvsActionResult } from './fvsAdapter';

interface ConversationItem {
  id: string;
  role: 'user' | 'assistant' | 'system';
  text: string;
  response?: ChatResponse;
  tts?: ConversationTts;
}

interface ConversationTts {
  status: 'loading' | 'ready' | 'error';
  audioUrl?: string;
  label?: string;
  error?: string;
  segments?: ChatStreamTtsReady[];
  nextSegmentIndex?: number;
  streamEnded?: boolean;
}

interface FvsEvent {
  id: string;
  actionId: string;
  label: string;
  fvsFunction: string;
  params: Record<string, unknown>;
  success: boolean;
  adapterSuccess: boolean;
  adapterMode: string;
  adapterMessage: string;
  speakText: string;
  requestId?: string | null;
}

type InputMode = 'text' | 'voice';
type MainView = 'chat' | 'ops' | 'config';
type TtsPlaybackState = 'idle' | 'loading' | 'playing' | 'error';
type FvsLoadState = 'idle' | 'loading' | 'ready' | 'error';
type ListeningState =
  | 'idle'
  | 'monitoring'
  | 'wake_checking'
  | 'recording'
  | 'followup_listening'
  | 'thinking'
  | 'speaking'
  | 'cooldown';
type VadSegmentKind = 'wake' | 'command' | 'barge_in';

interface SubmitQuestionOptions {
  awaitTts?: boolean;
  beforeAutoTts?: Promise<unknown> | null;
}

interface PlaybackOptions {
  monitorPlayback?: boolean;
  preferStreaming?: boolean;
}

interface MonitorCommandOptions {
  isFollowup?: boolean;
}

type AudioPlaybackResult = 'ended' | 'blocked' | 'error' | 'interrupted';

interface PcmStreamPlayback {
  id: string;
  audioContext: AudioContext;
  analyser: AnalyserNode;
  activeSources: Set<AudioBufferSourceNode>;
  stopped: boolean;
  nextStartTime: number;
  stop: () => void;
}

const WAKE_GREETING_TEXT = '您好。';
const ACKNOWLEDGEMENT_TEXT = '收到，正在为您查找信息。';
const ACKNOWLEDGEMENT_TTS_MAX_WAIT_MS = 1800;
const FVS_LOAD_TIMEOUT_MS = 10000;

const DEFAULT_WAKE_CONFIG: WakeConfigResponse = {
  version: '0.1.0',
  mode: 'semantic',
  wake_words: ['小智小智', '你好小智'],
  settings: {
    min_audio_ms: 800,
    max_audio_ms: 5000,
    cooldown_ms: 1500,
    require_exact_phrase: false,
    vad_threshold: 0.018,
    silence_ms: 700,
    command_timeout_ms: 8000,
    followup_enabled: true,
    followup_window_ms: 12000,
    max_followup_turns: 3,
    barge_in_enabled: false,
    barge_in_wake_words: ['小智小智', '你好小智'],
    barge_in_vad_threshold: 0.018,
    barge_in_min_audio_ms: 900,
    barge_in_silence_ms: 700,
    barge_in_max_audio_ms: 3500,
    barge_in_ignore_after_tts_start_ms: 700,
  },
};

const FALLBACK_DEMO_QUESTIONS: DemoQuestion[] = [
  { id: 'local-1', text: '我是演示嘉宾', category: 'welcome' },
  { id: 'local-2', text: '这个系统能做什么？', category: 'knowledge' },
  { id: 'local-3', text: '当前核心指标怎么样？', category: 'data' },
  { id: 'local-4', text: '请切换到成品库存页面', category: 'screen_control' },
  { id: 'local-5', text: '返回总览', category: 'screen_control' },
];
const MONITOR_PREROLL_MS = 360;
const MONITOR_SPEECH_START_FRAMES = 2;

const sessionId = `demo-session-${Date.now()}`;
const runtimeDemoStableMode = getRuntimeDemoStableMode();
const buildDemoStableMode = isTruthyEnv(import.meta.env.VITE_DEMO_STABLE_MODE);
const activeView = ref<MainView>(getInitialMainView());
const inputText = ref('请切换到成品库存页面');
const asrMockText = ref('请切换到成品库存页面');
const asrText = ref('');
const isSending = ref(false);
const isRecording = ref(false);
const isAsrProcessing = ref(false);
const recordedAudio = ref<Blob | null>(null);
const recorderMimeType = ref('');
const actions = ref<ScreenAction[]>([]);
const activeActionId = ref('SWITCH_HOME');
const fvsConfig = getFvsConfig();
const fvsFrame = ref<HTMLIFrameElement | null>(null);
const conversation = ref<ConversationItem[]>([]);
const fvsEvents = ref<FvsEvent[]>([]);
const apiStatus = ref<'idle' | 'ready' | 'error'>('idle');
const statusText = ref('连接中');
const ttsPlayback = ref<TtsPlaybackState>('idle');
const ttsStatusText = ref('等待播报');
const voiceEnergy = ref(0);
const wakeConfig = ref<WakeConfigResponse>(DEFAULT_WAKE_CONFIG);
const listenerEnabled = ref(false);
const listeningState = ref<ListeningState>('idle');
const listeningDetail = ref('未开启');
const wakeCheckText = ref('');
const commandText = ref('');
const wakeMissCount = ref(0);
const followupTurnsUsed = ref(0);
const monitorEnergy = ref(0);
const opsHealth = ref<OpsHealthResponse | null>(null);
const opsDependencies = ref<OpsDependenciesResponse | null>(null);
const opsMetrics = ref<OpsMetricsResponse | null>(null);
const opsSessions = ref<OpsSessionSummary[]>([]);
const opsErrors = ref<OpsErrorItem[]>([]);
const opsLoading = ref(false);
const opsExporting = ref(false);
const opsErrorText = ref('');
const opsLastUpdated = ref('');
const configEffective = ref<ConfigEffectiveResponse | null>(null);
const configSchema = ref<ConfigSchemaResponse | null>(null);
const configLoading = ref(false);
const configErrorText = ref('');
const demoConfig = ref<DemoConfigResponse | null>(null);
const demoConfigError = ref('');
const fvsLoadState = ref<FvsLoadState>(fvsConfig.enabled && fvsConfig.mode === 'iframe' ? 'loading' : 'idle');
const fvsLoadText = ref('FVS iframe 加载中。');

let mediaStream: MediaStream | null = null;
let recorderAudioContext: AudioContext | null = null;
let recorderSource: MediaStreamAudioSourceNode | null = null;
let recorderProcessor: ScriptProcessorNode | null = null;
let recordedSamples: Float32Array[] = [];
let recordingSampleRate = 16000;
let activeAudio: HTMLAudioElement | null = null;
let audioContext: AudioContext | null = null;
let analyserFrame: number | null = null;
let monitorStream: MediaStream | null = null;
let monitorAudioContext: AudioContext | null = null;
let monitorSource: MediaStreamAudioSourceNode | null = null;
let monitorProcessor: ScriptProcessorNode | null = null;
let monitorGain: GainNode | null = null;
let monitorSamples: Float32Array[] = [];
let monitorPrerollSamples: Float32Array[] = [];
let monitorSampleRate = 16000;
let monitorSpeechActive = false;
let monitorSpeechStartedAt = 0;
let monitorLastSpeechAt = 0;
let monitorSpeechCandidateFrames = 0;
let monitorFinalizing = false;
let monitorPlaybackStartedAt = 0;
let monitorCommandTimer: number | null = null;
let monitorCooldownTimer: number | null = null;
let activeSegmentPlaybackItemId: string | null = null;
let wakeGreetingAudioUrl: string | null = null;
let wakeGreetingAudioPromise: Promise<string | null> | null = null;
let acknowledgementAudioUrl: string | null = null;
let acknowledgementAudioPromise: Promise<string | null> | null = null;
let promptPlaybackQueue: Promise<void> = Promise.resolve();
let activeSpeechUtterance: SpeechSynthesisUtterance | null = null;
let activeStreamPlayback: PcmStreamPlayback | null = null;
let fvsLoadTimer: number | null = null;

const activeAction = computed(() => {
  return actions.value.find((action) => action.id === activeActionId.value) ?? actions.value[0];
});

const latestFvsEvent = computed(() => fvsEvents.value[0]);
const isFvsHost = computed(() => fvsConfig.enabled && fvsConfig.mode === 'iframe');
const isFvsWebFrame = computed(() => fvsConfig.enabled && fvsConfig.mode === 'parent');
const isOpsView = computed(() => activeView.value !== 'chat');
const isOpsMonitorView = computed(() => activeView.value === 'ops');
const isConfigView = computed(() => activeView.value === 'config');
const isDemoStableMode = computed(
  () => runtimeDemoStableMode || buildDemoStableMode || Boolean(demoConfig.value?.stable_mode),
);
const demoQuestions = computed(() => {
  const questions = demoConfig.value?.questions?.filter((item) => item.text) ?? [];
  return (questions.length ? questions : FALLBACK_DEMO_QUESTIONS).slice(0, 6);
});
const stageEyebrow = computed(() => demoConfig.value?.product_name || 'Configurable Digital Human');
const stageTitle = computed(() => demoConfig.value?.project_name || '通用可配置数字人');
const opsCustomerLabel = computed(() => demoConfig.value?.customer_name || opsHealth.value?.customer_id || '-');
const fvsConversationItems = computed(() => {
  return conversation.value.filter((item) => item.role === 'user' || item.role === 'assistant').slice(0, 5);
});
const isVoicePanelExpanded = computed(() => {
  if (!isFvsHost.value) return true;
  return (
    isSending.value ||
    ttsPlayback.value === 'loading' ||
    ttsPlayback.value === 'playing' ||
    ['recording', 'followup_listening', 'thinking', 'speaking'].includes(listeningState.value)
  );
});

const fvsModeLabel = computed(() => {
  if (!fvsConfig.enabled) return 'FVS Mock Screen';
  if (fvsConfig.mode === 'iframe') return 'FVS iframe';
  return 'FVS web frame';
});

const fvsLogCode = computed(() => {
  if (!latestFvsEvent.value) {
    return fvsConfig.enabled ? `${fvsConfig.mode}.idle` : 'mockFvs.idle';
  }
  return `${latestFvsEvent.value.adapterMode}:${latestFvsEvent.value.fvsFunction}`;
});

const recordedAudioLabel = computed(() => {
  if (!recordedAudio.value) return '未录音';
  return `${Math.max(1, Math.round(recordedAudio.value.size / 1024))} KB`;
});

const voiceStyle = computed(() => ({
  '--voice-energy': voiceEnergy.value.toFixed(3),
  '--monitor-energy': monitorEnergy.value.toFixed(3),
}));

const listeningStateLabel = computed(() => {
  const labels: Record<ListeningState, string> = {
    idle: 'idle',
    monitoring: 'monitoring',
    wake_checking: 'wake_checking',
    recording: 'recording',
    followup_listening: 'followup_listening',
    thinking: 'thinking',
    speaking: 'speaking',
    cooldown: 'cooldown',
  };
  return labels[listeningState.value];
});

const wakeWordsLabel = computed(() => wakeConfig.value.wake_words.join(' / '));

const opsOverallStatus = computed<OpsStatus>(() => {
  if (opsDependencies.value?.status) return opsDependencies.value.status;
  return opsHealth.value?.status ?? 'unknown';
});
const configProjectFields = computed(() => configFieldEntries(configEffective.value?.project));
const configCustomerFields = computed(() => configFieldEntries(configEffective.value?.customer));
const configMockFields = computed(() => configFieldEntries(configEffective.value?.mock_switches));
const configSensitiveFields = computed(() => configFieldEntries(configEffective.value?.sensitive));
const configDashboardBackendFields = computed(() =>
  configFieldEntries(asConfigRecord(configEffective.value?.dashboard?.backend_effective)),
);
const configDashboardContractFields = computed(() =>
  configFieldEntries(asConfigRecord(configEffective.value?.dashboard?.frontend_runtime_contract)),
);
const configAskMetricsFields = computed(() =>
  configFieldEntries(asConfigRecord(asConfigRecord(configEffective.value?.capabilities).ask_metrics)),
);
const configKnowledgeFields = computed(() =>
  configFieldEntries(asConfigRecord(asConfigRecord(configEffective.value?.capabilities).knowledge)),
);
const configScreenControlFields = computed(() =>
  configFieldEntries(asConfigRecord(asConfigRecord(configEffective.value?.capabilities).screen_control)),
);
const configDoraFields = computed(() =>
  configFieldEntries(asConfigRecord(asConfigRecord(configEffective.value?.capabilities).dora)),
);
const configVoiceFields = computed(() =>
  configFieldEntries(asConfigRecord(asConfigRecord(configEffective.value?.capabilities).voice)),
);
const configPromptEntries = computed(() => Object.entries(asConfigRecord(configEffective.value?.prompt_profiles)));
const configImplementationEntries = computed(() => Object.entries(configEffective.value?.implementation_status ?? {}));
const configProvenanceNotes = computed(() => {
  const notes = configEffective.value?.provenance?.notes;
  return Array.isArray(notes) ? notes.map(String) : [];
});
const configDisabledEndpoints = computed(() => configSchema.value?.disabled_endpoints ?? []);
const frontendRuntimeFvsFields = computed(() => [
  ['enabled', { value: fvsConfig.enabled, source: 'frontend_runtime', sensitive: false } as ConfigField],
  ['mode', { value: fvsConfig.mode, source: 'frontend_runtime', sensitive: false } as ConfigField],
  ['url', { value: fvsConfig.url || '-', source: 'frontend_runtime', sensitive: false } as ConfigField],
  [
    'targetOrigin',
    { value: fvsConfig.targetOrigin || '-', source: 'frontend_runtime', sensitive: false } as ConfigField,
  ],
] as Array<[string, ConfigField]>);

const followupLabel = computed(() => {
  const maxTurns = wakeConfig.value.settings.max_followup_turns;
  if (!wakeConfig.value.settings.followup_enabled || maxTurns <= 0) return '连续对话关闭';
  return `连续 ${followupTurnsUsed.value}/${maxTurns}`;
});

const canUseManualVoice = computed(
  () => !listenerEnabled.value && !isRecording.value && !isAsrProcessing.value && !isSending.value,
);

onMounted(async () => {
  window.addEventListener('popstate', syncMainViewFromLocation);
  void getWakeGreetingAudioUrl();
  void getAcknowledgementAudioUrl();
  if (fvsConfig.enabled && fvsConfig.mode === 'iframe') {
    markFvsFrameLoading('FVS iframe 加载中。');
  }

  try {
    const response = await fetchScreenActions();
    actions.value = response.actions;
    activeActionId.value = response.actions[0]?.id ?? 'SWITCH_HOME';
    apiStatus.value = 'ready';
    statusText.value = fvsConfig.enabled ? 'FVS 通信已就绪' : 'Mock API 已连接';
  } catch (error) {
    apiStatus.value = 'error';
    statusText.value = error instanceof Error ? error.message : 'Mock API 连接失败';
  }

  try {
    wakeConfig.value = normalizeWakeConfig(await fetchWakeConfig());
  } catch (error) {
    wakeConfig.value = DEFAULT_WAKE_CONFIG;
    pushSystemMessage('唤醒词配置读取失败，已使用本地默认配置。');
  }

  try {
    demoConfig.value = await fetchDemoConfig();
  } catch (error) {
    demoConfigError.value = error instanceof Error ? error.message : '演示配置读取失败';
  }

  if (activeView.value === 'ops') {
    await loadOpsDashboard();
  } else if (activeView.value === 'config') {
    await loadConfigDashboard();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('popstate', syncMainViewFromLocation);
  clearFvsLoadTimer();
  stopBackgroundListening();
  stopRecording();
  stopMediaStream();
  cleanupAudio();
});

async function setMainView(view: MainView, updateUrl = true) {
  activeView.value = view;
  if (updateUrl) {
    const nextPath = view === 'config' ? '/ops/config' : view === 'ops' ? '/ops' : '/';
    const nextUrl = `${nextPath}${window.location.search}${window.location.hash}`;
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (nextUrl !== currentUrl) {
      window.history.pushState({}, '', nextUrl);
    }
  }
  if (view === 'ops' && !opsHealth.value && !opsLoading.value) {
    await loadOpsDashboard();
  } else if (view === 'config' && !configEffective.value && !configLoading.value) {
    await loadConfigDashboard();
  }
}

async function loadOpsDashboard() {
  opsLoading.value = true;
  opsErrorText.value = '';
  try {
    const [health, dependencies, sessions, errors, metrics] = await Promise.all([
      fetchOpsHealth(),
      fetchOpsDependencies(),
      fetchOpsSessions(20),
      fetchOpsErrors(30),
      fetchOpsMetrics(),
    ]);
    opsHealth.value = health;
    opsDependencies.value = dependencies;
    opsSessions.value = sessions.sessions;
    opsErrors.value = errors.errors;
    opsMetrics.value = metrics;
    opsLastUpdated.value = formatOpsTime(new Date().toISOString());
  } catch (error) {
    opsErrorText.value = error instanceof Error ? error.message : '运维数据读取失败';
  } finally {
    opsLoading.value = false;
  }
}

async function exportOpsLogs() {
  opsExporting.value = true;
  opsErrorText.value = '';
  try {
    const content = await fetchOpsExport(80);
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `zt-ops-log-${new Date().toISOString().replace(/[:.]/g, '-')}.md`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    opsErrorText.value = error instanceof Error ? error.message : '日志导出失败';
  } finally {
    opsExporting.value = false;
  }
}

async function loadConfigDashboard() {
  configLoading.value = true;
  configErrorText.value = '';
  try {
    const [effective, schema] = await Promise.all([fetchConfigEffective(), fetchConfigSchema()]);
    configEffective.value = effective;
    configSchema.value = schema;
  } catch (error) {
    configErrorText.value = error instanceof Error ? error.message : '配置快照读取失败';
  } finally {
    configLoading.value = false;
  }
}

async function submitQuestion(
  textOverride?: string,
  mode: InputMode = 'text',
  options: SubmitQuestionOptions = {},
): Promise<ConversationItem | null> {
  const text = (textOverride ?? inputText.value).trim();
  if (!text || isSending.value) return null;

  isSending.value = true;
  conversation.value.unshift({
    id: crypto.randomUUID(),
    role: 'user',
    text,
  });

  try {
    const requestPayload = {
      session_id: sessionId,
      text,
      context: {
        screen_id: activeAction.value?.id ?? 'unknown',
        mode,
      },
    };
    const assistantItem: ConversationItem = {
      id: crypto.randomUUID(),
      role: 'assistant',
      text: '正在思考...',
      tts: { status: 'loading', label: '等待首段音频', segments: [], nextSegmentIndex: 0 },
    };
    conversation.value.unshift(assistantItem);

    let response: ChatResponse | null = null;
    let earlyStreamingPlayback: Promise<AudioPlaybackResult> | null = null;
    try {
      await streamChat(requestPayload, {
        onDelta(delta) {
          if (!assistantItem.response && delta.trim()) {
            assistantItem.text = assistantItem.text === '正在思考...' ? delta : `${assistantItem.text}${delta}`;
          }
        },
        onTtsReady(segment) {
          addTtsSegment(assistantItem, segment);
        },
        onTtsError(payload) {
          assistantItem.tts = {
            ...(assistantItem.tts ?? { status: 'error' }),
            status: 'error',
            label: '分段失败',
            error: payload.message || 'TTS 分段合成失败',
          };
        },
        onAnswer(streamResponse) {
          response = streamResponse;
          assistantItem.text = streamResponse.speak_text;
          assistantItem.response = streamResponse;
          assistantItem.tts = {
            ...(assistantItem.tts ?? { status: 'loading' }),
            streamEnded: true,
          };
          if (options.awaitTts && !earlyStreamingPlayback) {
            earlyStreamingPlayback = playAutoStreamingTts(
              streamResponse.speak_text,
              '真流式 TTS',
              true,
              options.beforeAutoTts,
            );
          }
        },
      });
    } catch (streamError) {
      response = await sendChat(requestPayload);
      assistantItem.text = response.speak_text;
      assistantItem.response = response;
      assistantItem.tts = { status: 'loading', label: '合成中' };
      pushSystemMessage(
        streamError instanceof Error ? `流式链路失败，已回退：${streamError.message}` : '流式链路失败，已回退。',
      );
    }

    if (!response) {
      throw new Error('Dora 未返回最终回答');
    }

    if (response.type === 'screen_control' && response.action) {
      const executeResponse = await executeScreenAction({
        session_id: response.session_id,
        action_id: response.action.id,
        target: response.action.target,
      });
      await applyFvsAction(executeResponse);
    }

    if (options.awaitTts && earlyStreamingPlayback) {
      const streamResult = await earlyStreamingPlayback;
      if (streamResult === 'ended') {
        assistantItem.tts = {
          ...(assistantItem.tts ?? { status: 'ready' }),
          status: 'ready',
          label: '真流式 TTS',
        };
        finishMonitorTurn('播报完成，等待继续提问。');
        if (!textOverride) {
          inputText.value = '';
        }
        return assistantItem;
      }
      if (streamResult === 'interrupted') {
        return assistantItem;
      }
    }

    if (assistantItem.tts?.segments?.length) {
      assistantItem.tts.streamEnded = true;
      assistantItem.tts.status = 'ready';
      assistantItem.tts.label = '分段 TTS';
      if (options.awaitTts) {
        await waitBeforeAutoTts(options.beforeAutoTts);
        await playConversationTts(assistantItem, {
          monitorPlayback: true,
          preferStreaming: !earlyStreamingPlayback,
        });
      }
    } else if (options.awaitTts) {
      await prepareTtsForItem(assistantItem);
    } else {
      void prepareTtsForItem(assistantItem);
    }
    if (!textOverride) {
      inputText.value = '';
    }
    return assistantItem;
  } catch (error) {
    pushSystemMessage(error instanceof Error ? error.message : '请求失败');
    return null;
  } finally {
    isSending.value = false;
  }
}

async function startRecording() {
  if (isRecording.value) return;
  if (listenerEnabled.value) {
    stopBackgroundListening();
  }
  const AudioContextCtor = getAudioContextCtor();
  if (!navigator.mediaDevices?.getUserMedia || !AudioContextCtor) {
    pushSystemMessage('当前浏览器不支持录音，请使用 Mock ASR 文本。');
    return;
  }

  try {
    recordedAudio.value = null;
    recordedSamples = [];
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorderAudioContext = new AudioContextCtor();
    recordingSampleRate = recorderAudioContext.sampleRate;
    recorderSource = recorderAudioContext.createMediaStreamSource(mediaStream);
    recorderProcessor = recorderAudioContext.createScriptProcessor(4096, 1, 1);
    recorderProcessor.onaudioprocess = (event) => {
      recordedSamples.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
    recorderSource.connect(recorderProcessor);
    recorderProcessor.connect(recorderAudioContext.destination);
    recorderMimeType.value = 'audio/wav';
    if (recorderAudioContext.state === 'suspended') {
      await recorderAudioContext.resume();
    }
    isRecording.value = true;
    asrText.value = '';
  } catch (error) {
    isRecording.value = false;
    stopMediaStream();
    pushSystemMessage(describeMediaError(error, '录音启动失败'));
  }
}

function stopRecording() {
  if (isRecording.value) {
    const samples = mergeSamples(recordedSamples);
    if (samples.length > 0) {
      recordedAudio.value = encodeWav(samples, recordingSampleRate, 16000);
    } else {
      recordedAudio.value = null;
    }
    isRecording.value = false;
    stopMediaStream();
    return;
  }
  isRecording.value = false;
  stopMediaStream();
}

async function transcribeAndSend() {
  if (isAsrProcessing.value || isSending.value) return;

  isAsrProcessing.value = true;
  try {
    const audioBase64 = recordedAudio.value ? await blobToBase64(recordedAudio.value) : null;
    const response = await transcribeAudio({
      session_id: sessionId,
      mock_text: asrMockText.value,
      audio_base64: audioBase64,
      audio_format: recordedAudio.value?.type || recorderMimeType.value || 'mock',
    });

    if (!response.success || !response.text) {
      throw new Error(response.error?.message || 'ASR 识别失败');
    }

    asrText.value = response.text;
    await submitQuestion(response.text, 'voice');
  } catch (error) {
    pushSystemMessage(error instanceof Error ? error.message : 'ASR 识别失败');
  } finally {
    isAsrProcessing.value = false;
  }
}

async function onListenerToggle(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.checked) {
    await startBackgroundListening();
  } else {
    stopBackgroundListening();
  }
  target.checked = listenerEnabled.value;
}

async function toggleVoiceDock() {
  if (listenerEnabled.value) {
    stopBackgroundListening();
    return;
  }
  await startBackgroundListening();
}

async function startBackgroundListening() {
  if (listenerEnabled.value) return;
  const AudioContextCtor = getAudioContextCtor();
  if (!navigator.mediaDevices?.getUserMedia || !AudioContextCtor) {
    pushSystemMessage('当前浏览器不支持后台监听，请使用手动录音。');
    return;
  }

  if (isRecording.value) {
    stopRecording();
  }

  try {
    clearMonitorTimers();
    resetVadSegment();
    monitorStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    monitorAudioContext = new AudioContextCtor();
    monitorSampleRate = monitorAudioContext.sampleRate;
    monitorSource = monitorAudioContext.createMediaStreamSource(monitorStream);
    monitorProcessor = monitorAudioContext.createScriptProcessor(4096, 1, 1);
    monitorGain = monitorAudioContext.createGain();
    monitorGain.gain.value = 0;
    monitorProcessor.onaudioprocess = handleMonitorAudioProcess;
    monitorSource.connect(monitorProcessor);
    monitorProcessor.connect(monitorGain);
    monitorGain.connect(monitorAudioContext.destination);
    if (monitorAudioContext.state === 'suspended') {
      await monitorAudioContext.resume();
    }
    listenerEnabled.value = true;
    resetFollowupSession();
    setListeningState('monitoring', `等待唤醒词：${wakeWordsLabel.value}`);
  } catch (error) {
    cleanupMonitorStream();
    listenerEnabled.value = false;
    setListeningState('idle', '麦克风授权失败。');
    pushSystemMessage(describeMediaError(error, '后台监听启动失败'));
  }
}

function stopBackgroundListening() {
  listenerEnabled.value = false;
  clearMonitorTimers();
  resetVadSegment();
  resetFollowupSession();
  cleanupMonitorStream();
  monitorEnergy.value = 0;
  setListeningState('idle', '未开启');
}

function handleMonitorAudioProcess(event: AudioProcessingEvent) {
  const frame = new Float32Array(event.inputBuffer.getChannelData(0));
  const rms = calculateRms(frame);
  const threshold = wakeConfig.value.settings.vad_threshold;
  monitorEnergy.value = Math.min(1, Math.max(monitorEnergy.value * 0.72, rms / Math.max(0.001, threshold * 3)));

  if (!listenerEnabled.value || monitorFinalizing) return;
  if (listeningState.value === 'monitoring') {
    collectVadFrame(frame, rms, 'wake');
  } else if (listeningState.value === 'recording' || listeningState.value === 'followup_listening') {
    collectVadFrame(frame, rms, 'command');
  } else if (listeningState.value === 'speaking' && shouldCollectBargeInFrame()) {
    collectVadFrame(frame, rms, 'barge_in');
  }
}

function collectVadFrame(frame: Float32Array, rms: number, kind: VadSegmentKind) {
  const now = performance.now();
  const segmentSettings = getVadSegmentSettings(kind);
  const hasSpeech = rms >= segmentSettings.vadThreshold;
  if (!monitorSpeechActive) {
    if (!hasSpeech) {
      monitorSpeechCandidateFrames = 0;
      rememberVadPrerollFrame(frame);
      return;
    }
    monitorSpeechCandidateFrames += 1;
    if (monitorSpeechCandidateFrames < MONITOR_SPEECH_START_FRAMES) {
      rememberVadPrerollFrame(frame);
      return;
    }
    if (kind === 'command' && monitorCommandTimer !== null) {
      clearTimeout(monitorCommandTimer);
      monitorCommandTimer = null;
    }
    monitorSpeechActive = true;
    monitorSpeechStartedAt = now;
    monitorLastSpeechAt = now;
    monitorSamples = monitorPrerollSamples.slice();
    monitorPrerollSamples = [];
  }

  monitorSamples.push(frame);
  if (hasSpeech) {
    monitorLastSpeechAt = now;
  }

  const elapsedMs = now - monitorSpeechStartedAt;
  const silenceMs = now - monitorLastSpeechAt;
  if (
    (elapsedMs >= segmentSettings.minAudioMs && silenceMs >= segmentSettings.silenceMs) ||
    elapsedMs >= segmentSettings.maxAudioMs
  ) {
    void finalizeVadSegment(kind);
  }
}

async function finalizeVadSegment(kind: VadSegmentKind) {
  if (monitorFinalizing) return;
  monitorFinalizing = true;
  const samples = mergeSamples(monitorSamples);
  const durationMs = (samples.length / Math.max(1, monitorSampleRate)) * 1000;
  const segmentSettings = getVadSegmentSettings(kind);
  resetVadSegment();

  try {
    if (durationMs < segmentSettings.minAudioMs * 0.6 || samples.length === 0) {
      if (listenerEnabled.value && listeningState.value === 'recording') {
        beginCommandRecording();
      } else if (listenerEnabled.value && listeningState.value === 'followup_listening') {
        beginFollowupListening('片段过短，可继续提问。');
      }
      return;
    }

    const audioBlob = encodeWav(samples, monitorSampleRate, 16000);
    if (kind === 'wake') {
      await processWakeSegment(audioBlob);
    } else if (kind === 'barge_in') {
      await processBargeInSegment(audioBlob);
    } else {
      await processCommandSegment(audioBlob);
    }
  } finally {
    monitorFinalizing = false;
  }
}

async function processBargeInSegment(audioBlob: Blob) {
  if (!listenerEnabled.value || !wakeConfig.value.settings.barge_in_enabled) return;
  try {
    const response = await transcribeMonitorAudio(audioBlob);
    if (!listenerEnabled.value || !response.success || !response.text) return;

    const matchedWakeWord = findWakeWord(response.text, getBargeInWakeWords());
    if (!matchedWakeWord) return;

    wakeCheckText.value = response.text;
    cleanupAudio();
    playWakeGreetingPrompt();
    startFollowupSession();

    const inlineCommand = stripWakeWord(response.text, matchedWakeWord);
    if (inlineCommand) {
      await runMonitorCommand(inlineCommand);
      return;
    }

    beginCommandRecording();
  } catch {
    // Barge-in checks are opportunistic. Failed or empty ASR results should not disturb playback.
  }
}

async function processWakeSegment(audioBlob: Blob) {
  if (!listenerEnabled.value) return;
  setListeningState('wake_checking', '正在判断唤醒词。');
  try {
    const response = await transcribeMonitorAudio(audioBlob);
    if (!listenerEnabled.value) return;
    if (!response.success || !response.text) {
      throw new Error(response.error?.message || '唤醒识别失败');
    }

    wakeCheckText.value = response.text;
    const matchedWakeWord = findWakeWord(response.text);
    if (!matchedWakeWord) {
      wakeMissCount.value += 1;
      enterMonitorCooldown('未命中唤醒词，短音频已丢弃。');
      return;
    }

    playWakeGreetingPrompt();
    startFollowupSession();
    const inlineCommand = stripWakeWord(response.text, matchedWakeWord);
    if (inlineCommand) {
      await runMonitorCommand(inlineCommand);
      return;
    }

    beginCommandRecording();
  } catch (error) {
    enterMonitorCooldown(error instanceof Error ? error.message : '唤醒识别失败');
  }
}

function beginCommandRecording() {
  if (!listenerEnabled.value) return;
  clearMonitorTimers();
  resetVadSegment();
  commandText.value = '';
  setListeningState('recording', '已唤醒，等待正式指令。');
  monitorCommandTimer = window.setTimeout(() => {
    if (listenerEnabled.value && listeningState.value === 'recording') {
      enterMonitorCooldown('唤醒后未听到指令，已回到监听。');
    }
  }, wakeConfig.value.settings.command_timeout_ms);
}

function beginFollowupListening(detail = '可直接继续提问。') {
  if (!listenerEnabled.value) return;
  clearMonitorTimers();
  resetVadSegment();
  commandText.value = '';
  setListeningState('followup_listening', detail);
  monitorCommandTimer = window.setTimeout(() => {
    if (listenerEnabled.value && listeningState.value === 'followup_listening') {
      enterMonitorCooldown('连续对话超时，已回到唤醒监听。');
    }
  }, wakeConfig.value.settings.followup_window_ms);
}

async function processCommandSegment(audioBlob: Blob) {
  if (!listenerEnabled.value) return;
  const isFollowup = listeningState.value === 'followup_listening';
  clearMonitorTimers();
  setListeningState('thinking', '正在识别指令。');
  try {
    const response = await transcribeMonitorAudio(audioBlob);
    if (!listenerEnabled.value) return;
    if (!response.success || !response.text) {
      throw new Error(response.error?.message || '指令识别失败');
    }
    await runMonitorCommand(stripAllWakeWords(response.text) || response.text, { isFollowup });
  } catch (error) {
    enterMonitorCooldown(error instanceof Error ? error.message : '指令识别失败');
  }
}

async function runMonitorCommand(text: string, options: MonitorCommandOptions = {}) {
  const cleanedText = stripAllWakeWords(text).trim();
  if (!cleanedText) {
    enterMonitorCooldown('未识别到有效指令，继续等待唤醒。');
    return;
  }

  if (options.isFollowup) {
    followupTurnsUsed.value += 1;
  }
  commandText.value = cleanedText;
  setListeningState('thinking', '正在处理指令。');
  const acknowledgementPlayback = playAcknowledgementPrompt();
  const assistantItem = await submitQuestion(cleanedText, 'voice', {
    awaitTts: true,
    beforeAutoTts: acknowledgementPlayback,
  });
  if (!listenerEnabled.value) return;

  if (assistantItem?.tts?.status === 'ready') {
    return;
  }

  finishMonitorTurn('已完成处理，等待继续提问。');
}

async function executeWhitelistedScreenAction(actionId: string) {
  if (isSending.value) return;
  try {
    const executeResponse = await executeScreenAction({
      session_id: sessionId,
      action_id: actionId,
    });
    await applyFvsAction(executeResponse);
  } catch (error) {
    pushSystemMessage(error instanceof Error ? error.message : '大屏动作执行失败');
  }
}

function startFollowupSession() {
  followupTurnsUsed.value = 0;
}

function resetFollowupSession() {
  followupTurnsUsed.value = 0;
}

function canContinueFollowup(): boolean {
  const settings = wakeConfig.value.settings;
  return settings.followup_enabled && settings.max_followup_turns > 0 && followupTurnsUsed.value < settings.max_followup_turns;
}

function finishMonitorTurn(detail: string) {
  if (!listenerEnabled.value) {
    setListeningState('idle', '未开启');
    return;
  }
  if (canContinueFollowup()) {
    beginFollowupListening(`${detail} ${followupLabel.value}`);
    return;
  }
  enterMonitorCooldown('连续对话轮次已结束，回到唤醒监听。');
}

async function transcribeMonitorAudio(audioBlob: Blob) {
  const audioBase64 = await blobToBase64(audioBlob);
  return transcribeAudio({
    session_id: sessionId,
    mock_text: asrMockText.value || null,
    audio_base64: audioBase64,
    audio_format: audioBlob.type || 'audio/wav',
  });
}

function enterMonitorCooldown(detail: string) {
  clearMonitorTimers();
  resetVadSegment();
  resetFollowupSession();
  if (!listenerEnabled.value) {
    setListeningState('idle', '未开启');
    return;
  }

  setListeningState('cooldown', detail);
  monitorCooldownTimer = window.setTimeout(() => {
    if (listenerEnabled.value && listeningState.value === 'cooldown') {
      setListeningState('monitoring', `等待唤醒词：${wakeWordsLabel.value}`);
    }
  }, wakeConfig.value.settings.cooldown_ms);
}

function setListeningState(state: ListeningState, detail: string) {
  listeningState.value = state;
  listeningDetail.value = detail;
}

function findWakeWord(text: string, wakeWords = wakeConfig.value.wake_words): string | null {
  const normalizedText = normalizeWakeText(text);
  const sortedWakeWords = [...wakeWords].sort(
    (left, right) => normalizeWakeText(right).length - normalizeWakeText(left).length,
  );
  for (const word of sortedWakeWords) {
    const normalizedWord = normalizeWakeText(word);
    if (!normalizedWord) continue;
    if (wakeConfig.value.settings.require_exact_phrase) {
      if (normalizedText === normalizedWord) return word;
    } else if (normalizedText.includes(normalizedWord)) {
      return word;
    }
  }
  return null;
}

function stripWakeWord(text: string, wakeWord: string): string {
  const pattern = buildWakeWordPattern(wakeWord);
  return text.replace(pattern, '').replace(/^[\s,，。.!！?？、]+/, '').trim();
}

function stripAllWakeWords(text: string): string {
  return wakeConfig.value.wake_words.reduce((result, word) => stripWakeWord(result, word), text).trim();
}

function buildWakeWordPattern(wakeWord: string): RegExp {
  const pieces = Array.from(wakeWord).map((char) => {
    if (char === '小') return '[小晓肖]';
    if (char === '天') return '[天田甜添填]';
    return escapeRegExp(char);
  });
  return new RegExp(`${pieces.join('[\\s,，。.!！?？、]*')}[\\s,，。.!！?？、]*`, 'i');
}

function normalizeWakeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[\s,，。.!！?？、]/g, '')
    .replace(/[晓肖]/g, '小')
    .replace(/[田甜添填]/g, '天');
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function calculateRms(samples: Float32Array): number {
  if (samples.length === 0) return 0;
  let sum = 0;
  for (const sample of samples) {
    sum += sample * sample;
  }
  return Math.sqrt(sum / samples.length);
}

function resetVadSegment() {
  monitorSamples = [];
  monitorPrerollSamples = [];
  monitorSpeechActive = false;
  monitorSpeechStartedAt = 0;
  monitorLastSpeechAt = 0;
  monitorSpeechCandidateFrames = 0;
}

function rememberVadPrerollFrame(frame: Float32Array) {
  monitorPrerollSamples.push(frame);
  const maxSamples = Math.max(1, Math.round((monitorSampleRate * MONITOR_PREROLL_MS) / 1000));
  let totalSamples = monitorPrerollSamples.reduce((sum, chunk) => sum + chunk.length, 0);
  while (totalSamples > maxSamples && monitorPrerollSamples.length > 1) {
    const removed = monitorPrerollSamples.shift();
    totalSamples -= removed?.length ?? 0;
  }
}

function clearMonitorTimers() {
  if (monitorCommandTimer !== null) {
    clearTimeout(monitorCommandTimer);
    monitorCommandTimer = null;
  }
  if (monitorCooldownTimer !== null) {
    clearTimeout(monitorCooldownTimer);
    monitorCooldownTimer = null;
  }
}

function cleanupMonitorStream() {
  monitorProcessor?.disconnect();
  monitorSource?.disconnect();
  monitorGain?.disconnect();
  if (monitorAudioContext && monitorAudioContext.state !== 'closed') {
    void monitorAudioContext.close();
  }
  monitorProcessor = null;
  monitorSource = null;
  monitorGain = null;
  monitorAudioContext = null;
  monitorStream?.getTracks().forEach((track) => track.stop());
  monitorStream = null;
}

function normalizeWakeConfig(config: WakeConfigResponse): WakeConfigResponse {
  return {
    ...DEFAULT_WAKE_CONFIG,
    ...config,
    wake_words: config.wake_words?.length ? config.wake_words : DEFAULT_WAKE_CONFIG.wake_words,
    settings: {
      ...DEFAULT_WAKE_CONFIG.settings,
      ...(config.settings ?? {}),
    },
  };
}

function getVadSegmentSettings(kind: VadSegmentKind) {
  const settings = wakeConfig.value.settings;
  if (kind === 'barge_in') {
    return {
      minAudioMs: settings.barge_in_min_audio_ms,
      maxAudioMs: settings.barge_in_max_audio_ms,
      silenceMs: settings.barge_in_silence_ms,
      vadThreshold: settings.barge_in_vad_threshold,
    };
  }

  return {
    minAudioMs: settings.min_audio_ms,
    maxAudioMs: kind === 'wake' ? settings.max_audio_ms : settings.command_timeout_ms,
    silenceMs: settings.silence_ms,
    vadThreshold: settings.vad_threshold,
  };
}

function shouldCollectBargeInFrame(): boolean {
  const settings = wakeConfig.value.settings;
  if (!settings.barge_in_enabled || getBargeInWakeWords().length === 0) return false;
  if (monitorPlaybackStartedAt <= 0) return false;
  return performance.now() - monitorPlaybackStartedAt >= settings.barge_in_ignore_after_tts_start_ms;
}

function getBargeInWakeWords(): string[] {
  const configuredWords = wakeConfig.value.settings.barge_in_wake_words
    .map((word) => word.trim())
    .filter(Boolean);
  if (configuredWords.length > 0) return configuredWords;
  return wakeConfig.value.wake_words.filter((word) => normalizeWakeText(word).length >= normalizeWakeText('小智小智').length);
}

function beginMonitorSpeakingState() {
  monitorPlaybackStartedAt = performance.now();
  resetVadSegment();
  setListeningState('speaking', '正在播报回复。');
}

function getWakeGreetingAudioUrl(): Promise<string | null> {
  if (wakeGreetingAudioUrl) return Promise.resolve(wakeGreetingAudioUrl);
  if (wakeGreetingAudioPromise) return wakeGreetingAudioPromise;

  wakeGreetingAudioPromise = synthesizeSpeech({
    text: WAKE_GREETING_TEXT,
    voice: 'longanyang',
    format: 'mp3',
  })
    .then((response) => {
      wakeGreetingAudioUrl = response.success && response.audio_url ? response.audio_url : null;
      return wakeGreetingAudioUrl;
    })
    .catch(() => null)
    .finally(() => {
      wakeGreetingAudioPromise = null;
    });
  return wakeGreetingAudioPromise;
}

function getAcknowledgementAudioUrl(): Promise<string | null> {
  if (acknowledgementAudioUrl) return Promise.resolve(acknowledgementAudioUrl);
  if (acknowledgementAudioPromise) return acknowledgementAudioPromise;

  acknowledgementAudioPromise = synthesizeSpeech({
    text: ACKNOWLEDGEMENT_TEXT,
    voice: 'longanyang',
    format: 'mp3',
  })
    .then((response) => {
      acknowledgementAudioUrl = response.success && response.audio_url ? response.audio_url : null;
      return acknowledgementAudioUrl;
    })
    .catch(() => null)
    .finally(() => {
      acknowledgementAudioPromise = null;
    });
  return acknowledgementAudioPromise;
}

function playWakeGreetingPrompt() {
  ttsStatusText.value = WAKE_GREETING_TEXT;
  enqueuePromptPlayback(WAKE_GREETING_TEXT, '唤醒提示', getWakeGreetingAudioUrl, () => listenerEnabled.value);
}

function playAcknowledgementPrompt(): Promise<void> {
  setListeningState('thinking', '已收到，正在查找信息。');
  ttsStatusText.value = ACKNOWLEDGEMENT_TEXT;
  return enqueuePromptPlayback(ACKNOWLEDGEMENT_TEXT, '等待提示', getAcknowledgementAudioUrl, () => !activeStreamPlayback);
}

function enqueuePromptPlayback(
  text: string,
  label: string,
  getAudioUrl: () => Promise<string | null>,
  shouldPlay: () => boolean,
) {
  const playbackTask = promptPlaybackQueue
    .catch(() => undefined)
    .then(async () => {
      if (!shouldPlay() || activeAudio || activeSpeechUtterance || activeStreamPlayback) return;

      const cachedAudioUrl = text === WAKE_GREETING_TEXT ? wakeGreetingAudioUrl : acknowledgementAudioUrl;
      if (cachedAudioUrl) {
        await playAudioUrl(cachedAudioUrl, label);
        return;
      }

      void getAudioUrl();
      await playLocalPrompt(text, label);
    });
  promptPlaybackQueue = playbackTask.catch(() => undefined);
  return playbackTask.catch(() => undefined);
}

async function playLocalPrompt(text: string, label: string): Promise<AudioPlaybackResult> {
  if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
    return 'blocked';
  }

  cleanupAudio();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'zh-CN';
  activeSpeechUtterance = utterance;
  ttsPlayback.value = 'playing';
  ttsStatusText.value = `${label}播报中`;
  voiceEnergy.value = 0.42;

  const playbackResult = new Promise<'ended' | 'error'>((resolve) => {
    utterance.onend = () => resolve('ended');
    utterance.onerror = () => resolve('error');
  });

  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);

  const result = await Promise.race([playbackResult, waitForSpeechInterruption(utterance)]);
  if (result === 'interrupted') {
    return result;
  }
  if (result === 'ended') {
    if (activeSpeechUtterance !== utterance) return 'interrupted';
    activeSpeechUtterance = null;
    voiceEnergy.value = 0;
    ttsPlayback.value = 'idle';
    ttsStatusText.value = `${label}播报完成`;
    return result;
  }
  if (activeSpeechUtterance === utterance) {
    activeSpeechUtterance = null;
    voiceEnergy.value = 0;
    ttsPlayback.value = 'error';
    ttsStatusText.value = `${label}播放失败`;
  }
  return 'error';
}

function waitForSpeechInterruption(utterance: SpeechSynthesisUtterance): Promise<'interrupted'> {
  return new Promise((resolve) => {
    const tick = () => {
      if (activeSpeechUtterance !== utterance) {
        resolve('interrupted');
        return;
      }
      window.setTimeout(tick, 80);
    };
    window.setTimeout(tick, 80);
  });
}

async function prepareTtsForItem(item: ConversationItem) {
  if (!item.tts || item.role !== 'assistant') return;
  if (item.tts.segments?.length) return;
  ttsPlayback.value = 'loading';
  ttsStatusText.value = 'TTS 合成中';
  try {
    const response = await synthesizeSpeech({
      text: item.text,
      voice: 'longanyang',
      format: 'mp3',
    });
    if (!response.success || !response.audio_url) {
      throw new Error(response.error?.message || 'TTS 合成失败');
    }

    item.tts = {
      status: 'ready',
      audioUrl: response.audio_url,
      label: response.mock ? 'Mock TTS' : response.provider,
    };
    ttsPlayback.value = 'idle';
    ttsStatusText.value = 'TTS 已就绪';
  } catch (error) {
    const message = error instanceof Error ? error.message : 'TTS 合成失败';
    item.tts = {
      status: 'error',
      label: '无音频',
      error: message,
    };
    ttsPlayback.value = 'error';
    ttsStatusText.value = message;
  }
}

async function waitBeforeAutoTts(beforeAutoTts?: Promise<unknown> | null) {
  if (!beforeAutoTts) return;
  await Promise.race([beforeAutoTts.catch(() => undefined), wait(ACKNOWLEDGEMENT_TTS_MAX_WAIT_MS)]);
}

async function playAutoStreamingTts(
  text: string,
  label: string,
  monitorPlayback: boolean,
  beforeAutoTts?: Promise<unknown> | null,
): Promise<AudioPlaybackResult> {
  await waitBeforeAutoTts(beforeAutoTts);
  return playStreamingTtsText(text, label, monitorPlayback);
}

function addTtsSegment(item: ConversationItem, segment: ChatStreamTtsReady) {
  const current = item.tts ?? { status: 'loading' as const, label: '分段 TTS' };
  const segments = [...(current.segments ?? []).filter((entry) => entry.index !== segment.index), segment].sort(
    (left, right) => left.index - right.index,
  );
  item.tts = {
    ...current,
    status: 'ready',
    audioUrl: segments[0]?.audio_url ?? current.audioUrl,
    label: segment.mock ? 'Mock 分段 TTS' : '分段 TTS',
    segments,
    nextSegmentIndex: current.nextSegmentIndex ?? 0,
  };
  if (!activeStreamPlayback) {
    ttsPlayback.value = ttsPlayback.value === 'playing' || ttsPlayback.value === 'loading' ? ttsPlayback.value : 'idle';
    ttsStatusText.value = `TTS 第 ${segment.index + 1} 段已就绪`;
  }
}

async function playStreamingTtsText(
  text: string,
  label: string,
  monitorPlayback = false,
): Promise<AudioPlaybackResult> {
  const trimmedText = text.trim();
  const AudioContextCtor = getAudioContextCtor();
  if (!trimmedText || !AudioContextCtor) return 'error';

  cleanupAudio();
  const streamPlayback = createPcmStreamPlayback(new AudioContextCtor());
  activeStreamPlayback = streamPlayback;
  audioContext = streamPlayback.audioContext;
  ttsPlayback.value = 'loading';
  ttsStatusText.value = '等待首个音频 chunk';

  try {
    await streamPlayback.audioContext.resume();
    startStreamVoiceMeter(streamPlayback);

    let receivedAudio = false;
    let streamError = '';
    const endPayload = await streamSpeech(
      {
        text: trimmedText,
        voice: 'longanyang',
        format: 'pcm',
      },
      {
        onMetadata(metadata) {
          if (activeStreamPlayback !== streamPlayback) return;
          ttsStatusText.value = `${metadata.mock ? 'Mock ' : ''}${label} 已连接`;
        },
        onAudioChunk(chunk) {
          if (activeStreamPlayback !== streamPlayback) return;
          schedulePcmAudioChunk(streamPlayback, chunk);
          if (!receivedAudio) {
            receivedAudio = true;
            ttsPlayback.value = 'playing';
            ttsStatusText.value = `${label} 播报中`;
            if (monitorPlayback) {
              beginMonitorSpeakingState();
            }
          }
        },
        onTtsError(payload) {
          streamError = payload.message || 'TTS 真流式失败';
        },
      },
    );

    if (activeStreamPlayback !== streamPlayback) return 'interrupted';
    if (!endPayload.ok || streamError) {
      throw new Error(streamError || 'TTS 真流式失败');
    }
    if (!receivedAudio) {
      throw new Error('TTS 真流式未返回音频');
    }

    await waitForPcmStreamPlaybackEnd(streamPlayback);
    if (activeStreamPlayback !== streamPlayback) return 'interrupted';
    cleanupAudio();
    ttsPlayback.value = 'idle';
    ttsStatusText.value = '播报完成';
    return 'ended';
  } catch (error) {
    if (activeStreamPlayback !== streamPlayback) return 'interrupted';
    cleanupAudio();
    if (error instanceof Error && error.name === 'NotAllowedError') {
      ttsPlayback.value = 'idle';
      ttsStatusText.value = '音频已就绪';
      return 'blocked';
    }
    ttsPlayback.value = 'error';
    ttsStatusText.value = error instanceof Error ? error.message : 'TTS 真流式失败';
    return 'error';
  }
}

async function playConversationTts(item: ConversationItem, options: PlaybackOptions = {}) {
  if (options.preferStreaming !== false) {
    const streamResult = await playStreamingTtsText(item.text, '真流式 TTS', options.monitorPlayback);
    if (streamResult === 'ended') {
      if (options.monitorPlayback) {
        finishMonitorTurn('播报完成，等待继续提问。');
      }
      return;
    }
    if (streamResult === 'interrupted') return;
  }

  if (item.tts?.segments?.length) {
    await playSegmentedConversationTts(item, options);
    return;
  }
  if (!item.tts?.audioUrl) return;

  const result = await playAudioUrl(item.tts.audioUrl, item.tts.label ?? 'TTS', options.monitorPlayback);
  if (!options.monitorPlayback) return;
  if (result === 'interrupted') return;
  if (result === 'ended') {
    finishMonitorTurn('播报完成，等待继续提问。');
  } else if (result === 'blocked') {
    finishMonitorTurn('浏览器阻止自动播报，已保留音频控件。');
  } else {
    finishMonitorTurn('TTS 播放失败，仍可继续提问。');
  }
}

async function playSegmentedConversationTts(item: ConversationItem, options: PlaybackOptions = {}) {
  if (activeSegmentPlaybackItemId === item.id) return;
  activeSegmentPlaybackItemId = item.id;
  try {
    if (options.monitorPlayback) {
      beginMonitorSpeakingState();
    }
    while (true) {
      const tts = item.tts;
      const nextIndex = tts?.nextSegmentIndex ?? 0;
      const segment = tts?.segments?.find((entry) => entry.index === nextIndex);
      if (segment) {
        item.tts = { ...(tts ?? { status: 'ready' as const }), nextSegmentIndex: nextIndex + 1 };
        const result = await playAudioUrl(segment.audio_url, tts?.label ?? '分段 TTS', options.monitorPlayback);
        if (result !== 'ended') {
          if (options.monitorPlayback && result !== 'interrupted') {
            finishMonitorTurn(result === 'blocked' ? '浏览器阻止自动播报，已保留音频控件。' : 'TTS 播放失败，仍可继续提问。');
          }
          return;
        }
        continue;
      }
      if (tts?.streamEnded) break;
      await wait(120);
    }
    if (options.monitorPlayback) {
      finishMonitorTurn('播报完成，等待继续提问。');
    }
  } finally {
    activeSegmentPlaybackItemId = null;
  }
}

async function playAudioUrl(
  audioUrl: string,
  label: string,
  monitorPlayback = false,
): Promise<AudioPlaybackResult> {
  cleanupAudio();
  ttsPlayback.value = 'loading';
  ttsStatusText.value = '音频载入中';

  try {
    const audio = new Audio();
    audio.crossOrigin = 'anonymous';
    audio.src = toApiUrl(audioUrl);
    activeAudio = audio;
    const analyser = createAudioAnalyser(audio);

    const playbackResult = new Promise<'ended' | 'error'>((resolve) => {
      audio.addEventListener('ended', () => resolve('ended'), { once: true });
      audio.addEventListener('error', () => resolve('error'), { once: true });
    });

    await audio.play();
    ttsPlayback.value = 'playing';
    ttsStatusText.value = `${label} 播报中`;
    if (monitorPlayback) {
      beginMonitorSpeakingState();
    }
    if (analyser) {
      await audioContext?.resume();
      startVoiceMeter(audio, analyser);
    }
    const result = await Promise.race([playbackResult, waitForAudioInterruption(audio)]);
    if (result === 'interrupted') {
      return result;
    }
    cleanupAudio();
    ttsPlayback.value = result === 'ended' ? 'idle' : 'error';
    ttsStatusText.value = result === 'ended' ? '播报完成' : '音频播放失败';
    return result;
  } catch (error) {
    cleanupAudio();
    if (error instanceof Error && error.name === 'NotAllowedError') {
      ttsPlayback.value = 'idle';
      ttsStatusText.value = '音频已就绪';
      return 'blocked';
    }
    ttsPlayback.value = 'error';
    ttsStatusText.value = 'TTS 播放失败';
    return 'error';
  }
}

function waitForAudioInterruption(audio: HTMLAudioElement): Promise<'interrupted'> {
  return new Promise((resolve) => {
    const tick = () => {
      if (activeAudio !== audio) {
        resolve('interrupted');
        return;
      }
      window.setTimeout(tick, 80);
    };
    window.setTimeout(tick, 80);
  });
}

function createPcmStreamPlayback(context: AudioContext): PcmStreamPlayback {
  const analyser = context.createAnalyser();
  analyser.fftSize = 128;
  analyser.connect(context.destination);
  const playback: PcmStreamPlayback = {
    id: crypto.randomUUID(),
    audioContext: context,
    analyser,
    activeSources: new Set<AudioBufferSourceNode>(),
    stopped: false,
    nextStartTime: 0,
    stop() {
      playback.stopped = true;
      playback.activeSources.forEach((source) => {
        try {
          source.stop();
        } catch {
          // Source may already have ended.
        }
      });
      playback.activeSources.clear();
      playback.analyser.disconnect();
      if (playback.audioContext.state !== 'closed') {
        void playback.audioContext.close();
      }
    },
  };
  return playback;
}

function schedulePcmAudioChunk(playback: PcmStreamPlayback, chunk: TtsStreamAudioChunk) {
  if (chunk.format !== 'pcm') {
    throw new Error('当前浏览器流式播放器仅支持 PCM 音频。');
  }
  const bytes = base64ToBytes(chunk.audio_base64);
  const frameCount = Math.floor(bytes.byteLength / 2);
  if (frameCount <= 0) return;

  const sampleRate = chunk.sample_rate || 16_000;
  const dataView = new DataView(bytes.buffer, bytes.byteOffset, frameCount * 2);
  const audioBuffer = playback.audioContext.createBuffer(1, frameCount, sampleRate);
  const channel = audioBuffer.getChannelData(0);
  for (let index = 0; index < frameCount; index += 1) {
    channel[index] = dataView.getInt16(index * 2, true) / 32768;
  }

  const source = playback.audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(playback.analyser);
  source.onended = () => {
    playback.activeSources.delete(source);
  };
  const startAt = Math.max(playback.audioContext.currentTime + 0.04, playback.nextStartTime || 0);
  playback.nextStartTime = startAt + audioBuffer.duration;
  playback.activeSources.add(source);
  source.start(startAt);
}

async function waitForPcmStreamPlaybackEnd(playback: PcmStreamPlayback) {
  while (
    !playback.stopped &&
    activeStreamPlayback === playback &&
    (playback.activeSources.size > 0 || playback.audioContext.currentTime + 0.05 < playback.nextStartTime)
  ) {
    await wait(50);
  }
}

function startStreamVoiceMeter(playback: PcmStreamPlayback) {
  const data = new Uint8Array(playback.analyser.frequencyBinCount);
  const tick = () => {
    playback.analyser.getByteFrequencyData(data);
    const average = data.reduce((sum, value) => sum + value, 0) / data.length;
    voiceEnergy.value = Math.min(1, average / 96);
    if (activeStreamPlayback === playback && !playback.stopped) {
      analyserFrame = requestAnimationFrame(tick);
    }
  };
  tick();
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function applyFvsAction(result: ScreenExecuteResponse) {
  const action = result.authorized_action ?? result.resolved_action ?? null;
  let adapterResult: FvsActionResult = {
    success: false,
    mode: fvsConfig.mode,
    message: result.rejection_reason || result.error?.message || 'Action was blocked by Gateway.',
  };

  if (result.success && action) {
    activeActionId.value = action.id;
    if (fvsConfig.enabled && fvsConfig.mode === 'iframe') {
      markFvsFrameLoading(`正在切换到 ${action.label}。`);
    }
    adapterResult = executeFvsAdapterAction(action, fvsConfig, fvsFrame.value);
    if (!adapterResult.success) {
      pushSystemMessage(`FVS 动作未发送：${adapterResult.message}`);
    }
  }

  fvsEvents.value.unshift({
    id: crypto.randomUUID(),
    actionId: result.action_id,
    label: action?.label ?? result.action_id,
    fvsFunction: action?.fvs_function ?? 'blocked',
    params: action?.params ?? {},
    success: result.success,
    adapterSuccess: adapterResult.success,
    adapterMode: adapterResult.mode,
    adapterMessage: adapterResult.message,
    speakText: result.speak_text,
    requestId: result.request_id,
  });
}

function fillDemo(text: string) {
  inputText.value = text;
}

function fillAsrDemo(text: string) {
  asrMockText.value = text;
}

function demoButtonLabel(question: DemoQuestion, index: number): string {
  const labels: Record<string, string> = {
    leader: '领导',
    knowledge: '知识',
    data: '问数',
    screen_control: '控屏',
    wakeup: '唤醒',
  };
  const category = String(question.category || '');
  return labels[category] ?? `演示${index + 1}`;
}

function handleFvsFrameLoad() {
  clearFvsLoadTimer();
  fvsLoadState.value = 'ready';
  fvsLoadText.value = 'FVS 看板已加载。';
}

function handleFvsFrameError() {
  clearFvsLoadTimer();
  fvsLoadState.value = 'error';
  fvsLoadText.value = 'FVS 看板加载失败，请检查 FVS 地址、同源代理或 iframe 策略。';
  pushSystemMessage(fvsLoadText.value);
}

function markFvsFrameLoading(text: string) {
  clearFvsLoadTimer();
  fvsLoadState.value = 'loading';
  fvsLoadText.value = text;
  fvsLoadTimer = window.setTimeout(() => {
    if (fvsLoadState.value !== 'loading') return;
    fvsLoadState.value = 'error';
    fvsLoadText.value = 'FVS 看板加载超时，请检查 FVS 服务、同源代理或浏览器 iframe 限制。';
    pushSystemMessage(fvsLoadText.value);
  }, FVS_LOAD_TIMEOUT_MS);
}

function clearFvsLoadTimer() {
  if (fvsLoadTimer !== null) {
    clearTimeout(fvsLoadTimer);
    fvsLoadTimer = null;
  }
}

function opsStatusText(status?: OpsStatus | null): string {
  const labels: Record<OpsStatus, string> = {
    ok: '正常',
    warning: '关注',
    error: '异常',
    unknown: '未知',
  };
  return labels[status ?? 'unknown'];
}

function formatOpsLatency(value?: number | null): string {
  if (value === null || value === undefined) return '-';
  if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
  return `${value}ms`;
}

function formatOpsTime(value?: string | null): string {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(parsed);
}

function sessionErrorText(session: OpsSessionSummary): string {
  if (!session.last_error) return '';
  const code = String(session.last_error.code ?? 'ERROR');
  const message = String(session.last_error.message ?? '未记录错误摘要');
  return `${code}: ${message}`;
}

function asConfigRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

function configFieldEntries(value?: Record<string, unknown> | null): Array<[string, ConfigField]> {
  return Object.entries(value ?? {}).map(([key, field]) => [key, toConfigField(field)]);
}

function toConfigField(value: unknown): ConfigField {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const record = value as ConfigField;
    if (
      'value' in record ||
      'source' in record ||
      'status' in record ||
      'configured' in record ||
      'masked' in record
    ) {
      return record;
    }
  }
  return { value, source: 'derived', sensitive: false };
}

function configFieldValue(field: ConfigField): string {
  if (field.sensitive) {
    const configured = field.configured ? 'configured' : 'not configured';
    return field.masked ? `${configured} · ${field.masked}` : configured;
  }
  if (field.status) return String(field.status);
  if (field.value === null || field.value === undefined || field.value === '') return '-';
  if (Array.isArray(field.value)) return field.value.map(String).join(', ');
  if (typeof field.value === 'object') return JSON.stringify(field.value);
  if (typeof field.value === 'boolean') return field.value ? 'true' : 'false';
  return String(field.value);
}

function configSourceLabel(source?: string): string {
  const labels: Record<string, string> = {
    code_default: 'code default',
    root_config: 'root config',
    customer_config: 'customer config',
    env: 'env',
    frontend_build: 'frontend build',
    frontend_runtime: 'frontend runtime',
    derived: 'derived',
    unknown: 'unknown',
  };
  return labels[source || 'unknown'] ?? String(source);
}

function configKeyLabel(key: string): string {
  return key.replace(/_/g, ' ');
}

function implementationStatusText(status: unknown): string {
  const value = String(status);
  if (value === 'implemented') return 'implemented';
  if (value === 'not_implemented') return 'not implemented';
  return value;
}

function pushSystemMessage(text: string) {
  conversation.value.unshift({
    id: crypto.randomUUID(),
    role: 'system',
    text,
  });
}

function getInitialMainView(): MainView {
  return getMainViewFromLocation();
}

function getMainViewFromLocation(): MainView {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  if (path === '/ops/config') return 'config';
  return path === '/ops' ? 'ops' : 'chat';
}

function syncMainViewFromLocation() {
  void setMainView(getMainViewFromLocation(), false);
}

function getRuntimeDemoStableMode(): boolean {
  const params = new URLSearchParams(window.location.search);
  return params.get('demo_mode') === 'stable' || isTruthyEnv(params.get('demoStable'));
}

function isTruthyEnv(value: unknown): boolean {
  const normalized = String(value || '').trim().toLowerCase();
  return ['1', 'true', 'yes', 'on', 'stable'].includes(normalized);
}

function describeMediaError(error: unknown, fallback: string): string {
  if (!window.isSecureContext) {
    return `${fallback}：当前页面不是安全上下文。麦克风通常需要 HTTPS 或 localhost；如果网页框使用局域网 IP 的 http 地址，请改用 HTTPS 或 localhost 验证。`;
  }

  if (isMicrophoneBlockedByPolicy()) {
    return `${fallback}：当前网页框没有获得 microphone 权限。请检查 FVS 网页框是否支持 allow="microphone"，或改为同源/HTTPS 方式嵌入数字人页面。`;
  }

  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
      return `${fallback}：浏览器拒绝了麦克风权限。请检查地址栏站点权限、FVS 网页框权限和浏览器麦克风授权。`;
    }
    if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
      return `${fallback}：没有找到可用麦克风设备。`;
    }
    if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
      return `${fallback}：麦克风可能被其他程序占用。`;
    }
  }

  if (error instanceof Error && error.message) {
    return `${fallback}：${error.message}`;
  }
  return fallback;
}

function isMicrophoneBlockedByPolicy(): boolean {
  const policyDocument = document as Document & {
    permissionsPolicy?: { allowsFeature?: (feature: string) => boolean };
    featurePolicy?: { allowsFeature?: (feature: string) => boolean };
  };
  try {
    const permissionsPolicy = policyDocument.permissionsPolicy;
    if (permissionsPolicy?.allowsFeature) {
      return permissionsPolicy.allowsFeature('microphone') === false;
    }
    const featurePolicy = policyDocument.featurePolicy;
    if (featurePolicy?.allowsFeature) {
      return featurePolicy.allowsFeature('microphone') === false;
    }
  } catch {
    return false;
  }
  return false;
}

function stopMediaStream() {
  recorderProcessor?.disconnect();
  recorderSource?.disconnect();
  if (recorderAudioContext && recorderAudioContext.state !== 'closed') {
    void recorderAudioContext.close();
  }
  recorderProcessor = null;
  recorderSource = null;
  recorderAudioContext = null;
  mediaStream?.getTracks().forEach((track) => track.stop());
  mediaStream = null;
}

function cleanupAudio() {
  if (activeSpeechUtterance) {
    window.speechSynthesis?.cancel();
    activeSpeechUtterance = null;
  }
  if (analyserFrame !== null) {
    cancelAnimationFrame(analyserFrame);
    analyserFrame = null;
  }
  if (activeAudio) {
    activeAudio.pause();
    activeAudio.removeAttribute('src');
    activeAudio.load();
    activeAudio = null;
  }
  if (activeStreamPlayback) {
    activeStreamPlayback.stop();
    activeStreamPlayback = null;
  }
  if (audioContext && audioContext.state !== 'closed') {
    void audioContext.close();
  }
  audioContext = null;
  voiceEnergy.value = 0;
}

function createAudioAnalyser(audio: HTMLAudioElement): AnalyserNode | null {
  const AudioContextCtor = getAudioContextCtor();
  if (!AudioContextCtor) return null;

  audioContext = new AudioContextCtor();
  const source = audioContext.createMediaElementSource(audio);
  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 128;
  source.connect(analyser);
  analyser.connect(audioContext.destination);
  return analyser;
}

function getAudioContextCtor() {
  return (
    window.AudioContext ||
    (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  );
}

function startVoiceMeter(audio: HTMLAudioElement, analyser: AnalyserNode) {
  const data = new Uint8Array(analyser.frequencyBinCount);
  const tick = () => {
    analyser.getByteFrequencyData(data);
    const average = data.reduce((sum, value) => sum + value, 0) / data.length;
    voiceEnergy.value = Math.min(1, average / 96);
    if (activeAudio === audio && !audio.paused && !audio.ended) {
      analyserFrame = requestAnimationFrame(tick);
    }
  };
  tick();
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = String(reader.result || '');
      resolve(result.includes(',') ? result.split(',')[1] : result);
    };
    reader.onerror = () => reject(new Error('音频读取失败'));
    reader.readAsDataURL(blob);
  });
}

function base64ToBytes(value: string): Uint8Array {
  const binary = window.atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function mergeSamples(chunks: Float32Array[]): Float32Array {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const result = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

function encodeWav(samples: Float32Array, sourceSampleRate: number, targetSampleRate: number): Blob {
  const resampled = resampleLinear(samples, sourceSampleRate, targetSampleRate);
  const buffer = new ArrayBuffer(44 + resampled.length * 2);
  const view = new DataView(buffer);

  writeAscii(view, 0, 'RIFF');
  view.setUint32(4, 36 + resampled.length * 2, true);
  writeAscii(view, 8, 'WAVE');
  writeAscii(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, targetSampleRate, true);
  view.setUint32(28, targetSampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, 'data');
  view.setUint32(40, resampled.length * 2, true);

  let offset = 44;
  for (const sample of resampled) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += 2;
  }

  return new Blob([view], { type: 'audio/wav' });
}

function resampleLinear(samples: Float32Array, sourceSampleRate: number, targetSampleRate: number): Float32Array {
  if (sourceSampleRate === targetSampleRate) return samples;
  const ratio = sourceSampleRate / targetSampleRate;
  const targetLength = Math.floor(samples.length / ratio);
  const result = new Float32Array(targetLength);
  for (let index = 0; index < targetLength; index += 1) {
    const sourceIndex = index * ratio;
    const before = Math.floor(sourceIndex);
    const after = Math.min(before + 1, samples.length - 1);
    const weight = sourceIndex - before;
    result[index] = samples[before] * (1 - weight) + samples[after] * weight;
  }
  return result;
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}
</script>

<template>
  <main class="app-shell" :class="{ 'fvs-host-shell': isFvsHost && !isOpsView }">
    <section
      class="workspace"
      :class="{
        'fvs-web-frame': isFvsWebFrame && !isOpsView,
        'fvs-host': isFvsHost && !isOpsView,
        'ops-mode': isOpsView,
      }"
    >
      <div class="stage">
        <div v-if="!isFvsHost || isOpsView" class="stage-topline">
          <div>
            <p class="eyebrow">{{ stageEyebrow }}</p>
            <h1>{{ stageTitle }}</h1>
          </div>
          <div class="stage-actions">
            <div class="view-switch" aria-label="Main view">
              <button type="button" :class="{ active: activeView === 'chat' }" @click="setMainView('chat')">
                演示
              </button>
              <button type="button" :class="{ active: activeView === 'ops' }" @click="setMainView('ops')">
                运维
              </button>
              <button type="button" :class="{ active: activeView === 'config' }" @click="setMainView('config')">
                配置
              </button>
            </div>
            <span v-if="isDemoStableMode" class="status-pill demo">演示稳态</span>
            <span class="status-pill" :class="apiStatus">{{ statusText }}</span>
          </div>
        </div>

        <section v-if="isOpsMonitorView" class="ops-dashboard" aria-label="运维监控和日志看板">
          <div class="ops-toolbar">
            <div>
              <span class="ops-kicker">Ops Monitor</span>
              <strong>运维监控和日志看板</strong>
            </div>
            <div class="ops-toolbar-actions">
              <span class="ops-status-chip" :class="opsOverallStatus">{{ opsStatusText(opsOverallStatus) }}</span>
              <button type="button" :disabled="opsLoading" @click="loadOpsDashboard">
                {{ opsLoading ? '刷新中' : '刷新' }}
              </button>
              <button type="button" :disabled="opsExporting" @click="exportOpsLogs">
                {{ opsExporting ? '导出中' : '导出日志' }}
              </button>
            </div>
          </div>

          <div v-if="opsErrorText" class="ops-alert">{{ opsErrorText }}</div>

          <div class="ops-summary">
            <div>
              <span>客户</span>
              <strong>{{ opsCustomerLabel }}</strong>
            </div>
            <div>
              <span>会话</span>
              <strong>{{ opsMetrics?.total_sessions ?? 0 }}</strong>
            </div>
            <div>
              <span>事件</span>
              <strong>{{ opsMetrics?.total_events ?? 0 }}</strong>
            </div>
            <div>
              <span>错误</span>
              <strong>{{ opsMetrics?.error_events ?? 0 }}</strong>
            </div>
            <div>
              <span>平均耗时</span>
              <strong>{{ formatOpsLatency(opsMetrics?.avg_latency_ms) }}</strong>
            </div>
            <div>
              <span>更新时间</span>
              <strong>{{ opsLastUpdated || formatOpsTime(opsHealth?.time) }}</strong>
            </div>
          </div>

          <div class="ops-section">
            <div class="ops-section-title">
              <span>依赖状态</span>
              <small>Dora / RAGFlow / FVS / ASR / TTS</small>
            </div>
            <div class="dependency-grid">
              <article
                v-for="dependency in opsDependencies?.dependencies ?? []"
                :key="dependency.name"
                class="dependency-item"
              >
                <div>
                  <strong>{{ dependency.label }}</strong>
                  <span class="ops-status-chip" :class="dependency.status">
                    {{ opsStatusText(dependency.status) }}
                  </span>
                </div>
                <p>{{ dependency.message }}</p>
                <small>{{ formatOpsLatency(dependency.latency_ms) }} · {{ formatOpsTime(dependency.checked_at) }}</small>
              </article>
              <div v-if="!opsDependencies?.dependencies.length" class="ops-empty">暂无依赖状态</div>
            </div>
          </div>

          <div class="ops-grid">
            <section class="ops-section">
              <div class="ops-section-title">
                <span>最近会话</span>
                <small>{{ opsSessions.length }} sessions</small>
              </div>
              <div class="ops-list">
                <article v-for="session in opsSessions" :key="session.session_id" class="ops-row">
                  <div>
                    <strong>{{ session.session_id }}</strong>
                    <span>{{ session.last_user_text || '无输入摘要' }}</span>
                    <small v-if="session.last_error">{{ sessionErrorText(session) }}</small>
                  </div>
                  <div>
                    <code>{{ session.last_intent_type }}</code>
                    <small>{{ session.turns }} 条 · {{ formatOpsLatency(session.last_latency_ms) }}</small>
                    <small>{{ formatOpsTime(session.last_message_at) }}</small>
                  </div>
                </article>
                <div v-if="opsSessions.length === 0" class="ops-empty">暂无会话日志</div>
              </div>
            </section>

            <section class="ops-section">
              <div class="ops-section-title">
                <span>错误列表</span>
                <small>{{ opsErrors.length }} errors</small>
              </div>
              <div class="ops-list">
                <article v-for="error in opsErrors" :key="error.id" class="ops-row error">
                  <div>
                    <strong>{{ error.code }}</strong>
                    <span>{{ error.message }}</span>
                    <small>{{ error.user_text || error.session_id }}</small>
                  </div>
                  <div>
                    <code>{{ error.intent_type }}</code>
                    <small>{{ formatOpsLatency(error.latency_total_ms) }}</small>
                    <small>{{ formatOpsTime(error.created_at) }}</small>
                  </div>
                </article>
                <div v-if="opsErrors.length === 0" class="ops-empty">暂无错误记录</div>
              </div>
            </section>
          </div>

          <div class="ops-section">
            <div class="ops-section-title">
              <span>耗时指标</span>
              <small>P50 {{ formatOpsLatency(opsMetrics?.p50_latency_ms) }} / P95 {{ formatOpsLatency(opsMetrics?.p95_latency_ms) }}</small>
            </div>
            <div class="latency-grid">
              <article v-for="bucket in opsMetrics?.by_intent ?? []" :key="bucket.name" class="latency-item">
                <div>
                  <strong>{{ bucket.name }}</strong>
                  <small>{{ bucket.count }} 条</small>
                </div>
                <span>{{ formatOpsLatency(bucket.avg_latency_ms) }}</span>
                <small>max {{ formatOpsLatency(bucket.max_latency_ms) }} · errors {{ bucket.error_count }}</small>
              </article>
              <div v-if="!opsMetrics?.by_intent.length" class="ops-empty">暂无耗时数据</div>
            </div>
          </div>
        </section>

        <section v-else-if="isConfigView" class="config-dashboard" aria-label="只读配置快照">
          <div class="ops-toolbar config-toolbar">
            <div>
              <span class="ops-kicker">Config Snapshot</span>
              <strong>只读配置快照</strong>
            </div>
            <div class="ops-toolbar-actions">
              <span class="ops-status-chip ok">read only</span>
              <span class="ops-status-chip unknown">schema v{{ configSchema?.version || '-' }}</span>
            </div>
          </div>

          <div v-if="configErrorText" class="ops-alert">{{ configErrorText }}</div>
          <div v-if="configLoading" class="ops-empty">配置快照读取中</div>

          <template v-if="configEffective">
            <div class="ops-summary config-summary">
              <div>
                <span>项目</span>
                <strong>{{ configFieldValue(configEffective.project.project_name) }}</strong>
              </div>
              <div>
                <span>客户</span>
                <strong>{{ configFieldValue(configEffective.customer.customer_name) }}</strong>
              </div>
              <div>
                <span>场景</span>
                <strong>{{ configFieldValue(configEffective.customer.scenario_name) }}</strong>
              </div>
              <div>
                <span>助手</span>
                <strong>{{ configFieldValue(configEffective.customer.assistant_name) }}</strong>
              </div>
              <div>
                <span>版本</span>
                <strong>{{ configEffective.version }}</strong>
              </div>
              <div>
                <span>生成时间</span>
                <strong>{{ formatOpsTime(configEffective.generated_at) }}</strong>
              </div>
            </div>

            <div class="config-grid">
              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>项目与客户</span>
                  <small>project / customer / scenario / assistant</small>
                </div>
                <div class="config-list">
                  <article v-for="[key, field] in configProjectFields" :key="`project-${key}`" class="config-row">
                    <span>{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                    <small v-if="field.notes">{{ field.notes }}</small>
                  </article>
                  <article v-for="[key, field] in configCustomerFields" :key="`customer-${key}`" class="config-row">
                    <span>{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                    <small v-if="field.notes">{{ field.notes }}</small>
                  </article>
                </div>
              </section>

              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>看板配置</span>
                  <small>backend effective / frontend runtime</small>
                </div>
                <div class="config-list">
                  <article
                    v-for="[key, field] in configDashboardBackendFields"
                    :key="`dashboard-backend-${key}`"
                    class="config-row"
                  >
                    <span>backend.{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                    <small v-if="field.notes">{{ field.notes }}</small>
                  </article>
                  <article
                    v-for="[key, field] in configDashboardContractFields"
                    :key="`dashboard-contract-${key}`"
                    class="config-row muted"
                  >
                    <span>contract.{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                    <small v-if="field.notes">{{ field.notes }}</small>
                  </article>
                  <article
                    v-for="[key, field] in frontendRuntimeFvsFields"
                    :key="`dashboard-runtime-${key}`"
                    class="config-row"
                  >
                    <span>runtime.{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                  </article>
                </div>
              </section>
            </div>

            <div class="config-grid">
              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>问数 Provider</span>
                  <small>Database Provider 未实现</small>
                </div>
                <div class="config-list">
                  <article v-for="[key, field] in configAskMetricsFields" :key="`ask-${key}`" class="config-row">
                    <span>{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                    <small v-if="field.notes">{{ field.notes }}</small>
                  </article>
                </div>
              </section>

              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>知识库 Provider</span>
                  <small>KnowledgeDirectAdapter 未实现</small>
                </div>
                <div class="config-list">
                  <article v-for="[key, field] in configKnowledgeFields" :key="`knowledge-${key}`" class="config-row">
                    <span>{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                    <small v-if="field.notes">{{ field.notes }}</small>
                  </article>
                </div>
              </section>
            </div>

            <div class="config-grid">
              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>控屏 Provider</span>
                  <small>可写 action 配置未实现</small>
                </div>
                <div class="config-list">
                  <article v-for="[key, field] in configScreenControlFields" :key="`screen-${key}`" class="config-row">
                    <span>{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                    <small v-if="field.notes">{{ field.notes }}</small>
                  </article>
                </div>
              </section>

              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>Dora 与语音</span>
                  <small>Mock 开关保留</small>
                </div>
                <div class="config-list">
                  <article v-for="[key, field] in configDoraFields" :key="`dora-${key}`" class="config-row">
                    <span>dora.{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                    <small v-if="field.notes">{{ field.notes }}</small>
                  </article>
                  <article v-for="[key, field] in configVoiceFields" :key="`voice-${key}`" class="config-row">
                    <span>voice.{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                    <small v-if="field.notes">{{ field.notes }}</small>
                  </article>
                </div>
              </section>
            </div>

            <div class="config-grid">
              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>Mock 开关</span>
                  <small>Dora / ASR / TTS / FVS</small>
                </div>
                <div class="config-list">
                  <article v-for="[key, field] in configMockFields" :key="`mock-${key}`" class="config-row">
                    <span>{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                  </article>
                </div>
              </section>

              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>Prompt Profile</span>
                  <small>本轮无可写 Prompt</small>
                </div>
                <div class="config-list">
                  <article v-for="[key, raw] in configPromptEntries" :key="`prompt-${key}`" class="config-row">
                    <span>{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(toConfigField(asConfigRecord(raw).profile)) }}</strong>
                    <code>{{ configSourceLabel(toConfigField(asConfigRecord(raw).profile).source) }}</code>
                    <small v-if="toConfigField(asConfigRecord(raw).profile).notes">
                      {{ toConfigField(asConfigRecord(raw).profile).notes }}
                    </small>
                  </article>
                </div>
              </section>
            </div>

            <div class="config-grid">
              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>敏感字段</span>
                  <small>只展示 configured / source / masked</small>
                </div>
                <div class="config-list">
                  <article v-for="[key, field] in configSensitiveFields" :key="`sensitive-${key}`" class="config-row">
                    <span>{{ configKeyLabel(key) }}</span>
                    <strong>{{ configFieldValue(field) }}</strong>
                    <code>{{ configSourceLabel(field.source) }}</code>
                  </article>
                </div>
              </section>

              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>实现状态</span>
                  <small>阶段 1 边界</small>
                </div>
                <div class="status-grid">
                  <span
                    v-for="[key, status] in configImplementationEntries"
                    :key="`status-${key}`"
                    class="status-pill"
                    :class="status === 'implemented' ? 'ready' : 'error'"
                  >
                    {{ configKeyLabel(key) }}: {{ implementationStatusText(status) }}
                  </span>
                </div>
              </section>
            </div>

            <div class="config-grid">
              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>来源限制</span>
                  <small>provenance notes</small>
                </div>
                <div class="config-note-list">
                  <p v-for="note in configProvenanceNotes" :key="note">{{ note }}</p>
                </div>
              </section>

              <section class="ops-section config-section">
                <div class="ops-section-title">
                  <span>未开放接口</span>
                  <small>schema disabled endpoints</small>
                </div>
                <div class="status-grid">
                  <code v-for="endpoint in configDisabledEndpoints" :key="endpoint">{{ endpoint }}</code>
                </div>
              </section>
            </div>
          </template>
        </section>

        <div
          v-else-if="!isFvsWebFrame"
          class="screen-frame"
          :class="{ 'real-fvs': fvsConfig.enabled && fvsConfig.mode === 'iframe' }"
        >
          <div v-if="!isFvsHost" class="screen-header">
            <span>{{ fvsModeLabel }}</span>
            <strong>{{ activeAction?.label ?? '未选择' }}</strong>
          </div>
          <template v-if="fvsConfig.enabled && fvsConfig.mode === 'iframe'">
            <iframe
              ref="fvsFrame"
              class="fvs-iframe"
              :src="fvsConfig.url"
              title="FVS Screen"
              allow="fullscreen"
              referrerpolicy="no-referrer-when-downgrade"
              @load="handleFvsFrameLoad"
              @error="handleFvsFrameError"
            ></iframe>
            <div v-if="fvsLoadState === 'error'" class="fvs-fallback">
              <strong>FVS 看板暂不可用</strong>
              <span>{{ fvsLoadText }}</span>
            </div>
          </template>
          <template v-else>
            <div class="screen-tabs">
              <button
                v-for="action in actions"
                :key="action.id"
                class="screen-tab"
                :class="{ active: action.id === activeActionId }"
                type="button"
                @click="activeActionId = action.id"
              >
                {{ action.label }}
              </button>
            </div>
            <div class="screen-body">
              <div class="metric-strip">
                <div>
                  <span>接入看板</span>
                  <strong>4</strong>
                </div>
                <div>
                  <span>示例指标</span>
                  <strong>3</strong>
                </div>
                <div>
                  <span>演示动作</span>
                  <strong>4</strong>
                </div>
              </div>
              <div class="screen-copy">
                <p>{{ activeAction?.description ?? '等待 Mock FVS 动作' }}</p>
                <small>{{ activeAction?.fvs_function ?? '-' }}</small>
              </div>
            </div>
          </template>
        </div>

        <div v-if="!isFvsHost && !isOpsView" class="voice-monitor" :class="ttsPlayback" :style="voiceStyle">
          <div>
            <span>语音播报</span>
            <strong>{{ ttsStatusText }}</strong>
          </div>
          <div class="voice-bars" aria-hidden="true">
            <i v-for="index in 7" :key="index"></i>
          </div>
        </div>

        <div v-if="!isFvsHost && !isOpsView" class="fvs-log">
          <span>最近动作</span>
          <strong>{{ latestFvsEvent?.label ?? '暂无执行记录' }}</strong>
          <code>{{ fvsLogCode }}</code>
        </div>

        <div v-if="!isFvsHost && !isOpsView" class="screen-action-row" aria-label="FVS page actions">
          <button
            v-for="action in actions"
            :key="action.id"
            type="button"
            :class="{ active: action.id === activeActionId }"
            :disabled="isSending"
            @click="executeWhitelistedScreenAction(action.id)"
          >
            {{ action.label }}
          </button>
        </div>
      </div>

      <div v-if="!isOpsView" class="conversation-panel" :class="{ compact: !isVoicePanelExpanded, expanded: isVoicePanelExpanded }">
        <button
          v-if="!isVoicePanelExpanded"
          class="voice-orb-button"
          :class="{ active: listenerEnabled }"
          :style="voiceStyle"
          type="button"
          :aria-label="listenerEnabled ? '关闭后台监听' : '开启后台监听'"
          @click="toggleVoiceDock"
        >
          <span class="voice-orb-rings" aria-hidden="true"></span>
          <span class="mic-symbol" aria-hidden="true"><i></i></span>
        </button>

        <template v-else-if="isFvsHost">
          <div class="fvs-comment-stream" aria-live="polite">
            <article v-for="item in fvsConversationItems" :key="item.id" class="fvs-comment" :class="item.role">
              <span>{{ item.role === 'user' ? '识别' : '数字人' }}</span>
              <p>{{ item.text }}</p>
            </article>
          </div>
        </template>

        <template v-else>
        <form v-if="!isFvsHost" class="chat-form" @submit.prevent="submitQuestion()">
          <label for="question">文本输入</label>
          <div class="input-row">
            <input
              id="question"
              v-model="inputText"
              autocomplete="off"
              placeholder="请输入演示问题"
              :disabled="isSending"
            />
            <button type="submit" :disabled="isSending || !inputText.trim()">
              {{ isSending ? '发送中' : '发送' }}
            </button>
          </div>
        </form>

        <div class="voice-panel">
          <div class="voice-header">
            <span>语音输入</span>
            <strong>{{ asrText || recordedAudioLabel }}</strong>
          </div>
          <div class="listener-card" :class="listeningState" :style="voiceStyle">
            <label class="listener-toggle">
              <input type="checkbox" :checked="listenerEnabled" @change="onListenerToggle" />
              <span>后台监听</span>
            </label>
            <div class="listener-status">
              <span>{{ listeningStateLabel }}</span>
              <strong>{{ listeningDetail }}</strong>
            </div>
            <div class="listener-meter" aria-hidden="true">
              <i v-for="index in 5" :key="index"></i>
            </div>
            <div class="listener-meta">
              <span>{{ wakeCheckText || wakeWordsLabel }}</span>
              <code>{{ commandText || (listeningState === 'followup_listening' ? followupLabel : `miss:${wakeMissCount}`) }}</code>
            </div>
          </div>
          <input
            v-if="!isFvsHost"
            v-model="asrMockText"
            autocomplete="off"
            placeholder="Mock ASR 识别文本"
            :disabled="isAsrProcessing || isSending || listenerEnabled"
          />
          <div v-if="!isFvsHost" class="voice-actions">
            <button type="button" :disabled="!canUseManualVoice" @click="startRecording">
              {{ isRecording ? '录音中' : '录音' }}
            </button>
            <button type="button" :disabled="!isRecording || listenerEnabled" @click="stopRecording">停止</button>
            <button type="button" :disabled="isAsrProcessing || isSending || listenerEnabled" @click="transcribeAndSend">
              {{ isAsrProcessing ? '识别中' : '识别并发送' }}
            </button>
          </div>
        </div>

        <div v-if="!isFvsHost" class="demo-row" aria-label="Demo questions">
          <button
            v-for="(question, index) in demoQuestions"
            :key="question.id || `${question.text}-${index}`"
            type="button"
            @click="fillDemo(question.text || '')"
          >
            {{ demoButtonLabel(question, index) }}
          </button>
          <button type="button" @click="fillAsrDemo('小智小智，请切换到成品库存页面')">ASR 唤醒</button>
        </div>

        <div class="messages" aria-live="polite">
          <article v-for="item in conversation" :key="item.id" class="message" :class="item.role">
            <div class="message-topline">
              <span class="message-role">
                {{ item.role === 'user' ? '用户' : item.role === 'assistant' ? '数字人' : '系统' }}
              </span>
              <button
                v-if="item.role === 'assistant'"
                class="message-tts"
                type="button"
                :disabled="item.tts?.status !== 'ready' || ttsPlayback === 'loading'"
                @click="playConversationTts(item)"
              >
                {{ item.tts?.status === 'loading' ? '合成中' : item.tts?.status === 'error' ? '无音频' : '播报' }}
              </button>
            </div>
            <p>{{ item.text }}</p>
            <audio
              v-if="item.tts?.audioUrl"
              class="message-audio"
              controls
              preload="none"
              :src="toApiUrl(item.tts.audioUrl)"
              @play="ttsStatusText = `${item.tts?.label ?? 'TTS'} 播报中`"
              @ended="ttsStatusText = '播报完成'"
            ></audio>

            <div v-if="item.response?.display" class="display-box">
              <strong>{{ item.response.title }}</strong>
              <span>{{ item.response.display.summary }}</span>
              <ul v-if="item.response.display.bullets?.length">
                <li v-for="bullet in item.response.display.bullets" :key="bullet">{{ bullet }}</li>
              </ul>
            </div>

            <div v-if="item.response?.action" class="action-box">
              <span>action_id</span>
              <code>{{ item.response.action.id }}</code>
              <small>{{ item.response.action.target }}</small>
            </div>

            <small v-if="item.response?.reason" class="reason">{{ item.response.reason }}</small>
          </article>

          <div v-if="conversation.length === 0" class="empty-state">
            <strong>{{ isFvsHost ? '等待语音' : '等待输入' }}</strong>
            <span>
              {{
                isFvsHost
                  ? '唤醒后的指令和数字人回复会显示在这里。'
                  : '文本或 Mock ASR 会进入同一条 `/api/chat` 链路。'
              }}
            </span>
          </div>
        </div>
        </template>
      </div>
    </section>
  </main>
</template>
