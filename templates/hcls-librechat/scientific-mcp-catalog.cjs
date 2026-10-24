'use strict';

// A tool's name can stay the same while its schema changes. Read one complete
// catalog per selected server per request, through the existing authorized
// connection. Do not mutate the current graph or replace the shared cache.
function createReader({ getSnapshot, configGeneration, isEphemeral, warn }) {
  const requests = new WeakMap();
  return async ({ req, userId, serverName, serverConfig, getCached, warn: report = warn }) => {
    if (!req || !userId || !serverConfig || isEphemeral(serverConfig)) {
      return getCached(userId, serverName, serverConfig);
    }
    let reads = requests.get(req);
    if (!reads) {
      reads = new Map();
      requests.set(req, reads);
    }
    const key = JSON.stringify([userId, serverName, configGeneration(serverConfig)]);
    if (!reads.has(key)) {
      reads.set(key, (async () => {
        const cached = await getCached(userId, serverName, serverConfig);
        try {
          // The manager checks user/config generations, preserves app vs user
          // scope, and the inspector rejects incomplete paginated snapshots.
          // Its existing connection timeout/ordering rules remain authoritative.
          const snapshot = await getSnapshot(userId, serverName, serverConfig);
          if (snapshot?.tools != null) return snapshot.tools; // {} is removal.
        } catch {
          // Do not log credentials, URLs, tool bodies, or upstream exceptions.
        }
        if (cached != null) {
          report('[MCP Catalog] Refresh unavailable; using the last complete catalog for this request');
        }
        // Failed reads are remembered only for this request, never as fresh.
        // Missing/OAuth-pending connections use the normal loader below us.
        return cached;
      })());
    }
    return reads.get(key);
  };
}

let reader;
module.exports = (context) => {
  if (!reader) {
    const { getMCPManager } = require('/app/api/config');
    const api = require('/app/packages/api/dist/index.cjs');
    reader = createReader({
      getSnapshot: (...args) => getMCPManager()?.getServerToolFunctionsSnapshot(...args),
      configGeneration: api.getMCPAppToolsPublicationGeneration,
      isEphemeral: api.requiresEphemeralUserConnection,
      warn: () => {},
    });
  }
  return reader(context);
};
module.exports.createReader = createReader;

function replaceOnce(source, before, after) {
  if (source.split(before).length !== 2) throw new Error('Unsupported pinned MCP catalog consumer');
  return source.replace(before, after);
}
module.exports.patchDefinitions = (source) => replaceOnce(source,
  'const cached = await getMCPServerTools(userId, serverName, serverConfig);',
  `const cached = await require('/opt/hcls-librechat/scientific-mcp-catalog.cjs')({
      req, userId, serverName, serverConfig, getCached: getMCPServerTools,
      warn: (message) => logger.warn(message),
    });`);
module.exports.patchInstances = (source) => replaceOnce(source,
  'availableTools = await getMCPServerTools(safeUser.id, serverName, config.config);',
  `availableTools = await require('/opt/hcls-librechat/scientific-mcp-catalog.cjs')({
              req: options.req, userId: safeUser.id, serverName, serverConfig: config.config,
              getCached: getMCPServerTools, warn: (message) => logger.warn(message),
            });`);
