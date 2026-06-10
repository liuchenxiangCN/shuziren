FROM node:24-alpine AS build

WORKDIR /app

RUN corepack enable

COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY apps/web/ ./

ARG VITE_API_BASE_URL=http://localhost:18080
ARG VITE_FVS_URL=
ARG VITE_FVS_INTEGRATION_MODE=mock
ARG VITE_FVS_TARGET_ORIGIN=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_FVS_URL=$VITE_FVS_URL
ENV VITE_FVS_INTEGRATION_MODE=$VITE_FVS_INTEGRATION_MODE
ENV VITE_FVS_TARGET_ORIGIN=$VITE_FVS_TARGET_ORIGIN

RUN pnpm build

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
