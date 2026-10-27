# syntax=docker/dockerfile:1.7
# PyTorch 2.9.1 + CUDA 12.8 includes Ada/Hopper/Blackwell code; exact GPU runs
# still need qualification. MONAI 1.6.1 requires torch >= 2.8.
FROM pytorch/pytorch@sha256:7b324d212a4450795b49edba9949b7cdc72429148a64e974334bfe5774d51385
USER 0
COPY requirements.txt /tmp/requirements.txt
RUN /opt/conda/bin/python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
COPY bundle/ /opt/monai/bundle/
COPY fetch_bundle.py /opt/monai/fetch_bundle.py
RUN /opt/conda/bin/python /opt/monai/fetch_bundle.py --output /opt/monai/bundle
COPY pyproject.toml /tmp/recipe/pyproject.toml
COPY monai_workflow/ /tmp/recipe/monai_workflow/
RUN /opt/conda/bin/python -m pip install --no-deps --no-build-isolation /tmp/recipe \
    && /opt/conda/bin/python -m pip check
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MONAI_CPU_THREADS=8 \
    HOME=/tmp USER=monai CUDA_CACHE_PATH=/tmp/cuda-cache
LABEL org.opencontainers.image.title="MONAI pretrained spleen CT finite inference" \
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.source="https://github.com/rene-tech/serverless-ai-cookbook" \
    ai.monai.bundle.revision="8c4da75225ff7cb30292729dd704cceccae5413c"
USER 10001:10001
RUN /opt/conda/bin/python -I -c 'from monai_workflow.runtime import verify_bundle; verify_bundle("/opt/monai/bundle")' \
    && /opt/conda/bin/python -I -c 'import monai, torch, nibabel; assert monai.__version__ == "1.6.1"; assert torch.__version__ == "2.9.1+cu128"' \
    && /opt/conda/bin/python -I -m monai_workflow.runtime --help >/dev/null
WORKDIR /tmp
ENTRYPOINT ["/opt/conda/bin/python", "-I", "-m", "monai_workflow.runtime"]
