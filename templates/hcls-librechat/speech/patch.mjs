import { readFile, writeFile } from 'node:fs/promises';
const mode = process.argv[2];
const replace = async (filename, before, after) => {
  const source = await readFile(filename, 'utf8');
  if (source.split(before).length !== 2) throw new Error(`Unsupported pinned speech patch: ${filename}`);
  await writeFile(filename, source.replace(before, after));
};
if (mode === 'client') {
  // This dedicated demo has an always-visible English microphone independent of
  // browser STT preferences. The general-purpose upstream speech hook is unused.
  await replace('/app/client/src/components/Chat/Input/ChatForm.tsx',
    '{SpeechToText && (', '{true && (');
  await replace('/app/client/src/components/ScientificDemos.tsx',
    "import { useEffect, useState } from 'react';", "import { useEffect, useState } from 'react';\nimport LiveSpeech from './LiveSpeech';");
  await replace('/app/client/src/components/ScientificDemos.tsx',
    '<h2 className="text-xl font-semibold">Transcript or recording → report draft</h2>',
    '<LiveSpeech /><h2 className="text-xl font-semibold">Transcript or recording → report draft</h2>');
} else if (mode === 'server') {
  await replace('/app/api/server/routes/scientific-demos.js',
    'router.use((error, _req, res, _next) => {',
    "require('/opt/hcls-librechat/speech/relay.cjs').installRoutes(router, { key, platform: service.platform });\nrequire('/opt/hcls-librechat/speech/diarization.cjs').installRoutes(router, { key });\nrouter.use((error, _req, res, _next) => {");
  await replace('/app/api/server/index.js', '  configureServerTimeouts(server);',
    "  require('/opt/hcls-librechat/speech/relay.cjs').attach(server);\n  configureServerTimeouts(server);");
} else throw new Error('Select client or server patch');
