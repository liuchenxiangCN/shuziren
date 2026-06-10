# ADR-0003 Screen Action Whitelist

## Status

Accepted

## Context

大屏控制涉及页面切换和前端执行能力。如果允许大模型直接生成 JavaScript 并执行, 会带来安全、稳定性和误操作风险。

## Decision

大屏控制只允许走动作白名单:

```text
用户语音
-> Dora 判断为大屏控制意图
-> 输出 action_id
-> Gateway 校验白名单
-> 前端执行预置 FVS Adapter
-> 返回执行结果
```

禁止:

- 大模型直接输出 JavaScript。
- 前端执行未经后端校验的动作。
- Dora 输出任意函数名后直接调用。

## Consequences

优点:

- 控屏动作可审计。
- 避免模型误操作。
- 客户移交时安全边界清晰。

代价:

- 每新增大屏动作都需要维护白名单。
- Dora Prompt 和白名单描述需要保持一致。

