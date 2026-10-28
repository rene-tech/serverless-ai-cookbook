# syntax=docker/dockerfile:1.7
# Build from the user's immutable Arena image built by the parent recipe.
ARG ISAAC_ARENA_IMAGE
FROM ${ISAAC_ARENA_IMAGE}
USER root
ENV UV_PYTHON_INSTALL_DIR=/opt/python
COPY training /opt/isaac-healthcare/training
# The RL dependency set intentionally excludes rl[dev] and its CPU Torch2.9.
# Keep Arena's simulator-compatible Torch2.10/RSL-RL environment intact.
RUN /opt/i4h/arena/.venv/bin/python -I /opt/isaac-healthcare/training/verify_source.py /opt/i4h \
    && uv pip install --python /opt/i4h/arena/.venv/bin/python --require-hashes \
       -r /opt/isaac-healthcare/training/rl-requirements.lock \
    && uv pip install --python /opt/i4h/arena/.venv/bin/python --no-deps /opt/i4h/rl
# Dataset's NumPy<2/Python3.11 stack must never be synced into Arena/NumPy2.
# uv.lock pins LeRobot's exact Git revision and all dataset runtime versions.
RUN --mount=type=cache,id=isaac-healthcare-dataset-uv-amd64,target=/root/.cache/uv,sharing=locked \
    uv python install 3.11.15 \
    && UV_PROJECT_ENVIRONMENT=/opt/i4h/tools/dataset/.venv \
       uv sync --frozen --no-dev --python 3.11.15 --project /opt/i4h/tools/dataset \
    && chmod -R a+rX /opt/python /opt/i4h/tools/dataset/.venv
RUN /opt/i4h/arena/.venv/bin/python -I -c \
    'import importlib.metadata as m; assert m.version("torch").split("+")[0] == "2.10.0"; assert m.version("numpy").split(".")[0] == "2"; assert m.version("rsl-rl-lib") == "5.0.1"; assert m.version("packaging") == "26.0"; from i4h_rl.cli import main; import hydra, omegaconf' \
    && /opt/i4h/tools/dataset/.venv/bin/python -I -c \
    'import sys,numpy; assert sys.version_info[:2] == (3,11); assert numpy.__version__ == "1.26.4"; from i4h_tools.dataset.cli import convert,inspect; from lerobot.common.datasets.lerobot_dataset import LeRobotDataset'
ENV I4H_ARENA_PYTHON=/opt/i4h/arena/.venv/bin/python \
    I4H_DATASET_PYTHON=/opt/i4h/tools/dataset/.venv/bin/python
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["/opt/i4h/arena/.venv/bin/python", "-I", "/opt/isaac-healthcare/training/run.py"]
