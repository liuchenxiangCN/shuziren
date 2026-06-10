# ASR / TTS 集成说明

## 目标

接入国产 ASR 和 TTS, 完成语音输入和语音播报。

## 默认策略

- ASR: 阿里云百炼 Fun-ASR Realtime。
- TTS: 阿里云百炼 CosyVoice Realtime。
- 备选: 科大讯飞、火山引擎等国产供应商。

## 配置项

```env
ASR_PROVIDER=aliyun
ASR_API_KEY=replace_me
ASR_MODEL=fun-asr-realtime
ASR_REGION=cn-beijing
ASR_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/inference
ASR_AUDIO_FORMAT=wav
ASR_SAMPLE_RATE=16000
ASR_TIMEOUT_SECONDS=30

TTS_PROVIDER=aliyun
TTS_API_KEY=replace_me
TTS_MODEL=cosyvoice-v3-flash
TTS_VOICE=longanyang
TTS_AUDIO_FORMAT=mp3
TTS_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/inference
TTS_SAMPLE_RATE=22050
TTS_TIMEOUT_SECONDS=30
TTS_CACHE_DIR=/app/data/tts-cache

ENABLE_MOCK_ASR=true
ENABLE_MOCK_TTS=true
```

说明: `https://dashscope.aliyuncs.com/compatible-mode/v1` 是 OpenAI-compatible 模型接口, 不用于本项目 ASR / TTS 语音链路。语音链路当前使用阿里云百炼 WebSocket: `wss://dashscope.aliyuncs.com/api-ws/v1/inference`。

## V0.3 / V0.4 / V0.5 当前实现

后端:

- `apps/api/app/services/asr_provider.py` 定义 `AsrProvider`、`MockAsrProvider` 和未配置真实 Provider 的安全兜底。
- `apps/api/app/services/tts_provider.py` 定义 `TtsProvider`、`MockTtsProvider` 和未配置真实 Provider 的安全兜底。
- `apps/api/app/services/wake_words.py` 读取 `config/wake-words.yaml`, 并通过 `GET /api/wake/config` 提供给前端。
- `POST /api/asr/transcribe` 接收 `mock_text` 和可选 `audio_base64`, 返回最终识别文本。
- `POST /api/tts` 使用 Mock TTS 生成完整 `wav` 文件, 返回 `/api/tts/audio/{audio_id}`。
- `GET /api/tts/audio/{audio_id}` 只允许读取后端生成的安全音频 ID。
- `ENABLE_MOCK_ASR=false` 时, 后端通过 Fun-ASR WebSocket 调用真实 ASR。
- `ENABLE_MOCK_TTS=false` 时, 后端通过 CosyVoice WebSocket 调用真实 TTS, 并把返回的二进制音频缓存为本地文件。
- V0.5 新增 `POST /api/chat/stream`, 在 Dora + RAGFlow MCP 知识库问答路径中边接收 Dora SSE, 边从最终回答 JSON 的 `speak_text` 提取增量文本。
- V0.5 流式路径会把 `speak_text` 拆成短段并发调用现有 TTS Provider, 通过 `tts_ready` SSE 事件返回分段音频 URL。
- 如果 Dora 某次只返回最终 answer 而没有稳定增量, 后端仍会把最终 `speak_text` 分段合成, 避免退回整段 TTS。

前端:

- 支持浏览器录音, 将短音频编码为 16k 单声道 WAV base64 后提交给 `/api/asr/transcribe`。
- 支持直接提交 Mock ASR 文本。
- ASR 文本自动进入现有 `/api/chat` 流程, `context.mode=voice`。
- 数字人回答后后台准备 TTS 音频, 消息中展示“播报”按钮和原生音频控件。
- 优先调用 `/api/chat/stream`; 收到分段 `tts_ready` 后按 `index` 顺序播放, 若流式失败则回退到原 `/api/chat` + `/api/tts`。
- 使用 Web Audio API 对 JS 播放路径做能量分析; 浏览器拦截自动播放时, 保留原生音频控件和文字回复。
- V0.4 增加“后台监听”显式开关, 用户授权后开启麦克风, 本地 RMS VAD 只截取短音频片段做唤醒判断。
- V0.4 命中唤醒词后, 同句剩余文本可直接进入 `/api/chat`; 如果只有唤醒词, 前端进入一次正式指令录音。
- V0.4 未命中唤醒词时丢弃短片段, 不进入 `/api/chat`, 不保存未命中环境音。
- V0.4.1 增加连续对话窗口: TTS 播报结束后进入 `followup_listening`, 在配置窗口内可直接追问, 超时或达到轮数后回到唤醒监听。
- V0.6 在 FVS 主画布模式下, 未唤醒时只显示角落麦克风入口; 唤醒、连续追问、思考或播报时展开悬浮语音面板, 显示状态动画和文字记录。
- V0.6 在正式指令或连续追问进入处理后立即播放等待提示语音 `收到, 正在为您查找信息。`; AI 结果 TTS 开始播放时会打断等待提示并优先播报最终回答。

边界:

- 当前已实现阿里云百炼真实 ASR / TTS 最小 Provider, 默认仍可通过 Mock 开关回退。
- 真实 TTS 接口验证通过; 浏览器麦克风 16k WAV 真实 ASR 已通过人工验收。
- 当前 V0.5 已接 RAGFlow MCP 检索; 仍不接真实 FVS。
- V0.6 已接入 FVS iframe host 主画布, 但语音权限仍由数字人主页面申请。
- Mock TTS 固定生成 `wav`; CosyVoice 真实 TTS 当前按 `TTS_AUDIO_FORMAT` 输出 mp3 或其他格式。
- V0.4 后台监听真实麦克风唤醒已完成人工验收。V0.4.1 连续对话窗口已通过构建、接口验证和浏览器人工验收。
- 当前优化是“文本增量 + 分段 TTS 文件播放”, 不是供应商返回音频字节后立即边下边播的真音频流。真正音频流式仍留到后续优化。

## 第一阶段简化策略

ASR:

- 非严格流式可接受。
- 前端录制短音频。
- 后端上传短音频。
- 返回最终文本。

TTS:

- 先生成完整音频; V0.3 Mock 使用 wav, 真实供应商后续可使用 mp3。
- 前端播放音频或展示 Mock 音频就绪状态。
- Web Audio API 分析音频能量。
- 声波 / 语音球同步动效。

## 第二阶段优化

- ASR 流式识别。
- 将当前 VAD + 短片段 ASR 唤醒优化为更稳定的本地 KWS 或供应商热词方案。
- Dora SSE 流式展示。V0.5 已在 `/api/chat/stream` 中实现基础增量展示。
- TTS 流式合成与边播报。V0.5 已实现分段 TTS 预合成和按段播放; 后续再评估供应商级音频流式。

## 异常兜底

ASR 失败:

```text
我没有听清楚，请您再说一遍。
```

TTS 失败:

```text
前端仍展示文字回复，不播放语音。
```

## 待确认

- 正式演示或客户移交前是否轮换当前 API Key。
- V0.4 后台监听在客户演示环境中的麦克风权限策略。
- 延迟目标。
- 是否允许云端语音识别和合成。
- 是否需要热词。
