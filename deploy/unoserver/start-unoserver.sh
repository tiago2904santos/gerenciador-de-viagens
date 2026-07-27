#!/bin/sh
set -eu

READY_FILE=/tmp/unoserver-ready
OUTPUT_FILE=/tmp/unoserver-warmup.pdf
rm -f "$READY_FILE" "$OUTPUT_FILE"

unoserver \
  --interface 0.0.0.0 \
  --port 2003 \
  --conversion-timeout 30 \
  --stop-after 1000 \
  --quiet &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup INT TERM

attempt=0
until unoping --host 127.0.0.1 --port 2003 --quiet >/dev/null 2>&1; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    wait "$SERVER_PID"
    exit 1
  fi
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 120 ]; then
    cleanup
    exit 1
  fi
  sleep 0.25
done

# Carrega os filtros do Writer antes de aceitar tráfego da aplicação.
unoconvert \
  --host 127.0.0.1 \
  --port 2003 \
  --host-location local \
  --dont-update-index \
  /opt/unoserver/warmup.rtf \
  "$OUTPUT_FILE"
test -s "$OUTPUT_FILE"
touch "$READY_FILE"

wait "$SERVER_PID"
