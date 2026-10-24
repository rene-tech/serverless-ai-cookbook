# Optional cBioPortal research plugin

`plugins/cbioportal-research` is an opt-in Agent Plugins 1.0.0 package: two
official hosted MCP connections and one original portable skill. It uses the
existing LibreChat plugin loader, OAuth manager and report tools. It installs
no database, proxy, scheduler or GPU runtime. The default image packages it at `/opt/hcls-librechat/plugins/cbioportal-research`
for explicit activation; it remains separate from the canonical skill bundle and
is not automatically connected in other clients.

Install the package as one child of a versioned directory on the instance's
persistent `/data` filesystem, retaining any already installed plugins. Set
`DEPLOYMENT_PLUGINS_DIR` to that directory and `DEPLOYMENT_PLUGIN_DATA_DIR` to
a persistent data directory in the instance's existing runtime environment.
Verify the package with the exact installed `loadPluginsFromDirectory` before
activation. Back up state and restart only the authorized idle client. Preserve
the existing skill path, provider credentials, user accounts, conversations,
model settings, shared bucket and study owner.

The actual LibreChat release used for qualification already supports Agent
Plugins. Existing supported clients can install this package without a runtime
patch; new default images include the same package. Copying the package
to `/data` makes it survive provider VM replacement when that state filesystem
and environment are retained. Do not activate it in other deployments merely
because the source is published.

The navigator at `https://mcp.cbioportal.org/navigator/mcp` currently needs no
login. Make its tools available to the chosen agent, keeping `resolve_and_route`
and `navigate_to_study_view` directly loaded (`defer_loading: false`) and deferring
the other four schemas. This avoids an unnecessary discovery step for ordinary
study lookups. Preserve that agent's existing tools/customizations.
The database at `https://mcp.cbioportal.org/db/mcp` advertises OAuth discovery,
dynamic client registration, S256 and `client_secret_post`; LibreChat handles
these natively. Do not seed the database into every chat before authentication.
The user connects it in MCP Settings, signs in with Google and selects it when
needed. For a saved agent, enabling the connection is a separate step from
adding its tools to that agent. Preserve existing tools and add
`sys__all__sys_mcp_cbioportal-database` with the matching `mcpServerNames` entry;
keep `list_guides` and `list_studies` directly loaded and defer other schemas.
Use the normal agent editor/API where available. An authorized operator repair
must back up the agent, compare against the current version and change only the
selected tools/options; no instance restart or token revocation is needed.
Keep the instance's correct HTTPS `DOMAIN_SERVER` for the callback.
No manually supplied shared database API key is needed.

Diagnose connection status, user authorization and agent tool selection
independently. `tool_search` excludes already-loaded tools. "No MCP server
matched" is not evidence that a connected user's OAuth credentials are invalid.

Acceptance covers exact package loading, unchanged existing skills/settings,
public study resolution and link generation from the actual browser agent,
clear unauthenticated database behavior, preserved chat state, and persisted
configuration. After owner consent, qualify actual queries in the saved agent,
then reopen the conversation and verify its retained tool evidence. For CNA
analysis, inspect the full discrete profile, assay coverage and missingness;
rank all measured genes with bounded aggregate queries and retain provenance.
Connection status or a successful navigation call does not qualify a database
analysis, and query success does not by itself qualify token refresh.
Hosted query logging means private documents and
patient information must not be included in external queries.

The upstream database README calls itself MIT, but its inspected `LICENSE`
contains Apache-2.0. This package does not vendor its implementation or prompts;
the companion skill is original guidance and references the official services.
