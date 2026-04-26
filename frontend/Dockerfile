# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Disable husky (no .git in Docker context)
ENV HUSKY=0

COPY package*.json ./
RUN npm ci --ignore-scripts

COPY . .
# VITE_API_URL intentionally left empty — nginx proxies /api/* to backend
RUN npm run build


# ── Stage 2: serve ────────────────────────────────────────────────────────────
FROM nginx:alpine

RUN apk add --no-cache apache2-utils

ENV PORT=80
ENV BACKEND_URL=http://backend:8000

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

CMD ["/docker-entrypoint.sh"]
