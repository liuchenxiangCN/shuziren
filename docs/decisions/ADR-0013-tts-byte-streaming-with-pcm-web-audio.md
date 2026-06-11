# ADR-0013 TTS Byte Streaming With PCM Web Audio

## Status

Accepted

## Context

V0.5 的语音优化是“Dora 文本增量 + 分段 TTS 文件播放”。该方案能提前播放短段音频, 但每段仍要等供应商生成完整文件后才可播放。V0.8 第二阶段要求实现 TTS 字节级真流式, 同时保留分段 TTS fallback。

浏览器对 MP3 / Opus 字节流的 MediaSource 支持存在兼容性差异, 且 Mock TTS 需要在无外部 API Key 时也能验证真流式播放、打断和回退。

## Decision

- 后端新增 `TtsProvider.stream_synthesize`。
- 新增 `POST /api/tts/stream`, 使用 SSE 返回 `metadata`、`audio_chunk`、`tts_error` 和 `end`。
- 真流式默认使用 `TTS_STREAMING_AUDIO_FORMAT=pcm`。
- Mock TTS 输出 PCM chunk; 阿里云 CosyVoice Provider 逐块转发 WebSocket 二进制音频帧。
- 前端使用 Web Audio API 将 PCM chunk 解码为 `AudioBuffer`, 并按时间轴排队播放。
- 前端收到 AI 结果真流式音频时继续通过统一 `cleanupAudio()` 打断等待提示音。
- `/api/chat/stream` 的 `tts_ready` 分段文件事件继续保留, 作为 `TTS_STREAMING_FALLBACK=segment` 的 fallback。

## Consequences

优点:

- 首个音频 chunk 可早于完整 TTS 文件生成。
- Mock 环境可验证真流式播放器和打断逻辑。
- 前端不接触供应商 API Key。
- 浏览器播放路径不依赖 MP3 / Opus MediaSource 支持。

代价:

- 前端需要维护一套 PCM Web Audio 调度逻辑。
- 当前真流式自动播报在收到最终 `answer` 后启动; Dora 文本增量期间仍由旧 `tts_ready` 分段方案作为 fallback。
- 如果未来要直接播放压缩音频流, 需要按目标浏览器重新评估 MediaSource / WebCodecs 兼容性。
