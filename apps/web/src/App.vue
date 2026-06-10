<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  executeScreenAction,
  fetchWakeConfig,
  fetchScreenActions,
  sendChat,
  streamChat,
  synthesizeSpeech,
  toApiUrl,
  transcribeAudio,
} from './api';
import { executeFvsAction as executeFvsAdapterAction, getFvsConfig } from './fvsAdapter';
import type {
  ChatResponse,
  ChatStreamTtsReady,
  ScreenAction,
  ScreenExecuteResponse,
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
type TtsPlaybackState = 'idle' | 'loading' | 'playing' | 'error';
type ListeningState =
  | 'idle'
  | 'monitoring'
  | 'wake_checking'
  | 'recording'
  | 'followup_listening'
  | 'thinking'
  | 'speaking'
  | 'cooldown';
type VadSegmentKind = 'wake' | 'command';

interface SubmitQuestionOptions {
  awaitTts?: boolean;
}

interface PlaybackOptions {
  monitorPlayback?: boolean;
}

interface MonitorCommandOptions {
  isFollowup?: boolean;
}

type AudioPlaybackResult = 'ended' | 'blocked' | 'error' | 'interrupted';

const ACKNOWLEDGEMENT_TEXT = '收到，正在为您查找信息。';

const DEFAULT_WAKE_CONFIG: WakeConfigResponse = {
  version: '0.1.0',
  mode: 'semantic',
  wake_words: ['小天小天', '中天小天', '你好小天'],
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
  },
};

const sessionId = `demo-session-${Date.now()}`;
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
let monitorSampleRate = 16000;
let monitorSpeechActive = false;
let monitorSpeechStartedAt = 0;
let monitorLastSpeechAt = 0;
let monitorFinalizing = false;
let monitorCommandTimer: number | null = null;
let monitorCooldownTimer: number | null = null;
let activeSegmentPlaybackItemId: string | null = null;
let acknowledgementAudioUrl: string | null = null;
let acknowledgementAudioPromise: Promise<string | null> | null = null;
let activeSpeechUtterance: SpeechSynthesisUtterance | null = null;

const activeAction = computed(() => {
  return actions.value.find((action) => action.id === activeActionId.value) ?? actions.value[0];
});

