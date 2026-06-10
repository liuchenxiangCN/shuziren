# ADR-0005 Package Management

## Status

Accepted

## Context

项目需要同时维护 Vue 前端和 FastAPI 后端。为避免后续跨对话开发时包管理方式漂移, 需要固定前后端依赖管理方案。

本机环境快照, 记录于 2026-06-10:

- Git 已安装。
- Docker Desktop 已启动, Docker Server 为 `29.5.2`。
- Node.js 为 `v24.16.0`。
- npm 为 `11.13.0`。
- Corepack 为 `0.35.0`。
- pnpm 未在 PATH 中找到。
- uv 未在 PATH 中找到。
- Python PATH 上为 `3.14.5`, 不符合本项目后端固定的 Python 3.11/3.12。

## Decision

项目标准固定为:

- 前端包管理: pnpm。
- 后端包管理: uv。
- 后端 Docker 运行时: Python 3.12。
- 非 Docker 本地后端开发: Python 3.11 或 3.12。

V0.1 可优先通过 Docker 构建环境使用 pnpm 和 uv。本机若要直接运行前后端, 需要补装 pnpm、uv 和 Python 3.12 或 3.11。

## Consequences

优点:

- 前后端包管理方式稳定。
- 后续 Codex 跨对话开发不再反复选择 npm、pip、poetry 等替代方案。
- Docker 运行时与本机 Python 3.14 解耦。

代价:

- 本机直接开发前需要补装工具。
- Dockerfile 需要显式安装或启用 pnpm 和 uv。

