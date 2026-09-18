# halfheaven frontend (Next.js) — BFF that proxies to halfhell with API key
FROM node:20-alpine AS base
WORKDIR /app

# deps
COPY package.json package-lock.json* ./
RUN npm ci

# source
COPY . .
# Build-time env (HALFHELL_API_URL is baked into server bundles)
ARG HALFHELL_API_URL=http://halfhell:8000
ARG HALFHELL_API_KEY
ENV HALFHELL_API_URL=$HALFHELL_API_URL
ENV HALFHELL_API_KEY=$HALFHELL_API_KEY
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["npm", "start"]
