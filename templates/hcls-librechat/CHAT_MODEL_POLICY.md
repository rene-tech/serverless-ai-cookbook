# Conversational model default

The product-owner-approved default conversational model is
`zai-org/GLM-5.3-Flash` on Nebius Token Factory.

Do not change this default, add an automatic fallback, or change the model set
on a live customer workbench without explicit product-owner approval. A user or
deployment may still select another available model explicitly.

This policy applies to the LibreChat planning/conversation model. Models pinned
inside a specific scientific workflow—such as a qualified clinical report,
patient, clinician, or judge model—are separate explicit choices and must not be
silently rewritten when the conversational default changes.

Workbench workflows complete the requested action and the reasoning, analysis
and checks necessary for its scientific deliverable, then return the result and
stop. A straightforward run does not automatically become an unrelated notebook,
study, extra model call, literature search or report. Necessary authorization,
input validation, isolation and clinical review remain intact. Investigation and
debugging remain available when requested or necessary to resolve a failure.

This is a request-following policy, not a reduction in scientific reasoning.
Models, provider parameters, reasoning settings and output/context/tool-call
ceilings are unchanged.
