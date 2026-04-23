#!/bin/sh
set -e

: "${BACKEND_URL:=http://backend:8000}"
: "${PORT:=80}"

envsubst '${BACKEND_URL} ${PORT}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
