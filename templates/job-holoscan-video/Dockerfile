# syntax=docker/dockerfile:1.7
FROM nvcr.io/nvidia/clara-holoscan/holoscan@sha256:9cd60e6a35ddaa697009139ad5565cedefa0034a98bae1c12f4a5bde051f202c
USER 0
ARG UPSTREAM_REVISION=7d2e3b3c2b5d48bf0bc5caeba4d715b797ae3031
LABEL org.opencontainers.image.source="https://github.com/rene-tech/serverless-ai-cookbook" \
      org.opencontainers.image.description="Recorded endoscopy tool tracking on the native Holoscan 5 operator graph"
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates patch \
    && rm -rf /var/lib/apt/lists/*
ADD --checksum=sha256:ed2f532b16a61380ca9b86a13cbbde1661b0429f3abad943255e3fa1ac3ca857 https://github.com/nvidia-holoscan/holoscan-applications/archive/7d2e3b3c2b5d48bf0bc5caeba4d715b797ae3031.tar.gz /tmp/upstream.tar.gz
RUN mkdir /opt/holoscan-endoscopy && tar -xzf /tmp/upstream.tar.gz --strip-components=1 -C /opt/holoscan-endoscopy \
    && rm /tmp/upstream.tar.gz
COPY patches/export-tracking.patch /tmp/export-tracking.patch
RUN cd /opt/holoscan-endoscopy/applications/endoscopy_tool_tracking \
    && patch -p1 --fuzz=0 < /tmp/export-tracking.patch \
    && cmake -S . -B /opt/holoscan-endoscopy/build \
       -DCMAKE_CUDA_ARCHITECTURES="89;90;100;120" \
       -DENDOSCOPY_ENABLE_VISUALIZATION=OFF -DBUILD_TESTING=ON \
    && cmake --build /opt/holoscan-endoscopy/build --parallel 4 \
    && install /opt/holoscan-endoscopy/build/endoscopy_tool_tracking /usr/local/bin/endoscopy_tool_tracking
COPY src/ /opt/holoscan-video/
RUN chmod 755 /opt/holoscan-video/launch.sh
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    HOLOSCAN_ENDOSCOPY_BINARY=/usr/local/bin/endoscopy_tool_tracking
# libcuda comes from the host at execution; do not substitute a driver stub here.
RUN test -x /usr/local/bin/endoscopy_tool_tracking \
    && python3 -c 'import numpy; assert numpy.__version__ == "2.5.4"' \
    && python3 /opt/holoscan-video/holoscan_video.py --help >/dev/null
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["/opt/holoscan-video/launch.sh", "python3", "/opt/holoscan-video/holoscan_video.py"]
