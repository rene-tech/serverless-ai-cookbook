# Conversational model default

The product-owner-approved default conversational model is
`moonshotai/Kimi-K3` on Nebius Token Factory, approved on October 2, 2026.
The general agent uses high reasoning, a 131072-token context ceiling and a
16384-token completion ceiling. The independent runtime budget remains 90 seconds
per model invocation and 300 seconds of accumulated model time per turn; tool
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
