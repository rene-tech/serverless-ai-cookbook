# Nebius workspace branding restoration — 7 October 2026

## Scope and cause

The product is **Nebius Scientific AI Workspace**. Nebius is the primary brand;
the partner footer carries both NVIDIA and Nebius. The assistant in the model
selector remains **Nebius Scientific AI Agent**: it is an agent within the
workspace, not the product name.

Commit `2a329c1255dd67b4abda210006c11b6a845e30af` introduced a frontend rebuild
on 1 October at 14:53:50 UTC. Vite repopulated `dist` from the upstream public
assets and HTML. The OpenFF R11 image still contained the correct Nebius logo;
agent-reliability R4, built at 15:04:41 UTC, contained LibreChat's stock logo and
title. The later source-component repair restored the footer but not its static
artwork. Persistent-state and Basel registration releases inherited this.

## Fix

- Brand Vite's source `index.html` and `public/assets` **before** the rebuild.
  Do not patch only the output directory or rewrite HTML after compression/PWA
  precaching: browser-served gzip/Brotli and service-worker hashes must agree.
- Use a dedicated `/assets/nebius-logo.svg` in the persistent chat header,
  landing page and footer. Preserve branded `logo.svg` for upstream consumers.
- Restore the green Nebius shell accent and workspace title, including
  `APP_TITLE` returned by `/api/config`.
- Keep both NVIDIA and Nebius in chat, login and registration footers. Use the
  existing approved artwork, including NVIDIA's light backing for dark mode.
- Retain source branding in the image so subsequent frontend rebuilds do not
  undo it. Normal and agent-reliability Dockerfiles both verify built artwork.
- Verify actual SVG bytes, title, theme and compressed HTML, not just alt text,
  a React component's existence, or an HTTP 200.

## Image and source

- Repository: `rene-tech/serverless-ai-cookbook`
- Branch: `agent/fs2-basel-workbench-20261007`
- Implementation: `bd0a976e8fc128467d120b903d263a2dd585ce8b`
- Published build source: `fce5de0c0fe80c2f8c64191fb3fa3b18bfc599b0`
- Dockerfile: `templates/hcls-librechat/Dockerfile.branding`
- Base: `lc@sha256:ce8fc5e3a87f4910951b3733a3be3d2f53a9d5ed3bede6921e8997bba6679496`
- Release: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:nebius-branding-20261007-r1`
- Digest: `sha256:521205505fb35a9e57ce7689c2ab97f613b0962de46c49889d993b5676f3bfa9`

The additive release changes frontend assets/source and the workspace title. It
does not change inference, agent instructions, providers, grants, credentials or
customer storage. Shared-registration remains an explicit deployment opt-in.
The deployment helper's default image now points to this release; existing
customer endpoints are not automatically upgraded.

## Verification

- Four Node asset/source-rebuild regression tests passed, including rejection
  of LibreChat artwork even when the logo URL returns a valid SVG.
- Three rendered React footer tests passed: both brands, authentication footer
  before config arrives, and retained privacy/terms links.
- The actual production Vite build passed; its output passed SVG/title/theme
  verification. Final-image gzip and Brotli HTML exactly match plain HTML;
  compiled bundles contain the persistent header and both partner identities.
- Eleven existing state/deployment tests and six shared-registration/config
  tests passed. The existing Python 3.12 tarfile deprecation and upstream
  Tailwind `ease-[…]` warning are unchanged and unrelated to branding.
- Initial multi-step builder hit the inherited Docker layer ceiling. The
  successful version uses a build-time bind mount and one final added layer
  (126 total); the failed build was never deployed.

Live rollout receipt is recorded below after verification. This is a branding
and state-preservation release, not a new all-model or scientific-capacity
qualification. No browser automation or visual-layout certification is claimed.

## Deployment and rollback

Target: Basel only, `project-e00rene`, eu-north1, CPU `4vcpu-16gb`.
Predecessor: `aiendpoint-e00qgee4t72w2k3q47`.
Retain the same state filesystem `computefilesystem-e00zvjx7md6thxfyma` and
workspace bucket `fs2-basel-1b86fd1010c2f76c`. Save a private MongoDB export before
stop; the replacement additionally takes a cold state snapshot before startup.
Never start both endpoints against the state filesystem at once.

For rollback, first stop the successor, then start the retained predecessor
against the same state (there is no database migration in this release).
For state recovery, the supervisor snapshot is named
`basel-nebius-branding-20261007`. Private deployment/export evidence is under
`/home/tux/secure-handoff/fs2-basel-onboarding-20261007/branding-*`; do not commit
these files because the export includes account and credential records.
