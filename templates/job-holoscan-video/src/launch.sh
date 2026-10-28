#!/bin/sh
# Retain the pinned NVIDIA image's supported-device CUDA compatibility probe.
# It selects compat libraries only after cudaCheck succeeds, otherwise preserving
# the host driver path. This script neither installs nor changes a host driver.
. /etc/shinit_v2
printf '%s\n' "Holoscan CUDA compatibility probe: ${_CUDA_COMPAT_STATUS:-not run; host driver not detected}" >&2
exec "$@"
