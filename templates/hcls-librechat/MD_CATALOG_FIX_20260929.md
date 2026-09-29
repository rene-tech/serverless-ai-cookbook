# Molecular-dynamics discovery correction

The deployed MD client could return only three of five authorized Apps for
`workbench_list_apps(query="molecular dynamics")`. AMBER26 and distributed
GROMACS lacked that phrase in their display names. All five were incorrectly
classified as `Other`, so the agent mistook a text-search omission for missing
authorization. The Apps page and platform grants were correct; this was a client
discovery defect, not an engine or license failure.

`demos/service.cjs` now recognizes the five existing MD App IDs when their live
operation is `run-workflow`, classifies them as `Molecular dynamics`, and gives
the group a native-trajectory/checkpoint example. Search normalizes case,
hyphens and underscores. It still starts from the caller-authorized live
catalog: no App is fabricated and no additional grant is issued. Unknown
workflow engines stay `Other` rather than being guessed to be MD.

Regression coverage includes all five Apps, AMBER's actual non-MD display name,
hyphenated/underscored category searches, a restricted two-App key and an unknown
workflow. All 19 `node --test demos/service.test.cjs` tests passed.

## Scoped runtime image

- Base: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:81a2f3b54a98299933d487ccca4e9eb3fbea3130257a5a818a83940127429a4d`.
- Catalog-only image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc@sha256:16b34a377caf015553d4d51ef78721ce1eb142d6e5c9a57ccd7cffdf7b9cdc65`.
- Exactly one added layer replaces `/opt/hcls-librechat/demos/service.cjs`.
  The original file matched the repository byte-for-byte before the patch.
  Original runtime configuration and all original layer digests are unchanged.
- Published regional tag: `lc:lynx-md-catalog-20260929`.

For a full rebuild the existing Dockerfile already copies this source. The
bounded release used the established `crane append` mechanism with a root-owned
tar entry at the exact runtime path; it did not rebuild or silently update the
large inherited client/runtime dependencies.

Only the new Lynx workbench is in this deployment scope. The owner clarified
that both people need separate logins on **one shared instance**, not one
instance per person. Final endpoint: `aiendpoint-e00kybbs8a1sbxcfyw`. No other
customer, demo or speech client is replaced. Initial onboarding client-local
state is exported before stop; the shared key, login passwords, bucket and
scientific model deployments are preserved.

Both ordinary logins passed HTTPS authentication, five-App discovery and
mounted workspace read/write on that same final endpoint. Application chat
histories remained account-scoped (cross-account messages return 404); workspace
files are deliberately shared. Two concurrent real agent conversations each
called `workbench_list_apps` exactly once with `molecular dynamics` and completed
without errors, listing all five IDs including `amber` and `gromacs-mpi`.
The installed catalog module independently returned all five under Molecular
dynamics. These are HTTP/SSE client and runtime checks, not a fresh visual/browser
qualification. Broader scientific/scaling qualification is not established by
this presentation-only fix.
