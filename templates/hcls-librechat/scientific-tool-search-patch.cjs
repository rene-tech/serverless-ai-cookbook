'use strict';

const ROUTING_NOTICE =
  'Catalog and available-App requests use the already loaded ' +
  'workbench_list_apps_mcp_scientific-demos tool. Never use an empty ' +
  'scientific-ai-apps server listing for catalog discovery.';

/**
 * Prevent LibreChat's deferred-tool search from dumping every Scientific AI
 * tool and schema into one turn. Focused non-empty searches remain unchanged.
 * The compact workbench catalog is caller-authorized and is the supported
 * discovery contract.
 */
function patchFactory(source) {
  if (source.includes('scientific_catalog_listing_disabled')) return source;

  const listingAnchor = 'Deferred tools (search to load; \\u2026 = has params, search first):';
  if (!source.includes(listingAnchor)) {
    throw new Error('Unsupported pinned ToolSearch description');
  }
  source = source.replaceAll(listingAnchor, `${ROUTING_NOTICE}\\n\\n${listingAnchor}`);

  const guardAnchor = 'const hasServerFilter = serverFilters.length > 0;';
  const matches = source.split(guardAnchor).length - 1;
  if (matches !== 1) {
    throw new Error(`Unsupported pinned ToolSearch guard count: ${matches}`);
  }
  source = source.replace(guardAnchor, `${guardAnchor}
		if (query.trim() === "" && serverFilters.includes("scientific-ai-apps")) return ["Catalog/tool enumeration is intentionally disabled for scientific-ai-apps. Call the already loaded workbench_list_apps_mcp_scientific-demos tool exactly once instead.", {
			tool_references: [],
			metadata: {
				scientific_catalog_listing_disabled: true,
				mcp_server: serverFilters
			}
		}];`);
  return source;
}

/** Keep the existing trusted host budget notice transparent to discovery only.
 * The provider still receives the complete history and its unchanged budget.
 * Never scan through user/steering messages or accept a text-only lookalike.
 */
function patchDiscoveries(source, format = 'cjs') {
  if (!['cjs', 'esm'].includes(format)) throw new Error('Unsupported discovery module format');
  if (source.includes('scientificHostBudgetNotice')) throw new Error('Discovery notice patch already installed');
  for (const name of ['extractToolDiscoveries', 'hasToolSearchInCurrentTurn']) {
    const anchor = `function ${name}(messages) {`;
    if (source.split(anchor).length !== 2) throw new Error(`Unsupported pinned discovery seam: ${name}`);
    source = source.replace(anchor, `${anchor}
\tif (scientificHostBudgetNotice.isHostBudgetNotice(messages.at(-1))) messages = messages.slice(0, -1);`);
  }
  const helper = '/opt/hcls-librechat/scientific-study-admission.cjs';
  return (format === 'esm'
    ? `import scientificHostBudgetNotice from '${helper}';\n`
    : `const scientificHostBudgetNotice = require('${helper}');\n`) + source;
}

module.exports = { patchFactory, patchDiscoveries, ROUTING_NOTICE };
