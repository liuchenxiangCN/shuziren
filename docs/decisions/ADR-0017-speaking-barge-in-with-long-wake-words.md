# ADR-0017: 播报中长唤醒词确认打断

## Status

Accepted

## Date

2026-06-11

## Context

V1.0 现场复演中, 用户希望 AI 回复语音正在播放时, 可以通过再次唤醒来打断当前播报并进入下一轮对话。当前前端在 `speaking` 状态不做 ASR 唤醒判断, 只会在播报结束后进入连续追问窗口。

大屏现场通常有外放, AI 自己的播报声可能被麦克风再次采集。如果采用“一检测到人声就打断”, 容易被外放、环境声或旁人说话误触发。当前项目尚未接入本地关键词唤醒 KWS, 播报中打断仍需依赖短片段 ASR 确认。

## Decision

- 在 `speaking` 状态下继续使用前端 VAD 截取短音频片段, 但只用于 `barge_in` 检查。
- `barge_in` 只匹配配置项 `barge_in_wake_words`, 当前为长唤醒词“小天小天”“你好小天”, 不包含短词“小天”。
- ASR 确认命中 `barge_in_wake_words` 后, 前端调用 `cleanupAudio()` 停止当前 TTS, 播放唤醒反馈“您好。”, 并进入正式指令录音; 若同句包含指令, 剥离唤醒词后直接进入 `/api/chat`。
- ASR 未命中、空识别或请求失败时静默忽略, 当前 TTS 继续播放, 不进入 cooldown, 不进入 `/api/chat`。
- 播报中使用独立 VAD 参数 `barge_in_vad_threshold`、`barge_in_min_audio_ms`、`barge_in_silence_ms`、`barge_in_max_audio_ms` 和 `barge_in_ignore_after_tts_start_ms`, 便于现场单独调优。

## Consequences

- 用户可在 AI 播报中通过长唤醒词打断, 交互更接近自然对话。
- 短词“小天”仍可用于普通唤醒, 但不作为播报中打断词, 降低外放和环境声误触发概率。
- 由于当前依赖云 ASR 确认, 打断不是毫秒级即时停止; 现场体验通常为说出唤醒词后约 1-2 秒确认并停播。
- 播报中会产生额外 ASR 请求, 但只在用户已显式开启后台监听后发生, 且仍只上传 VAD 截取的短片段。

## Guardrails

- 不因任意人声或 VAD 命中直接停止 TTS。
- 不把短唤醒词“小天”放入默认 `barge_in_wake_words`。
- 未命中打断词的音频片段不进入 `/api/chat`, 不触发控屏。
- 继续使用浏览器麦克风回声消除、降噪和自动增益约束。
- 后续如需更低延迟, 应评估本地 KWS 或供应商热词能力, 而不是执行模型生成代码。
