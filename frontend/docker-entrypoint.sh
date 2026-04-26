#!/bin/sh
set -e

: "${BACKEND_URL:=http://backend:8000}"
: "${PORT:=80}"
: "${AUTH_USER:=admin}"
: "${AUTH_PASS:=changeme}"

printf '%s:%s\n' "${AUTH_USER}" "$(openssl passwd -apr1 "${AUTH_PASS}")" > /etc/nginx/.htpasswd

envsubst '${BACKEND_URL} ${PORT}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
