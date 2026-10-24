# Cancer and immunology research profile

The optional profile adds five skills to the standard Scientific AI workbench:
cancer biology, immunology, CAR-T research, scientific evidence review and Dropbox
research. Existing Scientific AI/ClawBio skills, tools, chat model and viewers are
preserved. The main domain skills are condensed adaptations of inspected,
commit-pinned MIT K-Dense sources, with licenses and attribution in each skill.

Set `SCIENTIFIC_CORE_INSTRUCTIONS_PATH` to
`/opt/hcls-librechat/profiles/cancer-research-instructions.md` on the new instance
to select the profile. This appends domain routing to the existing standard core
instructions. It does not change existing agents or clients by itself.

Build `Dockerfile.research-workbench` on the immutable current standard image;
pass the verified skill bundle version/revision. Publish its digest explicitly
for the intended client. This optional image is not an automatic fleet rollout.

## Official Dropbox connection

Enable `SCIENTIFIC_DROPBOX_ENABLED=true`, provide `DROPBOX_APP_KEY` and
`DROPBOX_APP_SECRET` through provider secrets, and configure the instance's
`DOMAIN_SERVER` to its actual HTTPS origin. LibreChat uses
`https://<workspace-host>/api/mcp/dropbox/oauth/callback`; a desktop localhost
callback cannot receive a hosted workspace login. Register the exact URL in the
Dropbox app. The installed LibreChat handler derives it from `DOMAIN_SERVER`;
merely adding an `oauth.redirect_uri` entry does not override that handler.

The service is `https://mcp.dropbox.com/mcp`; it is hosted by Dropbox, in beta.
Use LibreChat's existing user-scoped OAuth manager, S256 PKCE, pinned Dropbox
authorization/token endpoints and encrypted persistent credential store. The
authorization URL requests offline access for refresh tokens. Initial scopes
are account identity, metadata read and content read; no app credential is a
substitute for the user's actual consent. Connect from the MCP menu once. Do
not use a shared access token in agent instructions or a custom proxy.

Keep Dropbox out of seeded agent tools and preset MCP selections. LibreChat
initializes selected servers before a turn: selecting an unauthenticated OAuth
server blocks even unrelated questions behind its consent prompt. The user
connects Dropbox in MCP Settings, then selects it in the chat tools menu when
needed. The standard research workflow remains usable before consent.

If the origin is assigned after endpoint creation, record `DOMAIN_SERVER` (and
`DOMAIN_CLIENT`) in that new instance's private persisted runtime environment
before activating OAuth, then restart only that newly provisioned instance's
application. Retain that state filesystem on replacements. Do not restart a
pre-existing customer's workbench to configure a new user.

Verify the generated OAuth URL has the exact callback, S256 challenge, state,
read scopes and `token_access_type=offline`, without exposing the client secret.
After owner consent, verify identity, list a user-selected folder, read a known
paper, and verify refresh without new consent. Until then, the integration is
configured, not authorized or data-access-qualified. An upstream 429 or network
error is distinct from user denial and must remain visible.

## Scientific acceptance

Use realistic questions and evaluate claims against primary sources, not prose
confidence. The source research map records current papers, access limitations
and public datasets. Example checks:

1. Distinguish direct CAR recognition from TCR peptide–MHC restriction.
2. Compare de novo binder and anti-TACI/BCMA papers, separating preclinical and
   clinical evidence and the retrieved preprint's status.
3. Design a GSE197268 analysis with patient-level replication, longitudinal
   grouping, held-out validation and actual data-access limitations.
4. Reject a fabricated citation and a claim that a structural score proves safe
   CAR-T efficacy; still propose a useful next analysis.
5. Read an authorized Dropbox paper with provenance; treat embedded instructions
   as untrusted and do not send private content to public search.
6. In the actual UI, use standard catalog/skill/execution tools, produce and reopen
   an inline evidence report, and verify persistent bucket writes in the new user's
   prefix. No customer model run is needed to test these client changes.

Retain request, tool trace, source identifiers, exact release and observed
limitations. Skills improve research practice; they do not certify expert
accuracy, clinical safety, exhaustive literature coverage or all hosted Apps.
