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
  await replace('/app/client/src/components/Chat/Input/ChatForm.tsx',
    "import AudioRecorder from './AudioRecorder';",
    "import AudioRecorder from './AudioRecorder';\nimport { submitWithWorkshopAudio } from '~/components/workshop-client';");
  await replace('/app/client/src/components/Chat/Input/ChatForm.tsx',
    '        return submitMessage(data);\n      })}',
    '        return submitWithWorkshopAudio(data, conversation, submitMessage);\n      })}');
  await replace('/app/client/src/components/Chat/Messages/Content/Parts/Text.tsx',
    "import store from '~/store';",
    "import store from '~/store';\nimport { visibleWorkshopPrompt } from '~/components/workshop-client';");
  await replace('/app/client/src/components/Chat/Messages/Content/Parts/Text.tsx',
    'const TextPart = memo(function TextPart({ text, isCreatedByUser, showCursor }: TextPartProps) {',
    'const TextPart = memo(function TextPart({ text: sourceText, isCreatedByUser, showCursor }: TextPartProps) {\n  const text = isCreatedByUser ? visibleWorkshopPrompt(sourceText) : sourceText;');
  await replace('/app/client/src/components/Chat/Messages/Content/MessageContent.tsx',
    "import store from '~/store';",
    "import store from '~/store';\nimport { visibleWorkshopPrompt } from '~/components/workshop-client';");
  await replace('/app/client/src/components/Chat/Messages/Content/MessageContent.tsx',
    'const DisplayMessage = ({ text, isCreatedByUser, message, showCursor }: TDisplayProps) => {',
    'const DisplayMessage = ({ text: sourceText, isCreatedByUser, message, showCursor }: TDisplayProps) => {\n  const text = isCreatedByUser ? visibleWorkshopPrompt(sourceText) : sourceText;');
  await replace('/app/client/src/components/ScientificDemos.tsx',
    "import { useEffect, useState } from 'react';", "import { useEffect, useState } from 'react';\nimport LiveSpeech from './LiveSpeech';\nimport ClinicalSoap from './ClinicalSoap';");
  await replace('/app/client/src/components/ScientificDemos.tsx',
    '<h2 className="text-xl font-semibold">Transcript or recording → report draft</h2>',
    '<LiveSpeech /><h2 className="text-xl font-semibold">Transcript or recording → report draft</h2>');
  await replace('/app/client/src/components/ScientificDemos.tsx',
    '        })}>{name}</Button>)}</div>\n      </article>)}',
    '        })}>{name}</Button>)}</div>\n        {job.status === \'completed\' && <ClinicalSoap jobId={job.id} />}\n      </article>)}');
} else if (mode === 'server') {
  await replace('/app/api/server/routes/scientific-demos.js',
    'router.use((error, _req, res, _next) => {',
    "require('/opt/hcls-librechat/speech/relay.cjs').installRoutes(router, { key, platform: service.platform });\nrequire('/opt/hcls-librechat/speech/diarization.cjs').installRoutes(router, { key, platform: service.platform, artifactBytes: service.platformBytes });\nrouter.use((error, _req, res, _next) => {");
  const attached = "  require('/opt/hcls-librechat/speech/relay.cjs').attach(server);\n  configureServerTimeouts(server);";
  const index = await readFile('/app/api/server/index.js', 'utf8');
  if (!index.includes(attached)) await replace('/app/api/server/index.js', '  configureServerTimeouts(server);', attached);
  else if (index.split("require('/opt/hcls-librechat/speech/relay.cjs').attach(server);").length !== 2) throw new Error('Expected exactly one existing speech relay attachment');
} else throw new Error('Select client or server patch');
