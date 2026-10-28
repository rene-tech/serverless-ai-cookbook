# syntax=docker/dockerfile:1.7
# Source-only recipe; NVIDIA simulator/component/asset licenses still apply.
FROM ghcr.io/astral-sh/uv@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 AS uv
FROM nvcr.io/nvidia/base/ubuntu@sha256:43fa5063e80fbbc533892af3ccca190868ce48db5a8928b19d7815c40436af8e
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl git gpgv libatomic1 libegl1 libgl1 \
    libglib2.0-0 libglu1-mesa libglx0 libgomp1 libnghttp2-14 libsm6 libxi6 \
    libxrandr2 libxt6 unzip util-linux && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy \
    NVIDIA_DRIVER_CAPABILITIES=all NVIDIA_VISIBLE_DEVICES=all \
    VK_DRIVER_FILES=/etc/vulkan/icd.d/nvidia_icd.json PYTHONDONTWRITEBYTECODE=1 \
    I4H_WORKFLOWS=/opt/i4h
RUN mkdir -p /etc/vulkan/icd.d /usr/share/glvnd/egl_vendor.d \
    && printf '%s\n' '{"file_format_version":"1.0.0","ICD":{"library_path":"libGLX_nvidia.so.0","api_version":"1.3.194"}}' > /etc/vulkan/icd.d/nvidia_icd.json \
    && printf '%s\n' '{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}' > /usr/share/glvnd/egl_vendor.d/10_nvidia.json
ARG I4H_REVISION=5b430a6d8d8c9cccc547b05b5e079d22b08ade9e
RUN git clone --filter=blob:none https://github.com/isaac-for-healthcare/i4h-workflows.git /opt/i4h \
    && git -C /opt/i4h checkout --detach ${I4H_REVISION} \
    && test "$(git -C /opt/i4h rev-parse HEAD)" = "${I4H_REVISION}" \
    && /opt/i4h/third_party/setup.sh arena
WORKDIR /opt/i4h
RUN --mount=type=cache,id=isaac-healthcare-uv-amd64,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev --project arena
COPY pyproject.toml /opt/isaac-healthcare/pyproject.toml
COPY build-requirements.txt /opt/isaac-healthcare/build-requirements.txt
COPY src /opt/isaac-healthcare/src
COPY runtime-requirements.txt /opt/isaac-healthcare/runtime-requirements.txt
RUN uv pip install --python /opt/i4h/arena/.venv/bin/python --require-hashes \
    -r /opt/isaac-healthcare/runtime-requirements.txt
RUN uv pip install --no-deps --build-constraints /opt/isaac-healthcare/build-requirements.txt --python /opt/i4h/arena/.venv/bin/python /opt/isaac-healthcare
COPY training /opt/isaac-healthcare/training
RUN /opt/i4h/arena/.venv/bin/python -I /opt/isaac-healthcare/training/verify_source.py /opt/i4h \
    && uv pip install --python /opt/i4h/arena/.venv/bin/python --require-hashes \
       -r /opt/isaac-healthcare/training/rl-requirements.lock \
    && uv pip install --no-deps --build-constraints /opt/isaac-healthcare/build-requirements.txt --python /opt/i4h/arena/.venv/bin/python /opt/i4h/rl
# Dataset owns a separate Python/NumPy/Torch environment; never sync it into Arena.
RUN --mount=type=cache,id=isaac-healthcare-dataset-uv-amd64,target=/root/.cache/uv,sharing=locked \
    uv python install 3.11.15 \
    && UV_PROJECT_ENVIRONMENT=/opt/i4h/tools/dataset/.venv \
       uv sync --frozen --no-dev --python 3.11.15 --project /opt/i4h/tools/dataset
RUN /opt/i4h/arena/.venv/bin/python -I -c \
    'import importlib.metadata as m; assert m.version("torch").split("+")[0] == "2.10.0"; assert m.version("numpy").split(".")[0] == "2"; assert m.version("rsl-rl-lib") == "5.0.1"; import hydra, omegaconf, i4h_rl.cli' \
    && /opt/i4h/tools/dataset/.venv/bin/python -I -c \
    'import sys,numpy; assert sys.version_info[:2] == (3,11); assert numpy.__version__ == "1.26.4"; from i4h_tools.dataset.cli import convert,inspect; from lerobot.common.datasets.lerobot_dataset import LeRobotDataset'
ENV I4H_ARENA_PYTHON=/opt/i4h/arena/.venv/bin/python \
    I4H_DATASET_PYTHON=/opt/i4h/tools/dataset/.venv/bin/python
COPY scripts /opt/isaac-healthcare/scripts
COPY patches /opt/isaac-healthcare/patches
RUN /opt/i4h/arena/.venv/bin/python /opt/isaac-healthcare/scripts/apply_runtime_patches.py
COPY asset-sources.json /opt/isaac-healthcare/asset-sources.json
RUN /opt/i4h/arena/.venv/bin/python /opt/isaac-healthcare/scripts/fetch_assets.py \
    /opt/isaac-healthcare/asset-sources.json /opt/i4h-assets/v0.9.0-7cf86a1 \
    --composed-report /opt/i4h-assets/v0.9.0-7cf86a1/composed-assets.json
RUN /opt/i4h/arena/.venv/bin/python /opt/isaac-healthcare/scripts/localize_kit_assets.py
RUN /opt/i4h/arena/.venv/bin/python /opt/isaac-healthcare/scripts/verify_runtime.py
RUN useradd --uid 10001 --create-home runtime && mkdir /work && chown 10001:10001 /work
USER 10001:10001
RUN /opt/i4h/arena/.venv/bin/python -I -c 'import i4h_rl.cli,hydra,omegaconf' \
    && /opt/i4h/tools/dataset/.venv/bin/python -I -c 'from i4h_tools.dataset.cli import convert,inspect'
RUN /opt/i4h/arena/.venv/bin/python /opt/isaac-healthcare/scripts/verify_runtime.py
WORKDIR /work
ENTRYPOINT ["/opt/i4h/arena/.venv/bin/python", "-I", "-m", "isaac_healthcare_runtime.runtime"]
