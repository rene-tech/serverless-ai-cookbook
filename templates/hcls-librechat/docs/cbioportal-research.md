# Optional cBioPortal research plugin

`plugins/cbioportal-research` is an opt-in Agent Plugins 1.0.0 package: two
official hosted MCP connections and one original portable skill. It uses the
existing LibreChat plugin loader, OAuth manager and report tools. It installs
no database, proxy, scheduler or GPU runtime. The standard image/default skill
bundle and other clients are unchanged.

Install the package as one child of a versioned directory on the instance's
persistent `/data` filesystem, retaining any already installed plugins. Set
`DEPLOYMENT_PLUGINS_DIR` to that directory and `DEPLOYMENT_PLUGIN_DATA_DIR` to
a persistent data directory in the instance's existing runtime environment.
Verify the package with the exact installed `loadPluginsFromDirectory` before
activation. Back up state and restart only the authorized idle client. Preserve
the existing skill path, provider credentials, user accounts, conversations,
model settings, shared bucket and study owner.

The actual LibreChat release used for qualification already supports Agent
Plugins; no client runtime patch or new image is required. Copying the package
to `/data` makes it survive provider VM replacement when that state filesystem
and environment are retained. Do not activate it in other deployments merely
because the source is published.

The navigator at `https://mcp.cbioportal.org/navigator/mcp` currently needs no
login. Make its tools available to the chosen agent, with `defer_loading: true`
for its detailed schemas, preserving that agent's existing tools/customizations.
The database at `https://mcp.cbioportal.org/db/mcp` advertises OAuth discovery,
dynamic client registration, S256 and `client_secret_post`; LibreChat handles
these natively. Do not seed the database into every chat before authentication.
The user connects it in MCP Settings, signs in with Google and selects it when
needed. Keep the instance's correct HTTPS `DOMAIN_SERVER` for the callback.
No manually supplied shared database API key is needed.

Acceptance covers exact package loading, unchanged existing skills/settings,
public study resolution and link generation from the actual browser agent,
clear unauthenticated database behavior, saved inline reports, and persisted
configuration. Authenticated database queries/refresh remain unqualified until
the owner completes Google consent. Never report navigator metadata as a
completed database analysis. Hosted query logging means private documents and
patient information must not be included in external queries.

The upstream database README calls itself MIT, but its inspected `LICENSE`
contains Apache-2.0. This package does not vendor its implementation or prompts;
the companion skill is original guidance and references the official services.
