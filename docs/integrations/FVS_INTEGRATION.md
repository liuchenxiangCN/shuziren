# FVS 集成说明

## 目标

让数字人前端能够嵌入或联动 FVS 看板, 并通过白名单动作控制页面或 Tab 切换。

## 第一阶段

本地开发优先使用 Mock FVS:

- 页面中展示 Mock 大屏或 iframe 占位。
- 执行动作时打印日志或改变 Mock 页面状态。
- 不依赖真实 FVS 接口。

## 第二阶段

接入真实 FVS:

- 优先验证 FVS 是否允许 iframe 嵌入。
- 如果允许, 使用数字人外壳页面嵌入 FVS。
- 如果不允许, 改为 FVS 内嵌数字人全局浮层。
- 控屏方式根据 FVS 实际接口选择 `postMessage` 或预埋 Adapter。

## Mock Adapter 示例

```ts
export async function executeFvsAction(action: ScreenAction) {
  console.log("Mock execute FVS action", action);
  return {
    success: true,
    message: `Mock executed ${action.id}`
  };
}
```

## postMessage 示例

```ts
export async function executeFvsAction(action: ScreenAction) {
  if (window.parent && action.fvsFunction) {
    window.parent.postMessage({
      type: "FVS_ACTION",
      functionName: action.fvsFunction,
      params: action.params
    }, "*");
  }
}
```

## 待确认

- FVS 看板访问地址。
- FVS 是否允许 iframe。
- FVS 是否设置 `X-Frame-Options` 或 CSP。
- FVS 是否已有 JS 控制接口。
- FVS 推荐使用 `postMessage` 还是直接函数调用。
- 页面 / Tab 的真实 ID。

