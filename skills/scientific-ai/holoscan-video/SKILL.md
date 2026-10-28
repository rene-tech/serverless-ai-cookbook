---
name: holoscan-video
description: Process recorded endoscopy video through the hosted Holoscan tool-tracking App, or use the portable Holoscan Job recipe on premises or in Nebius Serverless.
license: Apache-2.0
---

# Holoscan recorded endoscopy

For hosted execution, read `scientific-gateway`, discover App
`holoscan-endoscopy`, and fetch its live `submit_holoscan_endoscopy` schema.
Use operation `track-tools` only when this App is available to the caller.
For self-hosting, use the independent
[Docker/Serverless recipe](https://github.com/rene-tech/serverless-ai-cookbook/tree/main/templates/job-holoscan-video).
That route does not require Scientific AI credentials.

The model is the pinned CAMMA convolutional LSTM on the actual Holoscan 5 graph.
It accepts recorded MP4, MKV/WebM, AVI, H.264, HEVC or MPEG video, resizes RGB to
854×480, and produces seven tool probabilities, normalized tooltip coordinates,
and `[frames,7,60,107]` masks. This is research tool tracking, not diagnosis or
clinical control. Live capture, persistent streaming and network real-time
latency need their own qualification.

Preserve the original recording. For the hosted App, place it in an uncompressed
tar. Frame processing uses encoded pixels without automatic display rotation;
the result records the source display transform separately. Coordinates and
annotations use that encoded-pixel orientation. Upload the tar as an owned
artifact using the current gateway file client; the
manifest entry is `workload`, semantic type `holoscan-recorded-video-tar/v1`,
media type `application/x-tar`. Set `video_file` to its relative archive path.
Do not paste video bytes or base64 into chat or pass caller-controlled URLs.

Default `frame_count=0` means the entire remaining selected clip. Explain chosen
`start_frame` and `frame_stride`: recurrence starts at zero at the first selected
frame and carries across selected frames only. Temporal subsampling changes
model context. `probability_threshold` affects the optional annotation, while
all native values remain in the outputs. Never silently truncate a recording.

Keep the durable operation/idempotency identity and resume polling instead of
resubmitting. Inspect `result.json`, seven tracking rows per completed frame,
finite float32 masks with matching shape, recorded resize/frame mapping, model
hash, and artifact sizes/checksums. Decode the optional annotated MP4 and verify
frame coverage. Transport and shape checks do not establish tracking accuracy;
accuracy needs appropriately labeled recordings and an explicit protocol.

For missing files, malformed video, unavailable runtime or incomplete frames,
retain the actionable terminal error and correct its cause. Cancel only the
requested operation. Use separate owned prefixes for concurrent recordings;
private recurrent state is per execution. Keep raw data and credentials out of
chat, shared telemetry and public recipe source.
