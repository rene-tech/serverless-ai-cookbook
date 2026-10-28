# Conversational model default

The product-owner-approved default conversational model is
`moonshotai/Kimi-K3` on Nebius Token Factory, approved on October 2, 2026.
New deployments configure the general agent with high reasoning, a
1,024,000-token context ceiling and a 16,384-token completion ceiling. The
independent runtime budget remains 90 seconds per model invocation and 300 seconds of accumulated model time per turn; tool
execution and scientific job time do not consume that budget.

This replaces the earlier GLM-5.3-Flash default for new deployments. It does not
silently change existing customer instances, introduce an automatic fallback,
or qualify arbitrary scientific interpretation. The exact new release must be
tested with the seeded configuration, not just a comparison-agent override.

Do not change this default, add an automatic fallback, or change the model set
on a live customer workbench without explicit product-owner approval. A user or
deployment may still select another available model explicitly.

This policy applies to the LibreChat planning/conversation model. Models pinned
inside a specific scientific workflow—such as a qualified clinical report,
patient, clinician, or judge model—are separate explicit choices and must not be
silently rewritten when the conversational default changes.

An explicitly authorized deployment can opt in to regional primary routing by
setting `SCIENTIFIC_CHAT_MODEL` and `SCIENTIFIC_CHAT_BASE_URL`. Configure both
`SCIENTIFIC_CHAT_FALLBACK_MODEL` and `SCIENTIFIC_CHAT_FALLBACK_BASE_URL` to enable
one availability fallback. `SCIENTIFIC_CHAT_PRIMARY_WAIT_MS` bounds the wait for
initial output (default 20000 ms), within the existing overall invocation budget.
The entrypoint loads the routing transport only for this opt-in configuration.
The reusable release default and other deployments remain unchanged.

Public model selections continue through `SCIENTIFIC_CHAT_CATALOG_BASE_URL`
(default public Token Factory); only the selected primary model has fallback.
`SCIENTIFIC_CHAT_MODEL_LABEL` optionally sets the primary model's display name;
regional models are grouped as Token Factory rather than labeled public.
Both providers use the deployment's secret-backed provider credential. Operator
JSON logs record provider choice, fallback reason, HTTP status and elapsed time,
without prompts, tool results or credentials. HTTP 408/429/500/502/503/504,
connection failures and an initial-response timeout may fall back. Authentication,
invalid-request and model-not-found errors propagate. Once any text, reasoning,
refusal or tool fragment is exposed, stream interruption propagates without
switching providers. Tool execution and previously accepted work are never replayed.
