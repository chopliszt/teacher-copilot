# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Disable husky (no .git in Docker context)
ENV HUSKY=0

COPY package*.json ./
RUN npm ci

COPY . .
# VITE_API_URL intentionally left empty — nginx proxies /api/* to backend
RUN npm run build


# ── Stage 2: serve ────────────────────────────────────────────────────────────
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
