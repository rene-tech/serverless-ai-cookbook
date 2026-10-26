#!/bin/sh
set -eu

# MongoDB opens many WiredTiger files during recovery and restored-account
# imports. The default 1024 descriptor limit is insufficient for large clients.
ulimit -n 64000

DATA_DIR="${LIBRECHAT_DATA_DIR:-/data/hcls-librechat}"
MONGO_DATA_DIR="${LIBRECHAT_MONGO_DATA_DIR:-/data/db}"
RUNTIME_SECRETS="$DATA_DIR/runtime-secrets.env"

mkdir -p "$DATA_DIR" "$MONGO_DATA_DIR" /app/uploads /app/logs
umask 077

secret_hex() {
  bytes="$1"
  od -An -N "$bytes" -tx1 /dev/urandom | tr -d ' \n'
}

if [ ! -s "$RUNTIME_SECRETS" ]; then
  {
    printf 'CREDS_KEY=%s\n' "$(secret_hex 32)"
    printf 'CREDS_IV=%s\n' "$(secret_hex 16)"
    printf 'JWT_SECRET=%s\n' "$(secret_hex 32)"
    printf 'JWT_REFRESH_SECRET=%s\n' "$(secret_hex 32)"
  } > "$RUNTIME_SECRETS"
fi

set -a
# The generated path is deployment-local state.
# shellcheck disable=SC1090
. "$RUNTIME_SECRETS"
set +a

node /opt/hcls-librechat/render-config.mjs "$CONFIG_PATH"

mongod \
  --dbpath "$MONGO_DATA_DIR" \
  --bind_ip 127.0.0.1 \
  --port 27017 \
  --fork \
  --pidfilepath "$DATA_DIR/mongod.pid" \
  --logpath "$DATA_DIR/mongod.log" \
  --noauth

node /app/seed-hcls-workbench.js
node /opt/hcls-librechat/demos/seed.cjs

# Deployment-only convenience (set SEED_DEFAULT_USER_EMAIL/PASSWORD to use).
if [ -n "${SEED_DEFAULT_USER_EMAIL:-}" ] && [ -n "${SEED_DEFAULT_USER_PASSWORD:-}" ]; then
  node /app/seed-user.js
fi

if [ "${SCIENTIFIC_CAMSOL_ENABLED:-false}" = true ]; then
  # exec below preserves this PID/start time. The auxiliary loopback service
  # exits with that exact owner; it never starts another API/study supervisor.
  camsol_owner_start=$(/opt/scientific-client/bin/python -c \
    'from pathlib import Path; import sys; print(Path("/proc/"+sys.argv[1]+"/stat").read_text().rsplit(")",1)[1].split()[19])' "$$")
  /opt/scientific-client/bin/python /opt/hcls-librechat/camsol/server.py \
    --owner-pid "$$" --owner-start "$camsol_owner_start" > "$DATA_DIR/camsol-connection.log" 2>&1 &
fi

exec /opt/scientific-client/bin/python /opt/bionemo/scientific-study-worker.py -- node /app/api/server/index.js
