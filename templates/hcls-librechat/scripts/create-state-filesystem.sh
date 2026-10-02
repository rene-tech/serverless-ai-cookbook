#!/usr/bin/env bash
set -euo pipefail
: "${NEBIUS_PROJECT_ID:?Set the customer project}"
: "${WORKBENCH_NAME:?Set a stable workbench name}"
NEBIUS_CMD=("${NEBIUS_CLI:-nebius}")
if [[ -n "${NEBIUS_PROFILE:-}" ]]; then NEBIUS_CMD+=(--profile "$NEBIUS_PROFILE"); fi
# Creation is explicit. Do not silently reuse an arbitrary filesystem by name:
# a state volume owns accounts and must never be shared across client instances.
"${NEBIUS_CMD[@]}" compute filesystem create \
  --parent-id "$NEBIUS_PROJECT_ID" --name "${WORKBENCH_NAME}-state" \
  --size-gibibytes "${LIBRECHAT_STATE_SIZE_GIB:-32}" --type network_ssd \
  --format json
