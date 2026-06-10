# ASR / TTS 集成说明

## 目标

接入国产 ASR 和 TTS, 完成语音输入和语音播报。

## 默认策略

- ASR: 阿里云百炼 Paraformer。
- TTS: 阿里云百炼 Qwen-TTS Realtime 或 CosyVoice。
- 备选: 科大讯飞、火山引擎等国产供应商。

## 配置项

```env
ASR_PROVIDER=aliyun
ASR_API_KEY=replace_me
ASR_MODEL=paraformer-realtime
ASR_REGION=cn-beijing

TTS_PROVIDER=aliyun
TTS_API_KEY=replace_me
TTS_MODEL=qwen3-tts-flash-realtime
TTS_VOICE=Cherry
TTS_AUDIO_FORMAT=mp3

ENABLE_MOCK_ASR=true
ENABLE_MOCK_TTS=true
```

## 第一阶段简化策略

ASR:

- 非严格流式可接受。
- 前端录制短音频。
- 后端上传短音频。
- 返回最终文本。

TTS:

- 先生成完整 mp3。
- 前端播放音频。
- Web Audio API 分析音频能量。
- 声波 / 语音球同步动效。

## 第二阶段优化

- ASR 流式识别。
- Dora SSE 流式展示。
- TTS 流式合成与边播报。

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

- 供应商账号和 API Key。
- 音频格式要求。
- 是否支持 WebM / PCM。
- 延迟目标。
- 是否允许云端语音识别和合成。
- 是否需要热词。

