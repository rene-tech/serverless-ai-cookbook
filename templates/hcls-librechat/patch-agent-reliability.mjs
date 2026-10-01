// Additive patch to the pinned R11 graph. No routing/model/tool-budget changes.
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

function replaceOnce(source, before, after, name) {
  if (source.includes(after)) throw new Error(`${name} is already installed`);
  if (source.split(before).length !== 2) throw new Error(`Unsupported pinned ${name} seam`);
  return source.replace(before, after);
}

export function patchProviderRecovery(source) {
  source = replaceOnce(source,
    '\n\t\t\t\tresult = await require_langfuseRuntimeScope.withLangfuseRuntimeScope(',
    "\n\t\t\t\tresult = await require('/opt/hcls-librechat/scientific-provider-recovery.cjs').invokeWithRecovery({\n" +
    '\t\t\t\t\tinvoke: (recover) => require_langfuseRuntimeScope.withLangfuseRuntimeScope(',
    'empty provider recovery start');
  source = replaceOnce(source,
    'request: preparedRequest,',
    `request: recover ? (() => {
\t\t\t\t\t\tconst recoveryMessages = require('/opt/hcls-librechat/scientific-provider-recovery.cjs').recoveryMessages(beforeFinalProviderProjection, _langchain_core_messages.SystemMessage);
\t\t\t\t\t\tconst recovery = require_prepareProviderRequest.prepareProviderRequest({
\t\t\t\t\t\t\tmodel: this.overrideModel ?? model, messages: recoveryMessages,
\t\t\t\t\t\t\tprovider: agentContext.provider, context: this, config,
\t\t\t\t\t\t\tmaxToolResultChars: maxProviderToolResultChars, measure: measureProviderPayload
\t\t\t\t\t\t});
\t\t\t\t\t\tif (!recovery.measurement?.fits) throw createProviderPayloadOverflowError({
\t\t\t\t\t\t\tprojection: recovery.measurement, provider: agentContext.provider,
\t\t\t\t\t\t\tinfo: 'Empty-response recovery does not fit the unchanged context budget.'
\t\t\t\t\t\t});
\t\t\t\t\t\treturn recovery;
\t\t\t\t\t})() : preparedRequest,`,
    'bounded recovery notice');
  return replaceOnce(source,
    '\t\t\t\t}, invokeConfig));\n\t\t\t} catch (primaryError) {',
    `\t\t\t\t}, invokeConfig)),
\t\t\t\t\tsignal: invokeConfig.signal,
\t\t\t\t\tcanRetry: () => !hasCurrentTextDeltaStep({ graph: this, metadata }) &&
\t\t\t\t\t\t![...(this.pendingToolCallsByStep?.values() ?? [])].some((calls) => calls.size > 0),
\t\t\t\t\tobserveEmpty: (message) => {
\t\t\t\t\t\trequire('/opt/hcls-librechat/scientific-context-audit.cjs').response(message, agentContext);
\t\t\t\t\t\trequire_events.emitAgentLog(config, "warn", "graph", "Recovering an empty provider response without replaying tools", { retry: 1 }, invokeMeta, { force: true });
\t\t\t\t\t}
\t\t\t\t});
\t\t\t} catch (primaryError) {`, 'empty provider recovery end');
}

export function patchVerifiedDelivery(source) {
  source = replaceOnce(source,
    "const studyAdmissionText = require('/opt/hcls-librechat/scientific-study-admission.cjs')(messages);",
    "const verifiedDeliveryText = require('/opt/hcls-librechat/scientific-verified-delivery.cjs')(messages);\n" +
    "\t\t\tconst studyAdmissionText = verifiedDeliveryText ?? require('/opt/hcls-librechat/scientific-study-admission.cjs')(messages);",
    'verified delivery boundary');
  return replaceOnce(source,
    'response_metadata: { scientific_admission_acknowledgement: true }',
    'response_metadata: { scientific_admission_acknowledgement: verifiedDeliveryText === null, scientific_verified_delivery: verifiedDeliveryText !== null }',
    'verified delivery provenance');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const path = '/app/node_modules/@librechat/agents/dist/cjs/graphs/Graph.cjs';
  await writeFile(path, patchVerifiedDelivery(patchProviderRecovery(await readFile(path, 'utf8'))));
}
