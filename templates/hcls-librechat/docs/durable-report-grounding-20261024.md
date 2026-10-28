# Durable ownership and factual MD summaries

This is a source candidate, CPU-qualified without model calls. No running
workbench, installed skill, image pointer or model setting was changed.

## Receipt contract

The existing v2 executor returns `registered_phases` from its admitted immutable
plan, including model/method and observed phase state. `continuation_state`
distinguishes registered, blocked, stopped, completed and unconfirmed work.
Compare the registered scope with the user's entire request before promising
continuation. A handwritten status file or one accepted operation cannot own
unregistered future phases. Changed saved plans cannot execute; existing
operation evidence stays readable. Unknown admission stays unknown.

Keep original operation IDs and admission evidence. A partial conversation is
repaired by observing/recovering accepted IDs and scheduling only remaining
work, never by submitting the original operations again. No scheduler, retry
policy, model setting or inference contract is added here.

## Existing report pipeline

`native-md-timing` now publishes a producer-registered `customer-summary.json`.
The existing `report` analysis method accepts a `native-md` section:

```json
{"title":"Verified dynamics", "format":"native-md",
 "file":{"step":"analyze-dynamics", "file":"native-timing-report.json"}}
```

Each section rechecks its typed report against the retained publication receipt,
native result and small source-file hashes. Edited values or operation IDs fail
verification. Trajectories are not downloaded or fully rehashed again. When all
sections use this format, the aggregate also publishes a registered summary.
The existing verified `completion_summaries` projection supplies exact chat text.

Last reported temperature includes its observation step/time and source hash.
It is not a mean or necessarily an endpoint sample. Missing observations remain
unknown; native run time, integration and command wall time retain their scopes.
Source links are generated from actual workspace paths, without abbreviated
URLs. Declare individual HTML reports as deliverables for inline rendering.
The native measurement parsers are unchanged.

## Qualification and activation boundary

CPU regressions cover six synthetic retained-result analyses plus final assembly,
source/ID/value tampering, missing registration, changed admitted plans,
ambiguous admission, reconnect and cancellation. No new science is needed.
Shared instructions, gateway/batch skills and the future default-image recipe
carry the correction; this does not qualify an installed client or built image.

Activation requires the separately coordinated idle-client window. Preserve
existing chats, reports, skills/customizations, connections and process identity.
Later acceptance uses one CPU-only workflow on already-verified results with
the actual loaded skill, full returned links and saved-chat inline reports.
No extra model submissions or replay are part of that acceptance.
