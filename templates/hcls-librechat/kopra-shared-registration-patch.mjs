import { readFile, writeFile } from 'node:fs/promises';

async function replaceExact(path, before, after, expected = 1) {
  const source = await readFile(path, 'utf8');
  const count = source.split(before).length - 1;
  if (count !== expected) {
    throw new Error(`${path}: expected ${expected} patch target(s), found ${count}`);
  }
  await writeFile(path, source.replaceAll(before, after));
}

await replaceExact(
  '/app/seed-hcls-workbench.js',
  "'tavily_search_mcp_tavily'",
  "'search_mcp_tavily'",
);

await replaceExact(
  '/app/scientific-agent-instructions.md',
  '`tavily_search_mcp_tavily`',
  '`search_mcp_tavily`',
);

await replaceExact(
  '/opt/hcls-librechat/render-config.mjs',
  'tavily_search_mcp_tavily',
  'search_mcp_tavily',
);

await replaceExact(
  '/opt/hcls-librechat/scientific-tool-options.cjs',
  "'tavily_search_mcp_tavily'",
  "'search_mcp_tavily'",
);

await replaceExact(
  '/opt/hcls-librechat/render-config.mjs',
  "const sharedGatewayKey = Boolean(process.env.SCIENTIFIC_MODELS_API_KEY);",
  "const sharedGatewayKey = Boolean(process.env.SCIENTIFIC_MODELS_API_KEY);\n" +
    "const sharedRegisteredUsers = process.env.SCIENTIFIC_SHARED_GATEWAY_ENABLED === 'true' && sharedGatewayKey;",
);

await replaceExact(
  '/opt/hcls-librechat/render-config.mjs',
  "SCIENTIFIC_MODELS_API_KEY: '{{SCIENTIFIC_MODELS_API_KEY}}',\n" +
    "        SCIENTIFIC_MODELS_API_BASE_URL: '${SCIENTIFIC_MODELS_API_BASE_URL}',\n" +
    "        NEBIUS_API_KEY: '${NEBIUS_API_KEY}' },\n" +
    "      customUserVars: { SCIENTIFIC_MODELS_API_KEY: {\n" +
    "        title: 'Scientific AI API key', description: 'Your personal platform key, also configurable in the Apps panel.', sensitive: true,\n" +
    "      } }, serverInstructions: true,",
  "SCIENTIFIC_MODELS_API_KEY: sharedRegisteredUsers ? '${SCIENTIFIC_MODELS_API_KEY}' : '{{SCIENTIFIC_MODELS_API_KEY}}',\n" +
    "        SCIENTIFIC_MODELS_API_BASE_URL: '${SCIENTIFIC_MODELS_API_BASE_URL}',\n" +
    "        NEBIUS_API_KEY: '${NEBIUS_API_KEY}' },\n" +
    "      ...(!sharedRegisteredUsers ? { customUserVars: { SCIENTIFIC_MODELS_API_KEY: {\n" +
    "        title: 'Scientific AI API key', description: 'Your personal platform key, also configurable in the Apps panel.', sensitive: true,\n" +
    "      } } } : {}), serverInstructions: true,",
);

await replaceExact(
  '/app/api/server/routes/scientific-demos.js',
  "async function key(req) {\n" +
    "  return getUserPluginAuthValue(req.user.id, 'SCIENTIFIC_MODELS_API_KEY', false, 'mcp_scientific-demos');\n" +
    "}",
  "async function key(req) {\n" +
    "  const personal = await getUserPluginAuthValue(req.user.id, 'SCIENTIFIC_MODELS_API_KEY', false, 'mcp_scientific-demos');\n" +
    "  if (personal) return personal;\n" +
    "  if (process.env.SCIENTIFIC_SHARED_GATEWAY_ENABLED === 'true') {\n" +
    "    return process.env.SCIENTIFIC_MODELS_API_KEY;\n" +
    "  }\n" +
    "  return personal;\n" +
    "}",
);

process.stdout.write('Kopra shared-registration patch applied.\n');