const latestFvsEvent = computed(() => fvsEvents.value[0]);
const isFvsHost = computed(() => fvsConfig.enabled && fvsConfig.mode === 'iframe');
const isFvsWebFrame = computed(() => fvsConfig.enabled && fvsConfig.mode === 'parent');
const isVoicePanelExpanded = computed(() => {
  if (!isFvsHost.value) return true;
  return (
    isSending.value ||
    isAsrProcessing.value ||
    ttsPlayback.value === 'loading' ||
    ttsPlayback.value === 'playing' ||
    ['wake_checking', 'recording', 'followup_listening', 'thinking', 'speaking'].includes(listeningState.value)
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

const followupLabel = computed(() => {
  const maxTurns = wakeConfig.value.settings.max_followup_turns;
  if (!wakeConfig.value.settings.followup_enabled || maxTurns <= 0) return '连续对话关闭';
  return `连续 ${followupTurnsUsed.value}/${maxTurns}`;
});

const canUseManualVoice = computed(
  () => !listenerEnabled.value && !isRecording.value && !isAsrProcessing.value && !isSending.value,
);

onMounted(async () => {
  void getAcknowledgementAudioUrl();

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
});

onBeforeUnmount(() => {
  stopBackgroundListening();
  stopRecording();
  stopMediaStream();
  cleanupAudio();
});

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
    try {
      await streamChat(requestPayload, {
        onDelta(delta) {
          if (!assistantItem.response && delta.trim()) {
            assistantItem.text = assistantItem.text === '正在思考...' ? delta : `${assistantItem.text}${delta}`;
          }
        },
        onTtsReady(segment) {
          addTtsSegment(assistantItem, segment);
          if (options.awaitTts) {
            void playConversationTts(assistantItem, { monitorPlayback: true });
          }
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
      });
      await applyFvsAction(executeResponse);
    }

    if (assistantItem.tts?.segments?.length) {
      assistantItem.tts.streamEnded = true;
      assistantItem.tts.status = 'ready';
      assistantItem.tts.label = '分段 TTS';
      if (options.awaitTts) {
        await playConversationTts(assistantItem, { monitorPlayback: true });
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
  }
}

function collectVadFrame(frame: Float32Array, rms: number, kind: VadSegmentKind) {
  const now = performance.now();
  const settings = wakeConfig.value.settings;
  const hasSpeech = rms >= settings.vad_threshold;
  if (!monitorSpeechActive && hasSpeech) {
    if (kind === 'command' && monitorCommandTimer !== null) {
      clearTimeout(monitorCommandTimer);
      monitorCommandTimer = null;
    }
    monitorSpeechActive = true;
    monitorSpeechStartedAt = now;
    monitorLastSpeechAt = now;
    monitorSamples = [];
  }

  if (!monitorSpeechActive) return;

  monitorSamples.push(frame);
  if (hasSpeech) {
    monitorLastSpeechAt = now;
  }

  const elapsedMs = now - monitorSpeechStartedAt;
  const silenceMs = now - monitorLastSpeechAt;
  const maxAudioMs = kind === 'wake' ? settings.max_audio_ms : settings.command_timeout_ms;
  if ((elapsedMs >= settings.min_audio_ms && silenceMs >= settings.silence_ms) || elapsedMs >= maxAudioMs) {
    void finalizeVadSegment(kind);
  }
}

async function finalizeVadSegment(kind: VadSegmentKind) {
  if (monitorFinalizing) return;
  monitorFinalizing = true;
  const samples = mergeSamples(monitorSamples);
  const durationMs = (samples.length / Math.max(1, monitorSampleRate)) * 1000;
  resetVadSegment();

  try {
    if (durationMs < wakeConfig.value.settings.min_audio_ms * 0.6 || samples.length === 0) {
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
    } else {
      await processCommandSegment(audioBlob);
    }
  } finally {
    monitorFinalizing = false;
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
  playAcknowledgementPrompt();
  const assistantItem = await submitQuestion(cleanedText, 'voice', { awaitTts: true });
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

function findWakeWord(text: string): string | null {
  const normalizedText = normalizeWakeText(text);
  for (const word of wakeConfig.value.wake_words) {
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
  const pieces = Array.from(wakeWord).map((char) => escapeRegExp(char));
  return new RegExp(`${pieces.join('[\\s,，。.!！?？、]*')}[\\s,，。.!！?？、]*`, 'i');
}

function normalizeWakeText(text: string): string {
  return text.toLowerCase().replace(/[\s,，。.!！?？、]/g, '');
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
  monitorSpeechActive = false;
  monitorSpeechStartedAt = 0;
  monitorLastSpeechAt = 0;
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

function playAcknowledgementPrompt() {
  setListeningState('thinking', '已收到，正在查找信息。');
  ttsStatusText.value = ACKNOWLEDGEMENT_TEXT;

  if (acknowledgementAudioUrl) {
    void playAudioUrl(acknowledgementAudioUrl, '等待提示');
    return;
  }

  if (speakLocalAcknowledgement(ACKNOWLEDGEMENT_TEXT)) {
    void getAcknowledgementAudioUrl();
    return;
  }

  void getAcknowledgementAudioUrl().then((audioUrl) => {
    if (audioUrl && isSending.value && !activeAudio && !activeSpeechUtterance) {
      void playAudioUrl(audioUrl, '等待提示');
    }
  });
}

function speakLocalAcknowledgement(text: string): boolean {
  if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
    return false;
  }

  cleanupAudio();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'zh-CN';
  activeSpeechUtterance = utterance;
  ttsPlayback.value = 'playing';
  ttsStatusText.value = '等待提示播报中';
  voiceEnergy.value = 0.42;
  utterance.onend = () => {
    if (activeSpeechUtterance !== utterance) return;
    activeSpeechUtterance = null;
    voiceEnergy.value = 0;
    ttsPlayback.value = 'idle';
    ttsStatusText.value = '等待提示播报完成';
  };
  utterance.onerror = () => {
    if (activeSpeechUtterance !== utterance) return;
    activeSpeechUtterance = null;
    voiceEnergy.value = 0;
    ttsPlayback.value = 'idle';
  };
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
  return true;
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
  ttsPlayback.value = ttsPlayback.value === 'playing' ? 'playing' : 'idle';
  ttsStatusText.value = `TTS 第 ${segment.index + 1} 段已就绪`;
}

async function playConversationTts(item: ConversationItem, options: PlaybackOptions = {}) {
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
      setListeningState('speaking', '正在播报回复。');
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
      setListeningState('speaking', '正在播报回复。');
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

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function applyFvsAction(result: ScreenExecuteResponse) {
  const action = actions.value.find((item) => item.id === result.action_id);
  let adapterResult: FvsActionResult = {
    success: false,
    mode: fvsConfig.mode,
    message: result.error?.message || 'Action was blocked by Gateway.',
  };

  if (result.success && action) {
    activeActionId.value = action.id;
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

function pushSystemMessage(text: string) {
  conversation.value.unshift({
    id: crypto.randomUUID(),
    role: 'system',
    text,
  });
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
  <main class="app-shell" :class="{ 'fvs-host-shell': isFvsHost }">
    <section class="workspace" :class="{ 'fvs-web-frame': isFvsWebFrame, 'fvs-host': isFvsHost }">
      <div class="stage">
        <div v-if="!isFvsHost" class="stage-topline">
          <div>
            <p class="eyebrow">ZT Party Building POC</p>
            <h1>党建大屏数字人语音闭环</h1>
          </div>
          <span class="status-pill" :class="apiStatus">{{ statusText }}</span>
        </div>

        <div
          v-if="!isFvsWebFrame"
          class="screen-frame"
          :class="{ 'real-fvs': fvsConfig.enabled && fvsConfig.mode === 'iframe' }"
        >
          <div v-if="!isFvsHost" class="screen-header">
            <span>{{ fvsModeLabel }}</span>
            <strong>{{ activeAction?.label ?? '未选择' }}</strong>
          </div>
          <iframe
            v-if="fvsConfig.enabled && fvsConfig.mode === 'iframe'"
            ref="fvsFrame"
            class="fvs-iframe"
            :src="fvsConfig.url"
            title="FVS Screen"
            allow="fullscreen"
            referrerpolicy="no-referrer-when-downgrade"
          ></iframe>
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
                  <span>党员总数</span>
                  <strong>128</strong>
                </div>
                <div>
                  <span>学习完成率</span>
                  <strong>87.5%</strong>
                </div>
                <div>
                  <span>本月活动</span>
                  <strong>16</strong>
                </div>
              </div>
              <div class="screen-copy">
                <p>{{ activeAction?.description ?? '等待 Mock FVS 动作' }}</p>
                <small>{{ activeAction?.fvs_function ?? '-' }}</small>
              </div>
            </div>
          </template>
        </div>

        <div v-if="!isFvsHost" class="voice-monitor" :class="ttsPlayback" :style="voiceStyle">
          <div>
            <span>语音播报</span>
            <strong>{{ ttsStatusText }}</strong>
          </div>
          <div class="voice-bars" aria-hidden="true">
            <i v-for="index in 7" :key="index"></i>
          </div>
        </div>

        <div v-if="!isFvsHost" class="fvs-log">
          <span>最近动作</span>
          <strong>{{ latestFvsEvent?.label ?? '暂无执行记录' }}</strong>
          <code>{{ fvsLogCode }}</code>
        </div>

        <div v-if="!isFvsHost" class="screen-action-row" aria-label="FVS page actions">
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

      <div class="conversation-panel" :class="{ compact: !isVoicePanelExpanded, expanded: isVoicePanelExpanded }">
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
          <button type="button" @click="fillDemo('返回总览')">输入总览</button>
          <button type="button" @click="fillDemo('请切换到成品库存页面')">输入库存</button>
          <button type="button" @click="fillDemo('请切换到生产管理页面')">输入生产</button>
          <button type="button" @click="fillAsrDemo('请切换到设备分析页面')">ASR 设备</button>
          <button type="button" @click="fillAsrDemo('小天小天，请切换到成品库存页面')">ASR 唤醒</button>
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
